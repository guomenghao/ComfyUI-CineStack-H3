"""Real CPU seam math, allocation bounds and executor export-buffer ownership."""
import importlib
import json
from pathlib import Path
import unittest
from unittest import mock
import weakref

import torch
from torch.utils._python_dispatch import TorchDispatchMode
import test_rolling as rolling_tests

f = rolling_tests.f
continuity = importlib.import_module(f.PKG + '.director.segment_continuity')


class CloneSizes(TorchDispatchMode):
    def __init__(self):
        super().__init__()
        self.sizes = []

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        if func == torch.ops.aten.clone.default:
            self.sizes.append(args[0].numel())
        return func(*args, **(kwargs or {}))


class OpeningMemoryTests(unittest.TestCase):
    def test_owned_seam_matches_legacy_without_full_clip_clone(self):
        # The reported 277-frame final shot, including a deliberately visible seam.
        body = torch.linspace(.2, .4, 277).view(-1, 1, 1, 1).expand(-1, 16, 16, 3).clone()
        guide = torch.full((22, 16, 16, 3), .1)
        original, previous = body.clone(), guide.clone()
        expected_left, expected = continuity.prepare_export_seam(guide, body)
        self.assertTrue(torch.equal(body, original))  # Legacy caller owns its input.
        with CloneSizes() as clones:
            left, actual = continuity.prepare_export_seam(guide, body, inplace_body=True)
        self.assertIs(actual, body)
        self.assertTrue(torch.equal(expected, actual))
        self.assertTrue(torch.equal(expected_left, left))
        self.assertTrue(torch.equal(guide, previous))
        self.assertTrue(torch.equal(body[12:], original[12:]))
        self.assertLess(max(clones.sizes, default=0), body.numel())
        self.assertFalse(torch.equal(body[:12], original[:12]))

    def test_view_alias_permissions_preserve_distinct_or_unconstrained_consumers(self):
        body, guide = torch.zeros(40, 8, 8, 3), torch.ones(22, 8, 8, 3)
        key = (continuity.export_frame_view_key(guide), continuity.export_frame_view_key(body))
        allowed = continuity.owned_export_seam_pairs
        self.assertEqual(allowed([(guide, body), (guide[:], body)], {id(body)}), {key})
        self.assertEqual(allowed([(guide, body)], set()), set())  # borrowed cache
        self.assertEqual(allowed([(guide, body), (guide[1:], body)], {id(body)}), set())
        self.assertEqual(allowed([(guide, body), (None, body)], {id(body)}), set())
        self.assertEqual(allowed([(guide, body), (guide, body[1:])], {id(body)}), set())
        self.assertEqual(allowed([(guide, body), (guide, body.transpose(1, 2))], {id(body)}), set())
        self.assertEqual(allowed([(guide, body), (body[:1], guide)], {id(body)}), set())

    def test_no_correction_does_not_allocate_or_change_pixels(self):
        body, guide = torch.full((277, 8, 8, 3), .3), torch.full((22, 8, 8, 3), .3)
        with CloneSizes() as clones:
            _, actual = continuity.prepare_export_seam(guide, body, inplace_body=True)
        self.assertIs(actual, body)
        self.assertEqual(clones.sizes, [])
        self.assertTrue(torch.all(actual == .3))

    def test_functional_default_keeps_shared_first_pass_and_other_branches_intact(self):
        source = torch.linspace(.2, .4, 40).view(-1, 1, 1, 1).expand(-1, 8, 8, 3).clone()
        cached = source.clone()
        branch_a = source[:]
        branch_b = source[:]
        _, a = continuity.prepare_export_seam(torch.full((2, 8, 8, 3), .1), branch_a)
        _, b = continuity.prepare_export_seam(torch.full((2, 8, 8, 3), .8), branch_b)
        self.assertTrue(torch.equal(source, cached))
        self.assertNotEqual(a.data_ptr(), b.data_ptr())
        self.assertFalse(torch.equal(a[:12], b[:12]))
        self.assertTrue(torch.equal(a[12:], cached[12:]))
        self.assertTrue(torch.equal(b[12:], cached[12:]))


class PostprocessExecutorTests(unittest.TestCase):
    def setUp(self):
        self.case = rolling_tests.RollingTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_original_decode_released_before_seam_and_full_stage_trace_written(self):
        plan = self.case.continuity_plan()
        raw_refs, calls = [], []
        grade = f.core.match_export_opening_grade
        seam = f.core.prepare_export_seam
        def watch_grade(body, guide, **kw):
            # body is a cropped view of the fresh decoder output.
            raw_refs.append(weakref.ref(body._base if body._base is not None else body))
            return grade(body, guide, **kw)
        def watch_seam(left, body, **kw):
            self.assertTrue(kw.get('inplace_body'))
            self.assertIsNone(raw_refs[-1](), 'obsolete decoder storage retained into seam')
            expected = seam(left, body)[1]
            with CloneSizes() as clones:
                result = seam(left, body, **kw)
            self.assertTrue(torch.equal(result[1], expected))
            self.assertLess(max(clones.sizes, default=0), body.numel())
            calls.append(id(body))
            return result
        with mock.patch.object(f.core, 'match_export_opening_grade', watch_grade), \
             mock.patch.object(f.core, 'prepare_export_seam', watch_seam):
            self.case.continuity_run(plan)
        self.assertEqual(len(calls), 2)  # aliases for first/final/pre-face deduplicated
        rows = [json.loads(s) for s in (Path(plan.segment_mp4_run_dir) / 'memory_diagnostics.jsonl').read_text().splitlines()]
        stages = ['export_cpu_before', 'export_cpu_after', 'opening_grade_before',
                  'opening_grade_after', 'postprocess_release', 'seam_before', 'seam_after',
                  'segment_cache_before', 'segment_cache_after', 'boundary_cache_before',
                  'boundary_cache_after', 'segment_export_before', 'segment_export_after']
        for segment in (1, 2, 3):
            names = [r['stage'] for r in rows if r['segment'] == segment]
            offsets = [names.index(s) for s in stages]
            self.assertEqual(offsets, sorted(offsets))
        for segment in (2, 3):
            by_name = {r['stage']: r for r in rows if r['segment'] == segment}
            self.assertLess(by_name['postprocess_release']['tensors']['cpu_bytes'],
                            by_name['opening_grade_after']['tensors']['cpu_bytes'])

    def test_nineteen_connected_segments_with_long_final_shot_keep_seams_bounded(self):
        plan = self.case.build(tuple(range(100, 119)))
        plan.continuity_enabled = True
        plan.continuity_overlap_frames = 22
        plan.width = plan.height = 96
        start = 0
        for seg in plan.segments:
            seg.continuity_from_prev = seg.index > 0
            seg.start_frame = start
            start += 277 if seg.index == 18 else 39
            seg.end_frame = start
        seam, lengths = f.core.prepare_export_seam, []
        def check(left, body, **kw):
            self.assertTrue(kw.get('inplace_body'))
            with CloneSizes() as clones:
                result = seam(left, body, **kw)
            self.assertLess(max(clones.sizes, default=0), body.numel())
            lengths.append(body.shape[0])
            return result
        with mock.patch.object(f.core, 'prepare_export_seam', check):
            result, pins = self.case.continuity_run(plan)
        self.assertEqual(len(lengths), 18)
        self.assertGreaterEqual(lengths[-1], 277)
        self.assertEqual(len(pins), 18)
        encoded = self.case.pixels(Path(plan.segment_mp4_run_dir) / 'first_pass.mp4', 96)
        self.assertEqual(encoded.shape[0], sum(result[4]))

    def test_seam_failure_records_last_stage_without_success_or_final_merge(self):
        plan = self.case.continuity_plan()
        with mock.patch.object(f.core, 'prepare_export_seam', side_effect=RuntimeError('seam failure fixture')):
            with self.assertRaisesRegex(RuntimeError, 'seam failure fixture'):
                self.case.continuity_run(plan)
        rows = [json.loads(s) for s in (Path(plan.segment_mp4_run_dir) / 'memory_diagnostics.jsonl').read_text().splitlines()]
        stages = [r['stage'] for r in rows if r['segment'] == 2]
        self.assertIn('seam_before', stages)
        self.assertNotIn('seam_after', stages)
        self.assertNotIn('segment_result', stages)
        self.assertNotIn('merge_before', [r['stage'] for r in rows])
        self.assertEqual([r['stage'] for r in rows[-2:]], ['execution_failed', 'execution_exit'])
