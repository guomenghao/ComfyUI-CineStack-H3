"""Check release identity and runtime packaging; --publish requires a publisher."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project, comfy = config["project"], config["tool"]["comfy"]
    assert project["name"] == "cinestack-h3", "Incorrect Registry package identity"
    assert re.fullmatch(r"\d+\.\d+\.\d+", project["version"]), "Use X.Y.Z versions"
    assert project["urls"]["Repository"] == "https://github.com/guomenghao/ComfyUI-CineStack-H3"
    requirements = [line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    assert project["dependencies"] == requirements, "Dependency metadata drift"
    assert comfy["PublisherId"] != "aimixer", "Never publish under the upstream author's identity"
    if args.publish:
        assert comfy["PublisherId"].strip(), "Set your registered Comfy PublisherId before publishing"
    mapping = json.loads((ROOT / "node_ids.json").read_text())
    tree = ast.parse((ROOT / "__init__.py").read_text())
    registered = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS" for t in node.targets))
    keys = [key.value for key in registered.keys]
    assert len(keys) == len(set(keys)), "Duplicate node mappings"
    assert set(keys) == set(mapping.values()), "Node registry and migration mapping disagree"
    for rel in ("LICENSE", "NOTICE", "director/segment_seed.py", "director/refine_only.py",
                "web/js/minimax_segment_seed.js", "web/js/cinestack_migration.js", "node_ids.json",
                "web/js/cinestack_director_overview.js", "director/execution_mode.py", "director/low_memory.py"):
        assert (ROOT / rel).is_file(), f"Missing runtime/release file: {rel}"
    for path in (ROOT / "example_workflows").glob("*.json"):
        graph = json.loads(path.read_text())
        assert not any(n.get("type") in mapping for n in graph.get("nodes", [])), f"Unmigrated example: {path}"
    print(f"CineStack {project['version']}: release identity, dependencies, nodes and examples validated.")
    if not comfy["PublisherId"]:
        print("Registry preparation only: PublisherId is intentionally unset.")


if __name__ == "__main__":
    main()
