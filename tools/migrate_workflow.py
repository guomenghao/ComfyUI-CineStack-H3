"""Convert legacy Director workflows or API prompts without changing their inputs."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_version_spec = importlib.util.spec_from_file_location("cinestack_package_version", ROOT / "package_version.py")
_version_module = importlib.util.module_from_spec(_version_spec)
_version_spec.loader.exec_module(_version_module)
# CLI migration must fail rather than stamp an invented version.
PLUGIN_VERSION = _version_module.read_project_version()
NODE_IDS = json.loads((ROOT / "node_ids.json").read_text(encoding="utf-8"))
CINESTACK_IDS = set(NODE_IDS.values())


def migrate_workflow(data):
    result = deepcopy(data)
    changed = 0

    def node(item, key):
        nonlocal changed
        if not isinstance(item, dict):
            return
        if item.get(key) in NODE_IDS:
            item[key] = NODE_IDS[item[key]]
            changed += 1
        if key == "type" and item.get(key) in CINESTACK_IDS:
            props = item.setdefault("properties", {})
            props.update({"Node name for S&R": item[key], "cnr_id": "cinestack-h3",
                          "ver": PLUGIN_VERSION, "aux_id": "guomenghao/ComfyUI-CineStack-H3"})

    def graph(value):
        if not isinstance(value, dict):
            return
        for item in value.get("nodes", []):
            node(item, "type")
        for item in value.get("definitions", {}).get("subgraphs", []):
            graph(item)
        for item in value.get("extra", {}).get("groupNodes", {}).values():
            graph(item)

    if isinstance(result, dict):
        graph(result)
        # API prompts can be supplied directly or inside a queue request.
        prompt = result.get("prompt", result)
        if isinstance(prompt, dict):
            for item in prompt.values():
                node(item, "class_type")
    return result, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("Write to a new file; the original workflow must be preserved.")
    if args.destination.exists():
        parser.error("Destination already exists; choose a new filename.")
    data, count = migrate_workflow(json.loads(args.source.read_text(encoding="utf-8")))
    args.destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Migrated {count} nodes to {args.destination}")


if __name__ == "__main__":
    main()
