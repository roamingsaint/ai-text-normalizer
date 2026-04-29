from __future__ import annotations

import hashlib
import json
import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
RULES_VERSION_KEY = "rules_version"
BASED_ON_RULES_VERSION_KEY = "based_on_rules_version"
BASE_RULES_DIGEST_KEY = "base_rules_digest"
RULES_METADATA_KEYS = {
    "version",
    RULES_VERSION_KEY,
    BASED_ON_RULES_VERSION_KEY,
    BASE_RULES_DIGEST_KEY,
}
LEGACY_DEFAULT_RULESET_VERSIONS = {
    "47043033ec2c3d62e1b22b80f999d9c5f4f7b9950e24eb8d50fb8fe730994783": "1.0.0",
}


@dataclass(frozen=True)
class LiteralReplacement:
    find: str
    replace: str


@dataclass(frozen=True)
class RegexReplacement:
    pattern: str
    replace: str
    flags: int = 0

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, self.flags)


@dataclass
class NormalizationRules:
    literal_replacements: list[LiteralReplacement] = field(default_factory=list)
    regex_replacements: list[RegexReplacement] = field(default_factory=list)
    rules_version: str = ""
    based_on_rules_version: str = ""
    base_rules_digest: str = ""
    current_rules_digest: str = ""

    def normalize(self, text: str) -> str:
        result = text
        for rule in self.literal_replacements:
            if rule.find:
                result = result.replace(rule.find, rule.replace)
        for rule in self.regex_replacements:
            result = rule.compiled().sub(rule.replace, result)
        return result

    def is_customized(self) -> bool:
        return bool(self.base_rules_digest) and self.current_rules_digest != self.base_rules_digest


def _rules_payload_without_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = {
        key: value
        for key, value in payload.items()
        if key not in RULES_METADATA_KEYS
    }
    return sanitized


def compute_rules_digest_from_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        _rules_payload_without_metadata(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_rules_payload_to_toml(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        '# AI Text Normalizer rules',
        '# Comments are allowed in TOML. For detailed guidance and examples, see RULES.md.',
        "",
    ]
    version = payload.get("version", 1)
    lines.append(f"version = {int(version) if isinstance(version, int) else 1}")
    rules_version = str(payload.get(RULES_VERSION_KEY) or "")
    if rules_version:
        lines.append(f'{RULES_VERSION_KEY} = {json.dumps(rules_version, ensure_ascii=False)}')
    based_on_rules_version = str(payload.get(BASED_ON_RULES_VERSION_KEY) or "")
    if based_on_rules_version:
        lines.append(f'{BASED_ON_RULES_VERSION_KEY} = {json.dumps(based_on_rules_version, ensure_ascii=False)}')
    base_rules_digest = str(payload.get(BASE_RULES_DIGEST_KEY) or "")
    if base_rules_digest:
        lines.append(f'{BASE_RULES_DIGEST_KEY} = {json.dumps(base_rules_digest, ensure_ascii=False)}')

    literal_rules = payload.get("literal_replacements", [])
    if isinstance(literal_rules, list):
        for entry in literal_rules:
            if not isinstance(entry, dict):
                continue
            find = entry.get("find", "")
            replace = entry.get("replace", "")
            if not isinstance(find, str) or not isinstance(replace, str):
                continue
            lines.extend(
                [
                    "",
                    "[[literal_replacements]]",
                    f"find = {json.dumps(find, ensure_ascii=False)}",
                    f"replace = {json.dumps(replace, ensure_ascii=False)}",
                ]
            )

    regex_rules = payload.get("regex_replacements", [])
    if isinstance(regex_rules, list):
        for entry in regex_rules:
            if not isinstance(entry, dict):
                continue
            pattern = entry.get("pattern", "")
            replace = entry.get("replace", "")
            if not isinstance(pattern, str) or not isinstance(replace, str):
                continue
            lines.extend(
                [
                    "",
                    "[[regex_replacements]]",
                    f"pattern = {json.dumps(pattern, ensure_ascii=False)}",
                    f"replace = {json.dumps(replace, ensure_ascii=False)}",
                ]
            )
            flags = entry.get("flags")
            if isinstance(flags, list) and flags:
                encoded_flags = ", ".join(json.dumps(str(flag), ensure_ascii=False) for flag in flags)
                lines.append(f"flags = [{encoded_flags}]")
            elif isinstance(flags, int) and flags:
                lines.append(f"flags = {flags}")

    return "\n".join(lines) + "\n"


def load_rules_payload(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".toml":
        payload = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    else:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("rules file must contain a JSON object")
    return payload


def stamp_live_rules_payload(payload: dict[str, Any], *, based_on_rules_version: str | None = None) -> dict[str, Any]:
    stamped = dict(payload)
    rules_version = str(stamped.get(RULES_VERSION_KEY) or "")
    if not based_on_rules_version:
        based_on_rules_version = rules_version
    stamped[BASED_ON_RULES_VERSION_KEY] = based_on_rules_version
    stamped[BASE_RULES_DIGEST_KEY] = compute_rules_digest_from_payload(stamped)
    return stamped


def write_rules_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".toml":
        path.write_text(serialize_rules_payload_to_toml(payload), encoding="utf-8")
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_regex_flags(raw_flags: Any) -> int:
    if not raw_flags:
        return 0
    if isinstance(raw_flags, int):
        return raw_flags
    flags = 0
    if isinstance(raw_flags, list):
        for flag_name in raw_flags:
            if not isinstance(flag_name, str):
                continue
            flags |= getattr(re, flag_name.upper(), 0)
    return flags


def _parse_rules_payload(payload: dict[str, Any]) -> NormalizationRules:
    literal_rules: list[LiteralReplacement] = []
    regex_rules: list[RegexReplacement] = []

    raw_literal_rules = payload.get("literal_replacements", [])
    if isinstance(raw_literal_rules, list):
        for entry in raw_literal_rules:
            if not isinstance(entry, dict):
                continue
            find = entry.get("find", "")
            replace = entry.get("replace", "")
            if isinstance(find, str) and isinstance(replace, str):
                literal_rules.append(LiteralReplacement(find=find, replace=replace))

    raw_regex_rules = payload.get("regex_replacements", [])
    if isinstance(raw_regex_rules, list):
        for entry in raw_regex_rules:
            if not isinstance(entry, dict):
                continue
            pattern = entry.get("pattern", "")
            replace = entry.get("replace", "")
            flags = _parse_regex_flags(entry.get("flags"))
            if isinstance(pattern, str) and isinstance(replace, str):
                regex_rules.append(RegexReplacement(pattern=pattern, replace=replace, flags=flags))

    raw_combined_rules = payload.get("replacements", [])
    if isinstance(raw_combined_rules, list):
        for entry in raw_combined_rules:
            if not isinstance(entry, dict):
                continue
            rule_type = str(entry.get("type", "literal")).lower()
            replace = entry.get("replace", "")
            if rule_type == "regex":
                pattern = entry.get("pattern", entry.get("find", ""))
                flags = _parse_regex_flags(entry.get("flags"))
                if isinstance(pattern, str) and isinstance(replace, str):
                    regex_rules.append(RegexReplacement(pattern=pattern, replace=replace, flags=flags))
            else:
                find = entry.get("find", entry.get("pattern", ""))
                if isinstance(find, str) and isinstance(replace, str):
                    literal_rules.append(LiteralReplacement(find=find, replace=replace))

    return NormalizationRules(
        literal_replacements=literal_rules,
        regex_replacements=regex_rules,
        rules_version=str(payload.get(RULES_VERSION_KEY) or ""),
        based_on_rules_version=str(payload.get(BASED_ON_RULES_VERSION_KEY) or ""),
        base_rules_digest=str(payload.get(BASE_RULES_DIGEST_KEY) or ""),
        current_rules_digest=compute_rules_digest_from_payload(payload),
    )


def infer_legacy_rules_version(rules: NormalizationRules) -> str:
    return LEGACY_DEFAULT_RULESET_VERSIONS.get(rules.current_rules_digest, "")


def load_rules(path: Path) -> NormalizationRules:
    try:
        payload = load_rules_payload(path)
    except FileNotFoundError:
        LOGGER.warning("rules file missing: %s", path)
        return NormalizationRules()
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ValueError):
        LOGGER.exception("invalid rules file: %s", path)
        return NormalizationRules()

    return _parse_rules_payload(payload)


def normalize_text(text: str, rules: NormalizationRules) -> str:
    return rules.normalize(text)

