"""Serve one immutable, versioned ESM tree per running ComfyUI process."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import tempfile

from .package_version import PLUGIN_VERSION

_HOST_IMPORT = re.compile(
    r'''(?P<prefix>\bfrom\s+|\bimport\s*(?:\(\s*)?)(?P<quote>["'])(?:\.\./)+(?P<path>scripts/[^"']+)(?P=quote)'''
)


@dataclass
class FrontendAssets:
    directory: tempfile.TemporaryDirectory
    token: str
    files: dict[str, bytes]

    @property
    def web_directory(self) -> str:
        return self.directory.name


def build_frontend_assets(source_dir: Path, version: str) -> FrontendAssets:
    if not version or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Cannot serve frontend without a valid installed version")
    files = {}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(source_dir).parts):
            continue
        relative = path.relative_to(source_dir)
        content = path.read_bytes()
        if path.suffix == ".js":
            source = content.decode("utf-8").replace("\r\n", "\n")
            # /extensions/<plugin>/<version>/<relative file> -> host /scripts/.
            # Keep the host modules canonical: a second app.js instance is unsafe.
            prefix = "../" * (3 + len(relative.parts) - 1)
            source = _HOST_IMPORT.sub(
                lambda m: m["prefix"] + m["quote"] + prefix + m["path"] + m["quote"], source
            )
            content = source.encode("utf-8")
        files[relative.as_posix()] = content
    if not files or "cinestack_migration.js" not in files:
        raise ValueError("CineStack frontend sources are missing")
    digest = hashlib.sha256(version.encode("ascii") + b"\0")
    for name, content in files.items():
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(content).digest())
    token = f"v{version}-{digest.hexdigest()[:16]}"
    # Use OS temp, not ComfyUI's temp folder (which startup/cleanup can erase).
    # This object is held for the entire process lifetime; no writes to plugin sources.
    directory = tempfile.TemporaryDirectory(prefix="cinestack-web-", ignore_cleanup_errors=True)
    try:
        for name, content in files.items():
            target = Path(directory.name) / token / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    except BaseException:
        directory.cleanup()
        raise
    return FrontendAssets(directory, token, files)


@lru_cache(maxsize=1)
def get_frontend_assets() -> FrontendAssets:
    return build_frontend_assets(Path(__file__).parent / "web" / "js", PLUGIN_VERSION)
