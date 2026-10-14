"""Installed package version, captured once when the server imports this module.

Read only our simple [project] version field; no extra TOML dependency on Python 3.10.
"""
from pathlib import Path
import logging
import re


def read_project_version(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("pyproject.toml")
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.fullmatch(r"\s*\[([^\]]+)\]\s*(?:#.*)?", line)
        if heading:
            section = heading.group(1)
        if section == "project":
            match = re.fullmatch(r"\s*version\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']\s*(?:#.*)?", line)
            if match:
                return match.group(1)
    raise ValueError("Missing or invalid [project].version in pyproject.toml")


try:
    PLUGIN_VERSION = read_project_version()
except (OSError, ValueError) as exc:
    PLUGIN_VERSION = None
    logging.getLogger("ComfyUI-CineStack-H3").warning("Cannot read installed plugin version: %s", exc)
