"""Real disk-video composition; only model inference uses CPU fixtures."""
import importlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import test_rolling as r

f = r.f
store_module = importlib.import_module(f.PKG + ".director.rolling_store")


class RollingFullExportTests(unittest.TestCase):
    def setUp(self):
        self.runner = r.RollingTests()
        self.runner.setUp()
        self.addCleanup(self.runner.doCleanups)
        self.execute = self.runner.execute
        self.pixels = self.runner.pixels

    def build(self, seeds=(100, 200, 300, 400, 500), mode="first_pass", selected=None):
        plan = self.runner.build(seeds, mode)
        plan.export_mode = "all"
        plan.raw["output"]["exportMode"] = "all"
        plan.run_indices = None if selected is None else frozenset(selected)
        return plan

    def test_ambiguous_legacy_stage_has_actionable_error_before_sampling(self):
        plan = self.build(mode="legacy")
        plan.refine.update(enabled=True, confirm_first_pass=True, refine_only=False)
        first, second = [], []
        with self.assertRaisesRegex(ValueError, "分段工作台 → 执行方式") as error:
            self.execute(plan, first, second)
        self.assertIn("无需关闭滚动生成", str(error.exception))
        self.assertEqual((first, second), ([], []))
        self.assertFalse(self.index().exists())

    def paint(self, values):
        values = iter(values)
        return lambda *a, **kw: (f.torch.full((5, 32, 32, 3), next(values)), None)

    def manifest(self, plan):
        return json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())

    def index(self):
        return f.cache._cache_dir("fixture") / "rolling_videos.json"

    def test_replace_one_keeps_other_video_ranges_and_only_samples_selected_seed(self):
        base = self.build()
        self.execute(base, _decode_av_latent=self.paint([.1, .2, .3, .4, .5]))
        previous = Path(base.segment_mp4_run_dir) / "timeline_first_pass.mp4"
        original = previous.read_bytes()
        old_frames = self.pixels(previous)
        av_before = {p.name: p.read_bytes() for p in f.cache._cache_dir("fixture").glob("*.av.pt")
                     if "0002" not in p.name}
        plan = self.build((100, 200, 909, 400, 500), selected={2})
        first, second = [], []
        with mock.patch.object(f.core, "concat_continuous_chunks", side_effect=AssertionError("no whole IMAGE concat")):
            result = self.execute(plan, first, second, _decode_av_latent=self.paint([.8]))
        self.assertEqual((first, second), ([909], []))
        self.assertEqual(result[4], [5] * 5)
        self.assertEqual(previous.read_bytes(), original)
        for name, content in av_before.items():
            self.assertEqual((f.cache._cache_dir("fixture") / name).read_bytes(), content)
        output = self.pixels(Path(plan.segment_mp4_run_dir) / "timeline_first_pass.mp4")
        self.assertEqual(output.shape[0], 25)
        self.assertLess((output[:10] - old_frames[:10]).abs().max().item(), .035)
        self.assertLess((output[15:] - old_frames[15:]).abs().max().item(), .035)
        self.assertGreater(output[10:15].mean().item(), .75)
        full = self.manifest(plan)["full_export"]
        self.assertEqual([e["reused"] for e in full["segments"]], [True, True, False, True, True])
        self.assertEqual([e["first"]["start_frame"] for e in full["segments"]], [0, 5, 10, 15, 20])

    def test_segment_export_then_full_export_preserves_previous_partial_replacement(self):
        self.execute(self.build(), _decode_av_latent=self.paint([.1] * 5))
        partial = self.runner.build((100, 200, 700, 400, 500))
        partial.run_indices = frozenset({2})
        result = self.execute(partial, _decode_av_latent=self.paint([.7]))
        self.assertEqual(result[4], [5])
        self.assertIsNone(self.manifest(partial)["full_export"])
        plan = self.build((100, 200, 700, 400, 900), selected={4})
        first = []
        self.execute(plan, first, _decode_av_latent=self.paint([.9]))
        self.assertEqual(first, [900])
        pixels = self.pixels(Path(plan.segment_mp4_run_dir) / "timeline_first_pass.mp4")
        self.assertGreater(pixels[10:15].mean().item(), .65)
        self.assertGreater(pixels[20:].mean().item(), .85)

    def test_strict_second_reuses_unselected_final_without_loading_their_latents(self):
        self.execute(self.build())
        self.execute(self.build(mode="refine_only"))
        for path in f.cache._cache_dir("fixture").glob("*.av.pt"):
            if "0002" not in path.name:
                path.unlink()
        first, second = [], []
        plan = self.build(mode="refine_only", selected={2})
        self.execute(plan, first, second)
        self.assertEqual((first, second), ([], [300]))
        self.assertEqual(self.pixels(Path(plan.segment_mp4_run_dir) / "timeline_final.mp4").shape[0], 25)

    def test_missing_or_wrong_stage_rejects_before_sampling_and_cache_pruning(self):
        for mode in ("first_pass", "refine_only"):
            plan = self.build(mode=mode, selected={2})
            if mode == "refine_only":
                self.execute(self.build())  # First results may not masquerade as final.
            first, second = [], []
            with mock.patch.object(f.core, "prune_segment_cache") as prune:
                with self.assertRaisesRegex(ValueError, "第 1 段.*缺少"):
                    self.execute(plan, first, second)
                prune.assert_not_called()
            self.assertEqual((first, second), ([], []))

    def test_missing_modified_and_mismatched_results_stop_before_sampling(self):
        base = self.build()
        self.execute(base)
        plan = self.build(selected={2})
        index = json.loads(self.index().read_text())
        clip = Path(index["segments"]["0"]["first"]["path"])
        original = clip.read_bytes()
        saved_stat = clip.stat()
        clip.unlink()
        first = []
        with self.assertRaisesRegex(ValueError, "第 1 段.*缺失"):
            self.execute(plan, first)
        clip.write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "第 1 段.*修改"):
            self.execute(plan, first)
        import os
        clip.write_bytes(original)
        os.utime(clip, ns=(saved_stat.st_atime_ns, saved_stat.st_mtime_ns))
        plan.segments[0].first_pass_seed = 999
        with self.assertRaisesRegex(ValueError, "第 1 段.*seed"):
            self.execute(plan, first)
        self.assertEqual(first, [])

    def test_explicit_old_manifest_import_never_resamples_other_segments(self):
        base = self.runner.build()
        self.execute(base)
        path = Path(base.segment_mp4_run_dir) / "manifest.json"
        old = json.loads(path.read_text())
        old.pop("full_export", None)
        for row in old["segments"]:
            row.pop("identity", None)  # Actual 0.4.x format has no identity.
        path.write_text(json.dumps(old))
        self.index().unlink()
        plan = self.build((100, 200, 909), selected={2})
        plan.raw["output"]["rollingBaseManifest"] = str(path)
        first = []
        self.execute(plan, first)
        self.assertEqual(first, [909])
        self.assertEqual(self.manifest(plan)["full_export"]["frames"], 15)

    def test_failed_composition_keeps_previous_index_and_marks_run_interrupted(self):
        self.execute(self.build())
        before = self.index().read_bytes()
        plan = self.build(selected={2})
        with mock.patch.object(store_module, "compose_ranges", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.execute(plan)
        self.assertEqual(before, self.index().read_bytes())
        self.assertEqual(self.manifest(plan)["status"], "interrupted")
        self.assertTrue((Path(plan.segment_mp4_run_dir) / "first_pass.mp4").exists())

    def test_unselected_continuity_predecessor_handoff_and_video_remain_unchanged(self):
        base = self.runner.continuity_plan()
        base.export_mode = "all"
        self.runner.continuity_run(base)
        path = f.cache._cache_dir("fixture") / "seg_0000.handoff.json"
        before = path.read_bytes()
        plan = self.runner.continuity_plan()
        plan.export_mode = "all"
        plan.run_indices = frozenset({1})
        result, pins = self.runner.continuity_run(plan)
        self.assertEqual(len(pins), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(result[4]), 3)
        full = self.manifest(plan)["full_export"]
        self.assertEqual(full["segments"][0]["first"]["frames"], 38)

    def test_twenty_segments_replace_one_without_python_decoding_old_videos(self):
        self.execute(self.build((100,) * 20))
        first, decodes = [], []
        plan = self.build((100,) * 20, selected={10})
        def decode(*args, **kwargs):
            decodes.append(1)
            return f.torch.zeros(5, 32, 32, 3), None
        self.execute(plan, first, _decode_av_latent=decode)
        self.assertEqual((first, decodes), ([100], [1]))
        self.assertEqual(self.manifest(plan)["full_export"]["frames"], 100)

    def test_audio_is_preserved_across_saved_and_replaced_ranges(self):
        def decode(value):
            return lambda *a, **kw: (f.torch.zeros(5, 32, 32, 3),
                {"sample_rate": 48000, "waveform": f.torch.full((1, 2, 10000), value)})
        base = self.build((100, 200, 300))
        base.raw["output"]["audioMode"] = "generate"
        self.execute(base, _decode_av_latent=decode(.1))
        plan = self.build((100, 200, 300), selected={1})
        plan.raw["output"]["audioMode"] = "generate"
        self.execute(plan, _decode_av_latent=decode(.5))
        path = Path(plan.segment_mp4_run_dir) / "timeline_first_pass.mp4"
        pcm = subprocess.check_output([r.video._ffmpeg_bin(), "-v", "error", "-i", str(path),
            "-map", "0:a:0", "-ar", "48000", "-ac", "2", "-f", "f32le", "-"])
        audio = f.torch.frombuffer(bytearray(pcm), dtype=f.torch.float32).reshape(-1, 2)
        self.assertGreaterEqual(len(audio), 30000)
        self.assertLess(len(audio), 32000)  # AAC padding is outside intended timeline.
        for start, value in ((2000, .1), (12000, .5), (22000, .1)):
            self.assertAlmostEqual(audio[start:start+2000].mean().item(), value, delta=.04)

    def test_saved_geometry_change_and_replacement_normalize_without_full_tensor(self):
        base = self.build((100, 200, 300))
        shapes = iter((32, 64, 32))
        def decode(*a, **kw):
            n = next(shapes)
            return f.torch.zeros(5, n, n, 3), None
        self.execute(base, _decode_av_latent=decode)
        plan = self.build((100, 200, 300), selected={1})
        self.execute(plan)
        output = self.pixels(Path(plan.segment_mp4_run_dir) / "timeline_first_pass.mp4", 64)
        self.assertEqual(output.shape, (15, 64, 64, 3))

    def test_video_removed_during_sampling_leaves_catalog_unchanged(self):
        self.execute(self.build())
        before = self.index().read_bytes()
        previous = json.loads(before)["segments"]["0"]["first"]["path"]
        def decode(*a, **kw):
            Path(previous).unlink(missing_ok=True)
            return f.torch.zeros(5, 32, 32, 3), None
        plan = self.build(selected={2})
        with self.assertRaisesRegex(ValueError, "第 1 段.*缺失"):
            self.execute(plan, _decode_av_latent=decode)
        self.assertEqual(self.index().read_bytes(), before)
        self.assertEqual(self.manifest(plan)["status"], "interrupted")

    def test_incomplete_legacy_manifest_refused_without_sampling(self):
        base = self.runner.build()
        base.run_indices = frozenset({0})
        self.execute(base)
        self.index().unlink()
        plan = self.build((100, 200, 300), selected={1})
        plan.raw["output"]["rollingBaseManifest"] = str(Path(base.segment_mp4_run_dir) / "manifest.json")
        first = []
        with self.assertRaisesRegex(ValueError, "未覆盖当前完整时间轴"):
            self.execute(plan, first)
        self.assertEqual(first, [])

    def test_external_groups_keep_full_timeline_scope_and_import_path(self):
        groups = [{"kind": "t2v", "duration_sec": .2, "prompt": f"shot{i}"} for i in range(3)]
        plan = f.groups.build_plan_from_external_groups(groups, family="i2v",
            timeline_data=json.dumps({"runSelectEnabled": True, "runSelection": [1],
                "output": {"exportMode": "all", "rollingGeneration": True, "rollingBaseManifest": "old/manifest.json"}}),
            task_type="t2v", global_prompt="", total_frames=15, frame_rate=24, width=32, height=32, ref_max_size=32)
        self.assertEqual(plan.export_mode, "all")
        self.assertEqual(len(plan.segments), 3)
        self.assertEqual(plan.run_indices, frozenset({1}))
        self.assertEqual(plan.raw["output"]["rollingBaseManifest"], "old/manifest.json")


if __name__ == "__main__":
    unittest.main()
