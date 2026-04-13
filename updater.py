from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import GITHUB_LATEST_RELEASE_API, GITHUB_RELEASES_URL

_VERSION_PARTS_RE = re.compile(r"\d+")


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateStatus:
    current_version: str
    latest_version: str
    download_url: str
    html_url: str
    update_available: bool


def _normalize_version(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in _VERSION_PARTS_RE.findall(value)]
    return tuple(parts) if parts else (0,)


def fetch_latest_release(current_version: str) -> UpdateStatus:
    request = Request(
        GITHUB_LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AITextNormalizer",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise UpdateCheckError(f"Could not reach GitHub: {exc.reason}") from exc
    except Exception as exc:
        raise UpdateCheckError("Could not read release metadata.") from exc

    if not isinstance(payload, dict):
        raise UpdateCheckError("Unexpected GitHub response.")

    tag_name = str(payload.get("tag_name") or "")
    latest_version = tag_name.removeprefix("v") or current_version
    html_url = str(payload.get("html_url") or GITHUB_RELEASES_URL)

    download_url = html_url
    assets = payload.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if name.lower().endswith('.exe'):
                download_url = str(asset.get("browser_download_url") or html_url)
                break

    return UpdateStatus(
        current_version=current_version,
        latest_version=latest_version,
        download_url=download_url,
        html_url=html_url,
        update_available=_normalize_version(latest_version) > _normalize_version(current_version),
    )
