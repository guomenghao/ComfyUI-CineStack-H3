"""Convert legacy Director workflows or API prompts without changing their inputs."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_IDS = json.loads((ROOT / "node_ids.json").read_text(encoding="utf-8"))


def migrate_workflow(data):
    result = deepcopy(data)
    changed = 0

    def node(item, key):
        nonlocal changed
        if not isinstance(item, dict) or item.get(key) not in NODE_IDS:
            return
        item[key] = NODE_IDS[item[key]]
        changed += 1
        if key == "type":
            props = item.setdefault("properties", {})
            props.update({"Node name for S&R": item[key], "cnr_id": "cinestack-h3",
                          "ver": "0.1.0", "aux_id": "guomenghao/ComfyUI-CineStack-H3"})

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
