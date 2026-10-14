"""Check migration preserves real workflows and independent runtime identities."""
import ast
import asyncio
import tempfile
from types import SimpleNamespace
from aiohttp import web
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

    def test_existing_cinestack_and_nested_versions_refresh_without_input_changes(self):
        node = {"type": "CineStackH3Director", "properties": {"ver": "0.1.1", "custom": 17},
                "widgets_values": ["18446744073709551615"], "inputs": [{"link": 3}]}
        graph = {"nodes": [node, {"type": "Other", "properties": {"ver": "other"}}],
                 "definitions": {"subgraphs": [{"nodes": [node]}]},
                 "extra": {"groupNodes": {"old": {"nodes": [node]}}}}
        result, count = migration.migrate_workflow(graph)
        self.assertEqual(count, 0)
        self.assertEqual(node["properties"]["ver"], "0.1.1")
        for updated in (result["nodes"][0], result["definitions"]["subgraphs"][0]["nodes"][0],
                        result["extra"]["groupNodes"]["old"]["nodes"][0]):
            self.assertEqual(updated["properties"]["ver"], migration.PLUGIN_VERSION)
            self.assertEqual(updated["properties"]["custom"], 17)
            self.assertEqual(updated["widgets_values"], node["widgets_values"])
            self.assertEqual(updated["inputs"], node["inputs"])
        self.assertEqual(result["nodes"][1], graph["nodes"][1])

    def test_version_reader_uses_only_project_section_and_supports_python310(self):
        module = migration._version_module
        with (ROOT / "pyproject.toml").open("rb") as stream:
            self.assertEqual(module.PLUGIN_VERSION, tomllib.load(stream)["project"]["version"])
        ast.parse((ROOT / "package_version.py").read_text(), feature_version=(3, 10))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pyproject.toml"
            path.write_text("[tool.other]\nversion = \"9.9.9\"\n[project]\nversion = '1.2.3' # test\n")
            self.assertEqual(module.read_project_version(path), "1.2.3")
            for contents in ("[tool.other]\nversion = '9.9.9'", "[project]\nversion = 'main'"):
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    module.read_project_version(path)
        # Reading a different on-disk version never mutates this process's startup snapshot.
        self.assertEqual(module.PLUGIN_VERSION, migration.PLUGIN_VERSION)

    def test_version_route_reports_runtime_snapshot_and_disables_cache(self):
        tree = ast.parse((ROOT / "director/http_routes.py").read_text())
        handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "cinestack_version")
        namespace = {"PLUGIN_VERSION": "1.2.3", "web": web,
                     "get_frontend_assets": lambda: SimpleNamespace(token="v1.2.3-test")}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "http_routes.py", "exec"), namespace)
        response = asyncio.run(namespace[handler.name](None))
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text), {"package": "cinestack-h3", "version": "1.2.3",
                                                     "frontend_asset_version": "v1.2.3-test"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        namespace["PLUGIN_VERSION"] = None
        response = asyncio.run(namespace[handler.name](None))
        self.assertEqual(response.status, 503)
        self.assertNotIn("version", json.loads(response.text))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

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
