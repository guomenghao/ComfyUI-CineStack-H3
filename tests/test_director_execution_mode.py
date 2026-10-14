"""Real executor/cache checks for the new UI intent; Comfy GPU adapters are fixtures."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("workbench_seed_fixture", Path(__file__).with_name("test_segment_seed_refine_only.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class DirectorExecutionModeTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_first_pass_ignores_connected_refine_and_saves_inherited_seed_cache(self):
        plan = self.case.build((None,))
        plan.raw["executionMode"] = "first_pass"
        wired = plan.refine
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual(first, [999])
        self.assertEqual(second, [])
        self.assertTrue(wired["enabled"])
        self.assertFalse(plan.refine["enabled"])
        self.assertIsNotNone(fixture.cache.load_first_pass_cache("fixture", plan.segments[0], plan))

    def test_ui_refine_only_overrides_old_confirm_widgets_without_mutating_pack(self):
        plan = self.case.build()
        plan.raw["executionMode"] = "refine_only"
        plan.refine.update(refine_only=False, confirm_first_pass=True)
        wired = plan.refine
        self.case.store(plan)
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [100, 100, 200, 100, 100])
        self.assertFalse(wired["refine_only"])
        self.assertTrue(plan.refine["refine_only"])

    def test_ui_refine_only_missing_cache_never_samples(self):
        plan = self.case.build((100,))
        plan.raw["executionMode"] = "refine_only"
        plan.refine["refine_only"] = False
        first, second = [], []
        with self.assertRaisesRegex(ValueError, "缺少一采缓存"):
            self.case.execute(plan, first, second)
        self.assertEqual((first, second), ([], []))

    def test_invalid_ui_intent_or_missing_refine_stops_before_pruning(self):
        for mode, pack in [("refine_only", None), ("refine_only", {"enabled": True, "mode": "latent_upscale"}), ("typo", None)]:
            with self.subTest(mode=mode, pack=pack):
                plan = self.case.build((100,))
                plan.raw["executionMode"] = mode
                plan.refine = pack
                with mock.patch.object(fixture.core, "prune_segment_cache") as prune:
                    with self.assertRaises(ValueError):
                        self.case.execute(plan)
                    prune.assert_not_called()

    def test_absent_ui_mode_retains_old_confirmation_flow(self):
        plan = self.case.build((100,))
        plan.refine.update(refine_only=False, confirm_first_pass=True)
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual((first, second), ([100], []))

    def test_selected_ui_refine_only_validates_only_checked_segments(self):
        plan = self.case.build()
        plan.raw["executionMode"] = "refine_only"
        plan.run_indices = frozenset({2})
        self.case.store(plan, {2})
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual((first, second), ([], [200]))

    def test_external_groups_preserve_execution_mode(self):
        plan = fixture.groups.build_plan_from_external_groups(
            [{"kind": "t2v", "duration_sec": .2, "prompt": "shot"}], family="i2v",
            timeline_data=json.dumps({"executionMode": "first_pass"}), task_type="t2v",
            global_prompt="", total_frames=25, frame_rate=24, width=32, height=32, ref_max_size=32)
        self.assertEqual(plan.raw["executionMode"], "first_pass")

    def test_cache_differences_show_exact_uint64_and_bounded_prompt(self):
        maximum = (1 << 64) - 1
        differences = fixture.cache._cache_difference_values(
            {"seed": 1, "prompt": "old"}, {"seed": maximum, "prompt": "x" * 1000}, ["seed", "prompt"])
        self.assertEqual(differences[0]["current"], str(maximum))
        self.assertLessEqual(len(differences[1]["current"]), 181)

    def test_director_pack_reconstruction_preserves_intent_and_legacy_default(self):
        root = self.case.output
        (root / "asset_groups/01").mkdir(parents=True)
        (root / "asset_groups/01/group.json").write_text(json.dumps({"first_pass_seed": "200", "prompt": "shot"}))
        for task in ("t2v", "r2v", "fl2v"):
            with self.subTest(task=task):
                restored = fixture.pack_module._assemble_timeline(root, {"taskType": task, "executionMode": "refine_only"})
                self.assertEqual(restored["executionMode"], "refine_only")
                self.assertEqual(restored["segments"][0]["first_pass_seed"], "200")
        restored = fixture.pack_module._assemble_timeline(root, {"taskType": "t2v"})
        self.assertEqual(restored["executionMode"], "legacy")


if __name__ == "__main__":
    unittest.main()
