"""Real CPU caches, FFmpeg and rolling executor; only GPU/host adapters are fixtures."""
import gc
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
import weakref
from unittest import mock

spec = importlib.util.spec_from_file_location("rolling_fixture", Path(__file__).with_name("test_segment_seed_refine_only.py"))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
policy = importlib.import_module(f.PKG + ".director.execution_mode")
roll = importlib.import_module(f.PKG + ".director.rolling")
video = importlib.import_module(f.PKG + ".lib.video_export")
stream = importlib.import_module(f.PKG + ".lib.frame_stream")


class RollingTests(unittest.TestCase):
    def setUp(self):
        self.case = f.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        if not video._ffmpeg_bin():
            self.skipTest("FFmpeg is required for rolling integration")

    def build(self, seeds=(100, 200, 300), mode="first_pass"):
        plan = self.case.build(seeds)
        plan.raw["executionMode"] = mode
        plan.raw["output"]["rollingGeneration"] = True
        return plan

    def execute(self, plan, first=None, second=None, **patches):
        with mock.patch.object(f.core, "cleanup_segment_vram", lambda **kw: None):
            return self.case.execute(plan, first, second, **patches)

    def pixels(self, path, size=32):
        raw = subprocess.check_output([video._ffmpeg_bin(), "-v", "error", "-i", str(path),
            "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        return f.torch.frombuffer(bytearray(raw), dtype=f.torch.uint8).reshape(-1, size, size, 3).float() / 255

    def test_default_off_and_flag_does_not_invalidate_first_cache(self):
        plan = self.case.build((0,))
        before = f.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        self.assertFalse(policy.rolling_enabled(plan))
        plan.raw["output"]["rollingGeneration"] = True
        self.assertTrue(policy.low_memory_enabled(plan))
        self.assertEqual(before, f.cache.first_pass_cache_fingerprint(plan.segments[0], plan))

    def test_twenty_segments_use_one_encoder_bounded_pixels_and_no_rgb_cache(self):
        plan = self.build((100,) * 20)
        refs, counts, encoders, writes = [], [], [], []
        original_writer, original_write = roll.FrameStream, f.cache._write_via_temp
        def writer(*args, **kw):
            encoders.append(1)
            return original_writer(*args, **kw)
        def write(path, callback):
            writes.append(path.name)
            return original_write(path, callback)
        def decode(*args, **kw):
            x = f.torch.zeros(5, 32, 32, 3)
            refs.append(weakref.ref(x))
            return x, None
        def condition(**kw):
            gc.collect()
            counts.append(sum(ref() is not None for ref in refs))
            return [], [], {"samples": f.torch.zeros(1, 2, 1, 2, 2)}, "rolling"
        with mock.patch.object(roll, "FrameStream", writer), mock.patch.object(f.cache, "_write_via_temp", write), \
             mock.patch.object(f.core, "concat_continuous_chunks", side_effect=AssertionError("full concat forbidden")):
            result = self.execute(plan, _decode_av_latent=decode, run_cineStack_conditioning=condition)
        gc.collect()
        self.assertEqual(encoders, [1])
        self.assertLessEqual(max(counts), 1, counts)
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertTrue(all(x.numel() <= 12 for x in result[1]))
        root = Path(plan.segment_mp4_run_dir)
        self.assertEqual(self.pixels(root / "first_pass.mp4").shape[0], 100)
        self.assertFalse(list(root.glob("seg_*.mp4")))
        cache_root = f.cache._cache_dir("fixture")
        self.assertFalse(list(cache_root.glob("*.frames.mkv")))
        self.assertFalse(list(cache_root.glob("seg_????.pt")))
        self.assertEqual(sum(name.endswith(".pre.av.pt") for name in writes), 20)
        self.assertEqual(sum(name.endswith(".av.pt") and not name.endswith(".pre.av.pt") for name in writes), 20)
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual((manifest["mode"], manifest["status"], manifest["pending"]), ("rolling", "completed", []))

    def test_first_to_strict_second_preserves_exact_seeds_and_never_first_samples(self):
        seeds = (0, 200, (1 << 64) - 1)
        self.execute(self.build(seeds))
        plan = self.build(seeds, "refine_only")
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual((first, second), ([], list(seeds)))
        self.assertEqual(self.pixels(Path(plan.segment_mp4_run_dir) / "final.mp4").shape[0], 15)
        plan.segments[1].first_pass_seed = 201
        with mock.patch.object(roll, "FrameStream") as encoder, mock.patch.object(f.core, "prune_segment_cache") as prune:
            with self.assertRaisesRegex(ValueError, "第 2 段"):
                self.execute(plan)
            encoder.assert_not_called()
            prune.assert_not_called()

    def test_confirm_hold_decodes_once_and_no_intermediate_refine_decodes(self):
        plan = self.build((100,), "legacy")
        plan.refine.update(refine_only=False, confirm_first_pass=True)
        calls = []
        def decode(*args, **kw):
            calls.append(1)
            return f.torch.zeros(5, 32, 32, 3), None
        self.execute(plan, _decode_av_latent=decode)
        self.assertEqual(len(calls), 1)
        plan = self.build((100,), "refine_only")
        plan.refine["passes"] = 3
        calls.clear()
        def refine(*args, **kw):
            self.assertIsNone(kw["on_pass"])
            return kw["samples"], "three passes"
        self.execute(plan, apply_segment_refine=refine, _decode_av_latent=decode)
        self.assertEqual(len(calls), 2)  # first-pass comparison + final, no p1/p2 decode
        self.assertFalse(list(Path(plan.segment_mp4_run_dir).glob("*p[123].mp4")))

    def continuity_plan(self, enabled=True):
        plan = self.build()
        plan.raw["output"]["rollingGeneration"] = enabled
        plan.continuity_enabled = True
        plan.continuity_overlap_frames = 22
        plan.width = plan.height = 96
        for seg in plan.segments:
            seg.continuity_from_prev = seg.index > 0
            seg.start_frame, seg.end_frame = seg.index * 39, (seg.index + 1) * 39
        return plan

    def continuity_run(self, plan):
        pins, colors = [], iter((.15, .25, .35, .45) * 10)
        def condition(**kw):
            return [], [], {"samples": f.torch.zeros(1, 2, kw["length"], 2, 2)}, "continuity"
        def decode(samples, *args, **kw):
            data = samples["samples"]
            if isinstance(data, (tuple, list)):
                data = data[0]
            length = data.shape[2] if data.ndim == 5 else data.shape[1]
            return f.torch.full((length, 96, 96, 3), next(colors)), None
        def pin(positive, latent, **kw):
            pins.append(int(kw["context_frames"].shape[0]))
            return positive, 22, 1
        with mock.patch.object(f.core, "apply_motion_context", pin), \
             mock.patch.object(f.core, "select_continuity_pin_latent", lambda current, first, final: first if first is not None else final), \
             mock.patch.object(f.core, "describe_pin_window", lambda *a, **kw: "pin test"):
            result = self.execute(plan, run_cineStack_conditioning=condition, _decode_av_latent=decode)
        return result, pins

    def test_continuity_waits_for_phase_trim_before_encoding_and_matches_legacy(self):
        legacy, _ = self.continuity_run(self.continuity_plan(False))
        plan = self.continuity_plan()
        result, pins = self.continuity_run(plan)
        self.assertEqual(pins, [39, 51])
        self.assertEqual(result[4], [38, 50, 51])
        pixels = self.pixels(Path(plan.segment_mp4_run_dir) / "first_pass.mp4", 96)
        self.assertEqual(pixels.shape, legacy[0].shape)
        self.assertLess((pixels - legacy[0]).abs().max().item(), .035)
        meta = json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())
        self.assertEqual([e["first"]["frames"] for e in meta["segments"]], [38, 50, 51])

    def test_partial_run_reconstructs_only_predecessor_from_av(self):
        self.continuity_run(self.continuity_plan())
        plan = self.continuity_plan()
        plan.run_indices = frozenset({1})
        result, pins = self.continuity_run(plan)
        self.assertEqual(len(result[4]), 1)
        self.assertEqual(pins, [38])
        meta = json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())
        self.assertEqual([e["segment"] for e in meta["segments"]], [2])

    def test_strict_second_keeps_first_pass_phase_cuts(self):
        first, _ = self.continuity_run(self.continuity_plan())
        plan = self.continuity_plan()
        plan.raw["executionMode"] = "refine_only"
        second, pins = self.continuity_run(plan)
        self.assertEqual(pins, [])
        self.assertEqual(second[4], first[4])

    def test_stream_audio_handles_missing_track_resample_and_exact_frames(self):
        writer = stream.FrameStream(self.case.output, "audio", width=32, height=32, fps=24)
        writer.append(f.torch.zeros(5, 32, 32, 3), None)
        writer.append(f.torch.ones(5, 32, 32, 3), {"sample_rate": 44100, "waveform": f.torch.zeros(1, 1, 12000)})
        writer.append(f.torch.zeros(5, 32, 32, 3), {"sample_rate": 48000, "waveform": f.torch.zeros(1, 2, 12000)})
        self.assertEqual(writer.audio_samples, 30000)
        dest = writer.finish()
        self.assertEqual(self.pixels(dest).shape[0], 15)
        output = subprocess.run([video._ffmpeg_bin(), "-i", str(dest)], stderr=subprocess.PIPE)
        self.assertIn(b"Audio:", output.stderr)

    def test_encoder_failure_closes_process_preserves_latents_and_marks_interrupted(self):
        plan = self.build()
        original = roll.FrameStream
        instances = []
        class Failing(original):
            def append(self, frames, audio=None):
                instances.append(self)
                raise OSError("disk full")
        with mock.patch.object(roll, "FrameStream", Failing):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.execute(plan)
        self.assertTrue(all(writer.proc.poll() is not None for writer in instances))
        self.assertFalse(hasattr(plan, "_active_rolling_run"))
        for seg in plan.segments[:2]:
            self.assertIsNone(f.cache.first_pass_cache_problem("fixture", seg, plan))
        meta = json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())
        self.assertEqual(meta["status"], "interrupted")

    def test_external_group_and_pack_preserve_rolling(self):
        plan = f.groups.build_plan_from_external_groups(
            [{"kind": "t2v", "duration_sec": .2, "prompt": "shot"}], family="i2v",
            timeline_data=json.dumps({"output": {"rollingGeneration": True}}), task_type="t2v",
            global_prompt="", total_frames=25, frame_rate=24, width=32, height=32, ref_max_size=32)
        self.assertTrue(policy.rolling_enabled(plan))
        restored = f.pack_module._assemble_timeline(self.case.output, {"taskType": "t2v", "output": {"rollingGeneration": True}})
        self.assertTrue(restored["output"]["rollingGeneration"])

    def test_unrefined_first_and_final_share_encoding(self):
        plan = self.build((100, 200), "legacy")
        plan.refine = {"enabled": False}
        self.execute(plan)
        root = Path(plan.segment_mp4_run_dir)
        self.assertEqual((root / "first_pass.mp4").read_bytes(), (root / "final.mp4").read_bytes())

    def test_geometry_change_uses_bounded_parts_and_pads_on_merge(self):
        plan = self.build((100, 200))
        shapes = iter(((32, 32), (64, 64)))
        def decode(*args, **kw):
            h, w = next(shapes)
            return f.torch.zeros(5, h, w, 3), None
        self.execute(plan, _decode_av_latent=decode)
        frames = self.pixels(Path(plan.segment_mp4_run_dir) / "first_pass.mp4", 64)
        self.assertEqual(frames.shape, (10, 64, 64, 3))

    def test_mixed_confirmation_stages_are_labeled_partial_not_mixed(self):
        plan = self.build((100, 200), "legacy")
        plan.refine.update(refine_only=False, confirm_first_pass=True)
        self.case.store(plan, {0})
        self.execute(plan)
        root = Path(plan.segment_mp4_run_dir)
        self.assertTrue((root / "first_pass.mp4").exists())
        self.assertFalse((root / "final.mp4").exists())
        self.assertTrue((root / "final.partial.mp4").exists())
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertFalse(manifest["merged"]["final"]["complete"])

    def test_decode_oom_keeps_first_av_and_does_not_start_encoder(self):
        plan = self.build()
        with mock.patch.object(roll, "FrameStream") as encoder:
            with self.assertRaisesRegex(RuntimeError, "decode OOM"):
                self.execute(plan, _decode_av_latent=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("decode OOM")))
            encoder.assert_not_called()
        self.assertIsNone(f.cache.first_pass_cache_problem("fixture", plan.segments[0], plan))


if __name__ == "__main__":
    unittest.main()
