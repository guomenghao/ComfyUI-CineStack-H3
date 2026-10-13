"""Check migration preserves real workflows and independent runtime identities."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cinestack_migration", ROOT / "tools/migrate_workflow.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class CineStackReleaseTests(unittest.TestCase):
    def test_ui_and_nested_graphs_preserve_inputs_and_original(self):
        node = {"id": 9, "type": "MiniMaxH3Director", "widgets_values": ["seed", 17,
                '{"segments":[{"first_pass_seed":"18446744073709551615"}]}'],
                "inputs": [{"name": "model", "link": 10}]}
        graph = {"nodes": [node], "links": [[10, 1, 0, 9, 0, "MODEL"]],
                 "definitions": {"subgraphs": [{"nodes": [{"id": 2, "type": "MiniMaxH3DirectorRefine"}]}]},
                 "extra": {"groupNodes": {"old": {"nodes": [{"type": "ComfyMiniMaxH3Director"}]}}}}
        before = json.dumps(graph)
        converted, count = migration.migrate_workflow(graph)
        self.assertEqual(count, 3)
        self.assertEqual(json.dumps(graph), before)
        self.assertEqual(converted["nodes"][0]["type"], "CineStackH3Director")
        self.assertEqual(converted["nodes"][0]["widgets_values"], node["widgets_values"])
        self.assertEqual(converted["nodes"][0]["inputs"], node["inputs"])
        self.assertEqual(converted["links"], graph["links"])
        self.assertEqual(converted["nodes"][0]["id"], 9)

    def test_api_queue_and_unrelated_model_nodes(self):
        prompt = {"3": {"class_type": "MiniMaxH3DirectorRefine", "inputs": {"seed": 0, "refine_only": True}},
                  "4": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"prompt": "MiniMaxH3Director"}}}
        for source in (prompt, {"prompt": prompt, "client_id": "test"}):
            converted, count = migration.migrate_workflow(source)
            converted = converted.get("prompt", converted)
            self.assertEqual(count, 1)
            self.assertEqual(converted["3"]["class_type"], "CineStackH3DirectorRefine")
            self.assertEqual(converted["3"]["inputs"], prompt["3"]["inputs"])
            self.assertEqual(converted["4"], prompt["4"])

    def test_repeat_migration_is_idempotent(self):
        graph, _ = migration.migrate_workflow({"nodes": [{"type": "MiniMaxH3Director"}]})
        again, count = migration.migrate_workflow(graph)
        self.assertEqual(count, 0)
        self.assertEqual(again, graph)

    def test_release_metadata_and_publisher_gate(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/check_release.py")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        result = subprocess.run([sys.executable, str(ROOT / "tools/check_release.py"), "--publish"], capture_output=True)
        with (ROOT / "pyproject.toml").open("rb") as stream:
            publisher = tomllib.load(stream)["tool"]["comfy"]["PublisherId"].strip()
        if publisher:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"PublisherId", result.stderr)

    def test_all_examples_match_node_identity_and_routes_are_namespaced(self):
        ids = set(migration.NODE_IDS.values())
        for path in (ROOT / "example_workflows").glob("*.json"):
            for node in json.loads(path.read_text())["nodes"]:
                if node["type"] in ids:
                    self.assertEqual(node["properties"]["cnr_id"], "cinestack-h3")
                    self.assertEqual(node["properties"]["aux_id"], "guomenghao/ComfyUI-CineStack-H3")
        for directory in ("web/js", "director"):
            for path in (ROOT / directory).rglob("*"):
                if path.suffix in (".py", ".js"):
                    self.assertNotIn("/minimax/director/", path.read_text(), str(path))


if __name__ == "__main__":
    unittest.main()
