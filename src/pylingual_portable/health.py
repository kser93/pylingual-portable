from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .paths import HF_HUB, MODEL_LINKS, TOOLCHAINS


EXPECTED_TOOLCHAINS = (
    "3.6",
    "3.7",
    "3.8",
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
    "3.15",
)

_TOOLCHAIN_DIR_RE = re.compile(r"^cpython-(\d+\.\d+)\.\d+-win-x64$")


def model_status(
    *,
    links_path: Path = MODEL_LINKS,
    hub: Path = HF_HUB,
) -> dict[str, Any]:
    """Return only model packs that actually exist in the local HF cache."""
    try:
        links = json.loads(Path(links_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "models": [],
            "installed": {},
            "missing": [],
            "errors": [f"cannot read {links_path}: {exc!r}"],
        }

    installed: dict[str, dict[str, str]] = {}
    missing: list[dict[str, Any]] = []
    for version, roles in links.items():
        for role, entry in roles.items():
            repo = str(entry.get("repo", ""))
            sha = str(entry.get("sha", ""))
            files = entry.get("files") or {}
            snapshot = Path(hub) / ("models--" + repo.replace("/", "--")) / "snapshots" / sha
            absent: list[str] = []
            if not repo or not sha:
                absent.append("pin")
            if not snapshot.is_dir():
                absent.append("snapshot")
            else:
                for filename in files:
                    path = snapshot / filename
                    if not path.is_file() or path.stat().st_size <= 0:
                        absent.append(str(filename))
            if absent:
                missing.append(
                    {
                        "version": version,
                        "role": role,
                        "path": str(snapshot),
                        "missing": absent,
                    }
                )
            else:
                installed.setdefault(version, {})[role] = str(snapshot)

    complete_versions = [
        version
        for version, roles in links.items()
        if set(installed.get(version, {})) == set(roles)
    ]
    return {
        "ok": bool(links) and len(complete_versions) == len(links) and not missing,
        "models": sorted(complete_versions),
        "installed": installed,
        "missing": missing,
        "errors": [],
    }


def toolchain_status(
    *,
    toolchains_dir: Path = TOOLCHAINS,
    expected: tuple[str, ...] = EXPECTED_TOOLCHAINS,
) -> dict[str, Any]:
    """Return local target toolchains, keyed by major.minor."""
    installed: dict[str, str] = {}
    for python in sorted(Path(toolchains_dir).glob("cpython-*-win-x64/python.exe")):
        match = _TOOLCHAIN_DIR_RE.match(python.parent.name)
        if match and match.group(1) not in installed:
            installed[match.group(1)] = python.parent.name
    missing = [version for version in expected if version not in installed]
    return {
        "ok": not missing,
        "toolchains": [installed[version] for version in expected if version in installed],
        "installed": installed,
        "missing": missing,
    }


def installation_report(
    *,
    require_models: bool = True,
    require_toolchains: bool = True,
    links_path: Path = MODEL_LINKS,
    hub: Path = HF_HUB,
    toolchains_dir: Path = TOOLCHAINS,
    expected_toolchains: tuple[str, ...] = EXPECTED_TOOLCHAINS,
) -> dict[str, Any]:
    models = model_status(links_path=links_path, hub=hub)
    toolchains = toolchain_status(toolchains_dir=toolchains_dir, expected=expected_toolchains)
    ok = (not require_models or models["ok"]) and (not require_toolchains or toolchains["ok"])
    return {"ok": ok, "models": models, "toolchains": toolchains}
