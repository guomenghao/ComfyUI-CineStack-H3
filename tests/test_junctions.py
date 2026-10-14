"""Connected-boundary executor regressions; CPU/real disk and FFmpeg, GPU adapters mocked."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

import test_rolling as r

f = r.f
j = f.core.junctions
h3 = importlib.import_module(f.PKG + ".director.h3_motion_context")
patches = importlib.import_module(f.PKG + ".director.h3_context_patches")
refine = importlib.import_module(f.PKG + ".director.refine_sampling")


class JunctionTests(unittest.TestCase):
    def setUp(self):
        self.runner = r.RollingTests()
        self.runner.setUp()
        self.addCleanup(self.runner.doCleanups)

    def plan(self, selected=None, mode="first_pass", count=3):
        p = self.runner.continuity_plan()
        if count != 3:
            p = self.runner.build(tuple(range(100, 100 + count)))
            p.width = p.height = 96
            p.continuity_enabled, p.continuity_overlap_frames = True, 22
            for seg in p.segments:
                seg.start_frame, seg.end_frame = seg.index * 39, (seg.index + 1) * 39
                seg.continuity_from_prev = seg.index > 0
        p.raw["executionMode"] = mode
        p.run_indices = None if selected is None else frozenset(selected)
        return p

    def run_plan(self, p, first=None, second=None):
        tails, ends, refined = [], [], []
        def condition(**kw):
            return [], [], {"samples": f.torch.zeros(1, 2, kw["length"], 2, 2)}, "junction-test"
        def decode(samples, *a, **kw):
            data = samples["samples"]
            if isinstance(data, (tuple, list)):
                data = data[0]
            length = data.shape[2] if data.ndim == 5 else data.shape[1]
            return f.torch.full((length, 96, 96, 3), .3), None
        def pin(positive, latent, **kw):
            tails.append(kw["context_frames"].shape[0])
            return positive, 22, 0
        def end(positive, latent, frame, vae, **kw):
            ends.append((frame.clone(), kw["frame_index"]))
            return positive
        def refine_call(plan, seg, **kw):
            if second is not None:
                second.append(kw["seed"])
            refined.append(kw.get("right_frame"))
            return kw["samples"], "refined"
        with mock.patch.object(f.core, "apply_motion_context", pin), \
             mock.patch.object(j, "apply_end_lock", end), \
             mock.patch.object(f.core, "select_continuity_pin_latent", lambda *a: None), \
             mock.patch.object(f.core, "describe_pin_window", lambda *a, **kw: ""):
            result = self.runner.execute(p, first, second, run_cineStack_conditioning=condition,
                        _decode_av_latent=decode, apply_segment_refine=refine_call)
        return tails, ends, refined, result

    def test_middle_rebuild_reads_only_two_small_windows_and_own_seed(self):
        self.run_plan(self.plan())
        p = self.plan({1})
        p.segments[1].first_pass_seed = (1 << 64) - 1
        first = []
        with mock.patch.object(f.core, "load_segment_av_latent", side_effect=AssertionError("whole neighbour AV")), \
             mock.patch.object(f.core, "load_first_pass_av_latent", side_effect=AssertionError("whole neighbour pre AV")), \
             mock.patch.object(f.core, "load_segment_cache", side_effect=AssertionError("whole neighbour RGB")):
            tails, ends, _, out = self.run_plan(p, first)
        self.assertEqual(first, [(1 << 64) - 1])
        self.assertEqual(tails, [22])
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0][0].shape, (1, 96, 96, 3))
        self.assertEqual(len(out[4]), 1)

    def test_each_disconnected_side_is_not_read(self):
        self.run_plan(self.plan())
        for left, right in ((False, True), (True, False), (False, False)):
            p = self.plan({1})
            p.segments[1].continuity_from_prev = left
            p.segments[2].continuity_from_prev = right
            with mock.patch.object(j, "load_boundary", wraps=j.load_boundary) as reader:
                tails, ends, _, _ = self.run_plan(p)
            self.assertEqual(bool(tails), left)
            self.assertEqual(bool(ends), right)
            self.assertEqual({call.args[1].index for call in reader.call_args_list},
                             ({0} if left else set()) | ({2} if right else set()))

    def test_missing_both_neighbours_fails_before_sampling_or_pruning(self):
        p = self.plan({1})
        with mock.patch.object(f.core, "prune_segment_cache") as prune:
            with self.assertRaises(ValueError) as error:
                self.run_plan(p)
            prune.assert_not_called()
        self.assertIn("第 2 段左接点，需要第 1 段", str(error.exception))
        self.assertIn("第 2 段右接点，需要第 3 段", str(error.exception))

    def test_selected_island_uses_only_external_right_boundary(self):
        self.run_plan(self.plan(count=4))
        with mock.patch.object(j, "load_boundary", wraps=j.load_boundary) as reader:
            tails, ends, _, _ = self.run_plan(self.plan({1, 2}, count=4))
        self.assertEqual(len(tails), 2)
        self.assertEqual(len(ends), 1)
        self.assertEqual({c.args[1].index for c in reader.call_args_list}, {0, 3})

    def test_refine_only_uses_frozen_endpoint_without_neighbour_reads(self):
        self.run_plan(self.plan())
        self.run_plan(self.plan({1}))
        p = self.plan({1}, "refine_only")
        first, second = [], []
        with mock.patch.object(j, "load_boundary", side_effect=AssertionError("must not read neighbours")):
            tails, ends, refined, _ = self.run_plan(p, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [200])
        self.assertEqual((tails, ends), ([], []))
        self.assertEqual(refined[0].shape[0], 1)

    def test_changed_right_link_invalidates_strict_second_and_status(self):
        self.run_plan(self.plan())
        p = self.plan({1}, "refine_only")
        p.segments[2].continuity_from_prev = False
        with self.assertRaisesRegex(ValueError, "左右连接线"):
            self.run_plan(p)
        status = f.cache.inspect_first_pass_cache("fixture", p)
        self.assertFalse(status["segments"][1]["matches"])

    def test_corrupt_frozen_endpoint_rejected_before_refine(self):
        self.run_plan(self.plan())
        self.run_plan(self.plan({1}))
        path = f.cache._cache_dir("fixture") / "seg_0001.pre.av.pt"
        payload = f.torch.load(path, weights_only=False)
        payload.pop(j.LOCK_KEY)
        f.torch.save(payload, path)
        with self.assertRaisesRegex(ValueError, "右接点快照"):
            self.run_plan(self.plan({1}, "refine_only"))

    def test_old_rgb_mmap_reads_actual_export_interval(self):
        p = self.plan()
        seg = p.segments[0]
        frames = f.torch.arange(80, dtype=f.torch.uint8).reshape(80, 1, 1, 1).expand(80, 32, 32, 3).clone()
        f.cache.save_first_pass_cache("fixture", seg, p, av_latent={"samples": f.torch.zeros(1, 2)},
            frames=frames, handoff={"trim_frames": 5, "export_frames": 40})
        head, _ = j.load_boundary("fixture", seg, p, "head")
        tail, _ = j.load_boundary("fixture", seg, p, "tail")
        self.assertEqual(round(head[0, 0, 0, 0].item() * 255), 5)
        self.assertEqual(round(tail[-1, 0, 0, 0].item() * 255), 44)
        self.assertEqual(len(tail), 22)

    def test_old_rolling_video_ranges_are_streamed_when_sidecars_missing(self):
        self.run_plan(self.plan())
        root = f.cache._cache_dir("fixture")
        for path in root.glob("*.boundary.pt"):
            path.unlink()
        with mock.patch.object(f.core, "_decode_av_latent", side_effect=AssertionError("no VAE decode")):
            head, _ = j.load_boundary("fixture", self.plan().segments[2], self.plan(), "head")
            tail, _ = j.load_boundary("fixture", self.plan().segments[0], self.plan(), "tail")
        self.assertEqual((len(head), len(tail)), (1, 22))
        self.assertAlmostEqual(head.mean().item(), .3, delta=.03)

    def test_sidecar_storage_is_bounded_and_does_not_keep_full_tensor_storage(self):
        p = self.plan()
        x = f.torch.ones(300, 96, 96, 3)
        f.cache.save_segment_cache("fixture", p.segments[0], p, x)
        payload = f.torch.load(f.cache._cache_dir("fixture") / "seg_0000.boundary.pt", weights_only=True)
        self.assertEqual(len(payload["head"]), 1)
        self.assertEqual(len(payload["tail"]), 56)
        for key in ("head", "tail"):
            self.assertEqual(payload[key].untyped_storage().nbytes(), payload[key].numel())

    def test_actual_keyframe_merge_preserves_refs_prefix_and_retargets_export_end(self):
        helper = types.ModuleType("node_helpers")
        helper.conditioning_set_values = lambda rows, values: [[t, {**meta, **values}] for t, meta in rows]
        positive = [[f.torch.zeros(1), {"minimax_refs": [{"kind": "image"}], "minimax_keyframes": [
            {"resolved_frame_index": 0, patches.CTX_FRAME_KEY: 0, "latent": f.torch.zeros(1, 24, 1, 2, 2)},
            {"resolved_frame_index": 38, "latent": f.torch.zeros(1, 24, 1, 2, 2)}]}]]
        latent = {"samples": (f.torch.zeros(1, 24, h3.steps_for_frames(39), 2, 2),)}
        vae = types.SimpleNamespace(encode=lambda frame: f.torch.ones(1, 24, 1, 2, 2))
        with mock.patch.dict(sys.modules, {"node_helpers": helper}), \
             mock.patch.object(patches, "ensure_layout_patch"), mock.patch.object(patches, "ensure_payload_patch"), \
             mock.patch(f.PKG + ".lib.image_prep.fit_canvas", side_effect=lambda frame, w, h: frame):
            out = j.apply_end_lock(positive, latent, f.torch.ones(1, 32, 32, 3), vae, frame_index=30)
        self.assertEqual([k[patches.CTX_FRAME_KEY] for k in out[0][1]["minimax_keyframes"]], [0, 30])
        self.assertEqual(out[0][1]["minimax_refs"], positive[0][1]["minimax_refs"])
        self.assertEqual(len(positive[0][1]["minimax_keyframes"]), 2)

    def test_refine_reapplies_endpoint_after_canvas_preparation(self):
        p = self.plan({1}, "refine_only")
        args = dict(samples={"samples": f.torch.zeros(1, 2, 3, 2, 2)}, model=object(), vae=object(),
                    positive=[], negative=[], seed=200, cfg=1, first_steps=4, sampler_name="euler",
                    scheduler="simple", shift_video=1, shift_audio=1, right_frame=f.torch.ones(1, 32, 32, 3),
                    right_frame_index=4)
        with mock.patch.object(j, "apply_end_lock", return_value=["right-lock"]) as lock, \
             mock.patch.object(refine, "sample_single_stage", side_effect=lambda **kw: kw["latent"]) as sample:
            refine.apply_segment_refine(p, p.segments[1], **args)
        lock.assert_called_once()
        self.assertEqual(sample.call_args.kwargs["positive"], ["right-lock"])

    def test_old_av_only_cache_stops_instead_of_decoding_whole_neighbours(self):
        self.run_plan(self.plan())
        root = f.cache._cache_dir("fixture")
        for path in root.glob("*.boundary.pt"):
            path.unlink()
        (root / "rolling_videos.json").unlink()
        with mock.patch.object(f.core, "_decode_av_latent", side_effect=AssertionError("whole decode")):
            with self.assertRaisesRegex(ValueError, "只有 AV latent"):
                self.run_plan(self.plan({1}))

    def test_connected_i2v_head_overrides_explicit_start_image(self):
        self.run_plan(self.plan())
        p = self.plan({1})
        p.segments[1].task_key = "i2v"
        with mock.patch.object(f.core, "resolve_segment_raw_clip", return_value=f.torch.zeros(0, 96, 96, 3)), \
             mock.patch.object(f.core, "_build_cineStack_inputs",
                return_value=(f.torch.zeros(1, 96, 96, 3), None, None, None, None, None)):
            tails, ends, _, _ = self.run_plan(p)
        self.assertEqual(tails, [22])
        self.assertEqual(len(ends), 1)

    def test_continue_mode_keeps_right_keyframe_and_bounded_left_window(self):
        self.run_plan(self.plan())
        p = self.plan({1})
        p.continuity_mode = "continue"
        continuation = importlib.import_module(f.PKG + ".director.h3_latent_continue")
        def lock(latent, **kw):
            self.assertIsNone(kw["prev_av"])
            self.assertEqual(len(kw["prev_tail"]), 22)
            return latent, 22, 0
        with mock.patch.object(continuation, "apply_latent_continue", side_effect=lock) as apply:
            _, ends, _, _ = self.run_plan(p)
        apply.assert_called_once()
        self.assertEqual(len(ends), 1)

    def test_upscale_preserves_connected_endpoints_and_reencodes_right_at_new_canvas(self):
        p = self.plan({1}, "refine_only")
        p.refine.update(mode="upscale")
        p.segments[1].task_key = "i2v"
        work = {"samples": f.torch.zeros(1, 2, 3, 8, 8)}
        with mock.patch.object(refine, "refine_uses_h3_latent", return_value=True), \
             mock.patch.object(refine, "_resolve_refine_canvas", return_value=(128, 128)), \
             mock.patch.object(refine, "_apply_h3_latent_upscale", return_value=(work, [], [])), \
             mock.patch.object(refine, "_refresh_refine_endpoints", return_value=([], work, "")) as manual, \
             mock.patch.object(j, "apply_end_lock", return_value=["new-canvas-lock"]) as right, \
             mock.patch.object(refine, "sample_single_stage", side_effect=lambda **kw: kw["latent"]):
            refine.apply_segment_refine(p, p.segments[1], samples={"samples": f.torch.zeros(1, 2)},
                model=object(), vae=object(), positive=[], negative=[], seed=200, cfg=1, first_steps=4,
                sampler_name="euler", scheduler="simple", shift_video=1, shift_audio=1, trim_frames=22,
                right_frame=f.torch.ones(1, 32, 32, 3), right_frame_index=38)
        self.assertTrue(manual.call_args.kwargs["connected_head"])
        self.assertTrue(manual.call_args.kwargs["connected_tail"])
        self.assertIs(right.call_args.args[1], work)

    def test_strict_refine_restores_own_prefix_without_previous_refined_av(self):
        p = self.plan({1}, "refine_only")
        work = {"samples": f.torch.zeros(1, 2)}
        with mock.patch.object(refine, "_repin_after_upscale", return_value=([], True, work)) as repin, \
             mock.patch.object(refine, "sample_single_stage", side_effect=lambda **kw: kw["latent"]):
            refine.apply_segment_refine(p, p.segments[1], samples=work, model=object(), vae=object(),
                positive=[], negative=[], seed=200, cfg=1, first_steps=4, sampler_name="euler",
                scheduler="simple", shift_video=1, shift_audio=1, trim_frames=22, reuse_first_pass=True)
        repin.assert_called_once()
        self.assertNotIn("prev_refine_av", repin.call_args.kwargs)

    def test_gap_and_disconnected_joins_skip_legacy_export_seam_processing(self):
        continuity = importlib.import_module(f.PKG + ".director.segment_continuity")
        p = self.plan()
        p.segments[1].continuity_from_prev = False
        p.segments[2].start_frame += 10
        self.assertEqual(j.links(p, p.segments[1]), {"left": False, "right": False})
        chunks = [f.torch.zeros(5, 32, 32, 3) for _ in range(3)]
        with mock.patch.object(continuity, "prepare_export_seam", side_effect=AssertionError("disconnected seam")):
            joined = continuity.concat_continuous_chunks(chunks, p.segments, p)
        self.assertEqual(joined.shape[0], 15)


if __name__ == "__main__":
    unittest.main()
