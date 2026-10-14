"""Review regressions: real cache, Refine and HTTP handler with CPU host adapters."""
import ast
import asyncio
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import re
import unittest
from unittest import mock

from aiohttp import web

spec = importlib.util.spec_from_file_location("review_fixture", Path(__file__).with_name("test_segment_seed_refine_only.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
refinement = importlib.import_module(fixture.PKG + ".director.refine_sampling")


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_lora_edit_invalidates_first_and_final_cache(self):
        plan = self.case.build((100,))
        seg = plan.segments[0]
        self.case.store(plan)
        before = fixture.cache.segment_cache_fingerprint(seg, plan)
        seg.loras = [{"name": "character.safetensors", "strength": .75, "active": True}]
        self.assertNotEqual(before, fixture.cache.segment_cache_fingerprint(seg, plan))
        self.assertIn("LoRA", fixture.cache.first_pass_cache_problem("fixture", seg, plan))
        first = mock.Mock()
        with self.assertRaisesRegex(ValueError, "LoRA"):
            self.case.execute(plan, sample_single_stage=first)
        first.assert_not_called()

    def test_lora_file_replacement_and_order_are_part_of_cache_identity(self):
        plan = self.case.build((100,))
        seg = plan.segments[0]
        seg.loras = [{"name": "a", "strength": 1, "active": True}, {"name": "b", "strength": 1, "active": True}]
        path = self.case.output / "a.safetensors"
        path.write_bytes(b"old")
        with mock.patch.object(fixture.cache.folder_paths, "get_full_path", return_value=str(path), create=True):
            before = fixture.cache.first_pass_cache_fingerprint(seg, plan)
            path.write_bytes(b"replacement")
            self.assertNotEqual(before, fixture.cache.first_pass_cache_fingerprint(seg, plan))
            before = fixture.cache.first_pass_cache_fingerprint(seg, plan)
            seg.loras.reverse()
            self.assertNotEqual(before, fixture.cache.first_pass_cache_fingerprint(seg, plan))

    def test_disabled_or_zero_lora_preserves_legacy_identity(self):
        plan = self.case.build((None,))
        seg = plan.segments[0]
        before = fixture.cache.first_pass_cache_fingerprint(seg, plan)
        seg.loras = [{"name": "off", "strength": 1, "active": False}, {"name": "zero", "strength": 0, "active": True}]
        self.assertEqual(before, fixture.cache.first_pass_cache_fingerprint(seg, plan))

    def test_zero_cfg_and_shift_do_not_alias_default_cache_values(self):
        plan = self.case.build((100,))
        before = fixture.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        plan.sample_cfg = plan.sample_shift_video = plan.sample_shift_audio = 0
        after = fixture.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        self.assertEqual([after[k] for k in ("cfg", "shift_video", "shift_audio")], [0, 0, 0])
        self.assertNotEqual(before, after)

    def test_invalid_wired_first_pass_sigmas_stop_before_sampling_or_pruning(self):
        for values in ([float("nan"), 0], [float("inf"), 0], [-1, 0], [1], [1, "bad", 0]):
            with self.subTest(values=values):
                plan = self.case.build((100,))
                first = mock.Mock()
                with mock.patch.object(fixture.core, "prune_segment_cache") as prune:
                    with self.assertRaises(ValueError):
                        # The real executor validates SIGMAS before strict cache validation.
                        with mock.patch.object(fixture.core, "sample_single_stage", first):
                            fixture.core.execute_director_plan_core(plan, node_id="fixture", model=object(),
                                vae=object(), audio_vae=None, clip=object(), sigmas=values)
                first.assert_not_called()
                prune.assert_not_called()

    def test_invalid_second_pass_sigmas_rejected_by_strict_preflight(self):
        plan = self.case.build((100,))
        self.case.store(plan)
        plan.refine["sigmas_tensor"] = fixture.torch.tensor([float("nan"), 0])
        first, second = mock.Mock(), mock.Mock()
        with self.assertRaisesRegex(ValueError, "SIGMAS"):
            self.case.execute(plan, sample_single_stage=first, apply_segment_refine=second)
        first.assert_not_called()
        second.assert_not_called()

    def refine(self, plan, side_effect):
        with mock.patch.object(refinement, "sample_single_stage", side_effect=side_effect):
            return refinement.apply_segment_refine(plan, plan.segments[0],
                samples={"samples": fixture.torch.zeros(1, 2, 1, 2, 2)}, model=object(),
                vae=None, audio_vae=None, positive=[], negative=[], seed=100, cfg=1,
                first_steps=4, sampler_name="euler", scheduler="simple", shift_video=12, shift_audio=3)

    def test_refine_only_sampler_failure_propagates_with_segment_and_cause(self):
        plan = self.case.build((100,))
        with self.assertRaisesRegex(RuntimeError, "第 1 段.*二采失败.*GPU OOM"):
            self.refine(plan, RuntimeError("GPU OOM"))

    def test_refine_only_later_pass_failure_does_not_return_partial_success(self):
        plan = self.case.build((100,))
        plan.refine["passes"] = 2
        good = {"samples": fixture.torch.ones(1, 2, 1, 2, 2)}
        with self.assertRaisesRegex(RuntimeError, "二采失败"):
            self.refine(plan, [good, RuntimeError("second pass failed")])

    def test_legacy_refine_failure_still_returns_first_pass_with_failure_note(self):
        plan = self.case.build((100,))
        plan.refine["refine_only"] = False
        samples, note = self.refine(plan, RuntimeError("legacy failure"))
        self.assertIn("FAILED", note)
        self.assertEqual(samples["samples"].sum(), 0)

    def test_http_cache_inspection_preserves_explicit_zero_sampling_parameters(self):
        # Compile the production handler alone: unrelated video routes need a live host.
        source = (fixture.ROOT / "director/http_routes.py").read_text()
        tree = ast.parse(source)
        handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "minimax_first_pass_cache_status")
        namespace = {"__package__": fixture.PKG + ".director", "web": web, "re": re,
                     "json": json, "log": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), "http_routes.py", "exec"), namespace)
        plan = self.case.build((100,))
        self.case.store(plan)
        body = {"node_id": "56", "timeline_data": json.dumps(plan.raw), "seed": 999,
                "cfg": 0, "steps": 4, "shift_video": 0, "shift_audio": 0}
        request = mock.Mock(json=mock.AsyncMock(return_value=body))
        with mock.patch.object(fixture.cache, "inspect_first_pass_cache", return_value={}) as inspect:
            response = asyncio.run(namespace[handler.name](request))
        self.assertEqual(response.status, 200, response.text)
        inspected_plan = inspect.call_args.args[1]
        self.assertEqual((inspected_plan.sample_cfg, inspected_plan.sample_shift_video, inspected_plan.sample_shift_audio), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
