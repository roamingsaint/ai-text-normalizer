from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


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

    def normalize(self, text: str) -> str:
        result = text
        for rule in self.literal_replacements:
            if rule.find:
                result = result.replace(rule.find, rule.replace)
        for rule in self.regex_replacements:
            result = rule.compiled().sub(rule.replace, result)
        return result


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
    )


def load_rules(path: Path) -> NormalizationRules:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        LOGGER.warning("rules file missing: %s", path)
        return NormalizationRules()
    except json.JSONDecodeError:
        LOGGER.exception("invalid rules file: %s", path)
        return NormalizationRules()

    if not isinstance(payload, dict):
        LOGGER.warning("rules file must contain a JSON object: %s", path)
        return NormalizationRules()

    return _parse_rules_payload(payload)


def normalize_text(text: str, rules: NormalizationRules) -> str:
    return rules.normalize(text)
