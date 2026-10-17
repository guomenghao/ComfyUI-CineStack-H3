"""Build with comfy-cli's offline packer, then validate the extracted runtime.

Requires comfy-cli==1.22.0. No Registry request, credentials or publishing.
Only git-tracked files are packed: stage new release files before running.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def verify_archive(archive: Path, source: Path = ROOT):
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        # Require every current runtime source, not just a small hand-picked list.
        required = {p.relative_to(source).as_posix() for p in source.rglob("*.py")
                    if p.relative_to(source).parts[0] not in ("tests", "tools")
                    and not any(x.startswith('.') or x in ('node_modules', '__pycache__')
                                for x in p.relative_to(source).parts)}
        required |= {p.relative_to(source).as_posix() for p in (source / "web").rglob("*") if p.is_file()}
        required |= {p.relative_to(source).as_posix() for p in (source / "example_workflows").rglob("*") if p.is_file()}
        required |= {"pyproject.toml", "requirements.txt", "LICENSE", "NOTICE", "node_ids.json",
                     "example_workflows/cinestack_five_shots_first_pass.json",
                     "example_workflows/cinestack_five_shots_refine_only.json",
                     "docs/five-shot-workflow.md", "docs/publishing.md"}
        assert not required - names, f"Missing package files: {sorted(required - names)}"
        forbidden = [n for n in names if any(part in ('.git', 'tests', 'node_modules', '__pycache__',
                     '.github', 'qa', 'models', 'minimax_seg_cache') for part in Path(n).parts)
                     or Path(n).suffix.lower() in ('.pt', '.safetensors', '.mp4', '.log', '.pyc')
                     or Path(n).name.startswith('.env')]
        assert not forbidden, f"Development/private/generated files in package: {forbidden}"
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        with tempfile.TemporaryDirectory(prefix="cinestack-package-check-") as temp:
            extracted = Path(temp)
            z.extractall(extracted)
            subprocess.run([sys.executable, str(extracted / "tools/check_release.py"), "--publish"], check=True)
            # The immutable frontend must also build outside a Git checkout.
            package = types.ModuleType("cinestack_package_check")
            package.__path__ = [str(extracted)]
            sys.modules[package.__name__] = package
            spec = importlib.util.spec_from_file_location("cinestack_package_check.frontend_assets", extracted / "frontend_assets.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            assets = module.get_frontend_assets()
            assert Path(assets.web_directory).is_dir()
        return {"files": len(names), "runtime_files_checked": len(required), "bytes": archive.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive = args.output.resolve()
    assert ROOT not in archive.parents, "Write candidate archives outside the source checkout"
    assert subprocess.check_output(['git', '-C', str(ROOT), 'ls-files']).strip(), 'A tracked checkout is required'
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cinestack-cli-config-") as config_dir:
        # Importing the CLI UI creates config directories. Isolate those side effects.
        from comfy_cli import constants
        constants.DEFAULT_CONFIG = {key: config_dir for key in constants.DEFAULT_CONFIG}
        from comfy_cli.file_utils import zip_files
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            # comfy-cli 1.22.0 uses line-based `git ls-files`; default Git quoting
            # turns Chinese names into escaped strings that do not exist on disk.
            index = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
            with patch.dict(os.environ, {"GIT_CONFIG_COUNT": str(index + 1),
                            f"GIT_CONFIG_KEY_{index}": "core.quotepath",
                            f"GIT_CONFIG_VALUE_{index}": "false"}):
                zip_files(str(archive))
        finally:
            os.chdir(previous)
    print(json.dumps(verify_archive(archive), ensure_ascii=False))
    print(f"Offline package validated: {archive}; nothing published.")


if __name__ == "__main__":
    main()
