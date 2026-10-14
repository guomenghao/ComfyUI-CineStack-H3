"""Disk mode integration: real CPU caches/codecs; GPU/Comfy adapters are fixtures."""
import ast
import gc
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
import weakref
from unittest import mock

spec = importlib.util.spec_from_file_location("low_memory_fixture", Path(__file__).with_name("test_segment_seed_refine_only.py"))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
disk = importlib.import_module(f.PKG + ".director.low_memory")
video = importlib.import_module(f.PKG + ".lib.video_export")
policy = importlib.import_module(f.PKG + ".director.execution_mode")


class LowMemoryTests(unittest.TestCase):
    def setUp(self):
        self.case = f.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def build(self, seeds=(100, 100, 200, 100, 100), mode="first_pass"):
        plan = self.case.build(seeds)
        plan.raw["output"]["lowMemoryMode"] = True
        plan.raw["executionMode"] = mode
        return plan

    def execute(self, plan, first=None, second=None, **patches):
        with mock.patch.object(f.core, "cleanup_segment_vram", lambda **kw: None):
            return self.case.execute(plan, first, second, **patches)

    def require_codec(self):
        if not video._ffmpeg_bin():
            self.skipTest("Install imageio-ffmpeg or FFmpeg for disk media integration")

    def test_legacy_default_and_low_mode_do_not_change_first_pass_cache_identity(self):
        plan = self.case.build((0,))
        before = f.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        self.assertFalse(policy.low_memory_enabled(plan))
        plan.raw["output"]["lowMemoryMode"] = True
        self.assertTrue(policy.low_memory_enabled(plan))
        self.assertEqual(before, f.cache.first_pass_cache_fingerprint(plan.segments[0], plan))

    def test_missing_ffmpeg_stops_before_sampling_or_pruning(self):
        plan = self.build((100,))
        first = mock.Mock()
        with mock.patch.object(disk, "_ffmpeg_bin", return_value=None), mock.patch.object(f.core, "prune_segment_cache") as prune:
            with self.assertRaisesRegex(RuntimeError, "FFmpeg"):
                self.execute(plan, sample_single_stage=first)
            prune.assert_not_called()
            first.assert_not_called()

    def test_new_latent_without_pixels_drops_stale_seed_preview(self):
        plan = self.case.build((100,))
        seg = plan.segments[0]
        f.cache.save_first_pass_cache("fixture", seg, plan, av_latent={"samples": f.torch.zeros(1, 2, 1, 2, 2)},
                                      frames=f.torch.ones(5, 32, 32, 3))
        seg.first_pass_seed = 200
        f.cache.save_first_pass_cache("fixture", seg, plan, av_latent={"samples": f.torch.zeros(1, 2, 1, 2, 2)})
        self.assertIsNone(f.cache.load_first_pass_cache("fixture", seg, plan).get("frames"))

    def test_bounded_cache_conversion_is_pixel_exact(self):
        frames = f.torch.rand(11, 32, 32, 3) * 1.5 - .25
        self.assertTrue(f.torch.equal(f.cache._frames_to_disk(frames), f.cache._frames_to_disk(frames, bounded=True)))

    def test_low_cache_write_failure_raises_but_legacy_remains_best_effort(self):
        for enabled in (False, True):
            plan = self.case.build((100,))
            plan.raw["output"]["lowMemoryMode"] = enabled
            with mock.patch.object(f.cache, "_write_via_temp", side_effect=OSError("disk full")):
                if enabled:
                    with self.assertRaisesRegex(RuntimeError, "disk full"):
                        f.cache.save_first_pass_cache("fixture", plan.segments[0], plan,
                            av_latent={"samples": f.torch.zeros(1, 2, 1, 2, 2)})
                else:
                    self.case.store(plan)

    def test_first_pass_single_decode_fixed_seeds_and_durable_video(self):
        self.require_codec()
        plan = self.build((0, 200, (1 << 64) - 1))
        calls = []
        def decode(*args, **kwargs):
            calls.append(1)
            return f.torch.zeros(5, 32, 32, 3), None
        first = []
        with mock.patch.object(f.core, "concat_continuous_chunks", side_effect=AssertionError("Whole-timeline concat forbidden")):
            result = self.execute(plan, first, _decode_av_latent=decode)
        self.assertEqual(first, [0, 200, (1 << 64) - 1])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(t.numel() <= 12 for t in result[1]))
        root = Path(plan.segment_mp4_run_dir)
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual([e["first_pass_seed"] for e in manifest["segments"]], ["0", "200", "18446744073709551615"])
        self.assertTrue((root / "first_pass.mp4").is_file())
        self.assertFalse((root / "final.mp4").exists())
        for seg in plan.segments:
            self.assertIsNone(f.cache.first_pass_cache_problem("fixture", seg, plan))

    def test_legacy_confirmation_hold_decodes_once_in_low_mode(self):
        self.require_codec()
        plan = self.build((100, 200), mode="legacy")
        plan.refine.update(refine_only=False, confirm_first_pass=True)
        calls = []
        def decode(*a, **kw):
            calls.append(1)
            return f.torch.zeros(5, 32, 32, 3), None
        result = self.execute(plan, _decode_av_latent=decode)
        self.assertTrue(result[7])
        self.assertEqual(len(calls), 2)
        self.assertTrue((Path(plan.segment_mp4_run_dir) / "first_pass.mp4").is_file())

    def test_low_first_cache_can_be_used_by_strict_second_without_first_sampling(self):
        self.require_codec()
        self.execute(self.build((100, 200)))
        plan = self.build((100, 200), "refine_only")
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual((first, second), ([], [100, 200]))
        self.assertTrue((Path(plan.segment_mp4_run_dir) / "final.mp4").is_file())
        plan.segments[1].first_pass_seed = 201
        with mock.patch.object(f.core, "prune_segment_cache") as prune:
            with self.assertRaisesRegex(ValueError, "第 2 段"):
                self.execute(plan)
            prune.assert_not_called()

    def test_partial_run_only_exports_selected_and_preserves_exact_seed(self):
        self.require_codec()
        plan = self.build()
        plan.run_indices = frozenset({2})
        first = []
        self.execute(plan, first)
        self.assertEqual(first, [200])
        entries = json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())["segments"]
        self.assertEqual([e["segment"] for e in entries], [3])

    def test_full_frame_storage_is_bounded_across_many_segments(self):
        self.require_codec()
        plan = self.build((100,) * 12)
        references, counts = [], []
        def decode(*a, **kw):
            tensor = f.torch.zeros(5, 32, 32, 3)
            references.append(weakref.ref(tensor))
            return tensor, None
        def conditioning(**kw):
            gc.collect()
            counts.append(sum(ref() is not None for ref in references))
            return [], [], {"samples": f.torch.zeros(1, 2, 1, 2, 2)}, "memory test"
        # Plain callables are intentional: Mock histories would retain IMAGE arguments.
        result = self.execute(plan, _decode_av_latent=decode, run_cineStack_conditioning=conditioning)
        gc.collect()
        self.assertLessEqual(max(counts), 1, counts)
        self.assertTrue(all(ref() is None for ref in references))
        self.assertLessEqual(sum(t.untyped_storage().nbytes() for t in result[1]), 12 * 48)

    def test_frame_streaming_never_converts_entire_clip_and_has_audio(self):
        self.require_codec()
        batches = []
        convert = video._frames_to_rgb_u8
        def checked(frames):
            batches.append(int(frames.shape[0]))
            return convert(frames)
        dest = self.case.output / "stream.mp4"
        with mock.patch.object(video, "_frames_to_rgb_u8", checked):
            video.write_frames_to_mp4(dest, f.torch.zeros(7, 33, 35, 3), fps=24,
                audio={"sample_rate": 48000, "waveform": f.torch.zeros(1, 2, 14000)}, stream=True)
        self.assertEqual(batches, [1] * 7)
        self.assertTrue(disk._has_audio(dest))

    def test_streaming_merge_normalizes_geometry_and_missing_audio(self):
        self.require_codec()
        first, second = self.case.output / "a.mp4", self.case.output / "b.mp4"
        video.write_frames_to_mp4(first, f.torch.zeros(5, 32, 32, 3), fps=24, stream=True,
            audio={"sample_rate": 48000, "waveform": f.torch.zeros(1, 2, 10000)})
        video.write_frames_to_mp4(second, f.torch.ones(7, 34, 16, 3), fps=24, stream=True)
        dest = self.case.output / "merged.mp4"
        disk.merge_disk_clips([{"path": str(first), "frames": 5, "width": 32, "height": 32},
                               {"path": str(second), "frames": 7, "width": 16, "height": 34}], dest, 24)
        self.assertTrue(disk._has_audio(dest))
        pixels = subprocess.check_output([video._ffmpeg_bin(), "-v", "error", "-i", str(dest),
                                          "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        self.assertEqual(len(pixels), 12 * 32 * 34 * 3)

    def test_video_write_failure_stops_after_one_sample_and_keeps_first_latent(self):
        self.require_codec()
        plan = self.build((100, 200))
        first = []
        with mock.patch.object(video, "write_frames_to_mp4", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "第 1 段.*disk full"):
                self.execute(plan, first)
        self.assertEqual(first, [100])
        self.assertIsNone(f.cache.first_pass_cache_problem("fixture", plan.segments[0], plan))
        self.assertFalse((Path(plan.segment_mp4_run_dir) / "first_pass.mp4").exists())

    def test_decode_failure_keeps_successful_first_latent_on_disk(self):
        self.require_codec()
        plan = self.build((100, 200))
        first = []
        def fail_decode(*args, **kwargs):
            raise RuntimeError("decode OOM")
        with self.assertRaisesRegex(RuntimeError, "decode OOM"):
            self.execute(plan, first, _decode_av_latent=fail_decode)
        self.assertEqual(first, [100])
        self.assertIsNone(f.cache.first_pass_cache_problem("fixture", plan.segments[0], plan))

    def test_continuity_consumes_full_predecessor_before_release_and_rewrites_trim(self):
        self.require_codec()
        plan = self.build((100, 200, 300))
        plan.continuity_enabled = True
        plan.width = plan.height = 96
        plan.continuity_overlap_frames = 22
        for seg in plan.segments:
            seg.continuity_from_prev = seg.index > 0
            seg.start_frame = seg.index * 39
            seg.end_frame = (seg.index + 1) * 39
        pin_lengths = []
        def condition(**kw):
            return [], [], {"samples": f.torch.zeros(1, 2, kw["length"], 2, 2)}, "continuity"
        def decode(samples, *args, **kw):
            return f.torch.zeros(samples["samples"].shape[2], 96, 96, 3), None
        def pin(positive, latent, **kw):
            pin_lengths.append(int(kw["context_frames"].shape[0]))
            self.assertGreaterEqual(pin_lengths[-1], 22)
            return positive, 22, 1
        with mock.patch.object(f.core, "apply_motion_context", pin), \
             mock.patch.object(f.core, "select_continuity_pin_latent", lambda current, first, final: first if first is not None else final), \
             mock.patch.object(f.core, "describe_pin_window", lambda *args, **kw: "test pin"):
            result = self.execute(plan, run_cineStack_conditioning=condition, _decode_av_latent=decode)
        self.assertEqual(pin_lengths, [39, 51])
        self.assertEqual(result[4], [38, 50, 51])
        entries = json.loads((Path(plan.segment_mp4_run_dir) / "manifest.json").read_text())["segments"]
        self.assertEqual([e["first"]["frames"] for e in entries], [38, 50, 51])

    def test_disk_merge_preserves_legacy_continuity_seam_pixels_and_frame_count(self):
        self.require_codec()
        def run(enabled):
            plan = self.build((100, 200, 300))
            plan.raw["output"]["lowMemoryMode"] = enabled
            plan.continuity_enabled = True
            plan.continuity_overlap_frames = 22
            plan.width = plan.height = 96
            for seg in plan.segments:
                seg.start_frame, seg.end_frame = seg.index * 39, (seg.index + 1) * 39
                seg.continuity_from_prev = seg.index > 0
            color = iter((.15, .25, .35))
            def condition(**kw):
                return [], [], {"samples": f.torch.zeros(1, 2, kw["length"], 2, 2)}, "continuity"
            def decode(samples, *args, **kw):
                return f.torch.full((samples["samples"].shape[2], 96, 96, 3), next(color)), None
            with mock.patch.object(f.core, "apply_motion_context", lambda positive, latent, **kw: (positive, 22, 1)), \
                 mock.patch.object(f.core, "select_continuity_pin_latent", lambda current, first, final: first if first is not None else final), \
                 mock.patch.object(f.core, "describe_pin_window", lambda *a, **kw: "test pin"):
                result = self.execute(plan, run_cineStack_conditioning=condition, _decode_av_latent=decode)
            return plan, result
        _, legacy = run(False)
        plan, low = run(True)
        raw = subprocess.check_output([video._ffmpeg_bin(), "-v", "error", "-i",
            str(Path(plan.segment_mp4_run_dir) / "first_pass.mp4"), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        decoded = f.torch.frombuffer(bytearray(raw), dtype=f.torch.uint8).reshape(-1, 96, 96, 3).float() / 255
        self.assertEqual(low[4], legacy[4])
        self.assertEqual(decoded.shape, legacy[0].shape)
        self.assertLess((decoded - legacy[0]).abs().max().item(), .035)

    def test_intermediate_refine_passes_flush_without_retaining_full_frames(self):
        self.require_codec()
        self.execute(self.build((100,)))
        plan = self.build((100,), "refine_only")
        plan.refine["passes"] = 3
        references = []
        def decode(*args, **kw):
            tensor = f.torch.zeros(5, 32, 32, 3)
            references.append(weakref.ref(tensor))
            return tensor, None
        def refine(*args, **kw):
            kw["on_pass"](1, 3, kw["samples"])
            kw["on_pass"](2, 3, kw["samples"])
            self.assertIsNone(references[-2]())
            self.assertIsNone(references[-1]())
            return kw["samples"], "three passes"
        self.execute(plan, _decode_av_latent=decode, apply_segment_refine=refine)
        root = Path(plan.segment_mp4_run_dir)
        self.assertTrue(all((root / f"seg_0000_p{i}.mp4").is_file() for i in (1, 2, 3)))

    def test_last_refine_alias_tracks_predecessor_seam_rewrite(self):
        self.require_codec()
        first_plan = self.build((100, 200))
        first_plan.continuity_enabled = True
        for seg in first_plan.segments:
            seg.continuity_from_prev = False
        self.execute(first_plan)
        plan = self.build((100, 200), "refine_only")
        plan.refine["passes"] = 3
        plan.continuity_enabled = True
        for seg in plan.segments:
            seg.continuity_from_prev = False
        def refine(*args, **kw):
            kw["on_pass"](1, 3, kw["samples"])
            kw["on_pass"](2, 3, kw["samples"])
            return kw["samples"], "three passes"
        # Force a visible predecessor correction to test file-alias coordination;
        # the real seam algorithm is compared against legacy output separately.
        with mock.patch.object(f.core, "prepare_export_seam", lambda left, right: (left + .2, right)):
            self.execute(plan, apply_segment_refine=refine)
        root = Path(plan.segment_mp4_run_dir)
        self.assertEqual((root / "seg_0000_p3.mp4").read_bytes(), (root / "seg_0000.mp4").read_bytes())

    def test_external_group_and_pack_preserve_low_memory_flag(self):
        plan = f.groups.build_plan_from_external_groups(
            [{"kind": "t2v", "duration_sec": .2, "prompt": "shot"}], family="i2v",
            timeline_data=json.dumps({"output": {"lowMemoryMode": True}}), task_type="t2v",
            global_prompt="", total_frames=25, frame_rate=24, width=32, height=32, ref_max_size=32)
        self.assertTrue(policy.low_memory_enabled(plan))
        restored = f.pack_module._assemble_timeline(self.case.output, {"taskType": "t2v", "output": {"lowMemoryMode": True}})
        self.assertTrue(restored["output"]["lowMemoryMode"])

    def test_low_finalize_blocks_media_without_running_legacy_materialization(self):
        source = (f.ROOT / "nodes/director_common.py").read_text()
        fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "finalize_director_outputs")
        class Blocker:
            def __init__(self, value): self.value = value
        env = {"__package__": f.PKG + ".nodes", "ExecutionBlocker": Blocker}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "director_common.py", "exec"), env)
        result = env[fn.name](self.build(), None, [], "disk report", segment_frame_counts=[5, 22])
        self.assertTrue(all(isinstance(result[i], Blocker) for i in (0, 1, 4, 6, 7)))
        self.assertEqual(result[3], 27)


if __name__ == "__main__":
    unittest.main()
