"""Ordinary All export: exact old pixels, bounded allocations and cache isolation."""
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import torch
from torch.utils._python_dispatch import TorchDispatchMode
import test_segment_seed_refine_only as f
import test_rolling as rolling

c = importlib.import_module(f.PKG + '.director.segment_continuity')
m = importlib.import_module(f.PKG + '.director.memory_diagnostics')


def legacy(chunks, segments, plan):
    # Frozen pre-0.6.8 algorithm, intentionally retaining all corrected clones.
    if not plan.continuity_enabled or len(chunks) < 2:
        return c.cat_frames_variable_size(chunks)
    fixed = [chunks[0]]
    for i in range(1, len(chunks)):
        if (i >= len(segments) or segments[i].index != segments[i - 1].index + 1
                or not c.is_continuity_active(plan, segments[i])):
            fixed.append(chunks[i])
            continue
        left, body = c.prepare_export_seam(fixed[-1], chunks[i])
        fixed[-1] = left
        fixed.append(body)
    return c.cat_frames_variable_size(fixed)


class Allocations(TorchDispatchMode):
    def __init__(self):
        super().__init__()
        self.clones, self.empty, self.cats = [], [], 0

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        if func == torch.ops.aten.clone.default:
            self.clones.append(args[0].numel())
        if func == torch.ops.aten.empty.memory_format:
            self.empty.append(tuple(args[0]))
        if func == torch.ops.aten.cat.default:
            self.cats += 1
        return func(*args, **(kwargs or {}))


class StandardMergeTests(unittest.TestCase):
    def setUp(self):
        prep = importlib.import_module(f.PKG + '.lib.image_prep')
        # The complete suite installs an audio-only Comfy adapter. Supply only
        # the resize adapter here; seam/padding/concatenation remain real code.
        patcher = mock.patch.object(prep, 'common_upscale',
            lambda tensor, width, height, *a: torch.nn.functional.interpolate(
                tensor, size=(height, width), mode='nearest'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fixtures(self, lengths=(124, 170, 136, 170, 170, 136)):
        plan = SimpleNamespace(continuity_enabled=True, segment_count=len(lengths))
        segments = [SimpleNamespace(index=i, timeline_index=i, continuity_from_prev=i > 0,
                                    task_key='r2v', start_frame=i*300, end_frame=(i+1)*300) for i in range(len(lengths))]
        plan.segments = segments
        chunks = [torch.linspace(.1 + i * .07, .25 + i * .07, n).view(-1, 1, 1, 1)
                  .expand(-1, 8, 10, 3).clone() for i, n in enumerate(lengths)]
        return chunks, segments, plan

    def test_six_segment_pixels_equal_legacy_one_output_no_whole_clip_clones(self):
        chunks, segments, plan = self.fixtures()
        originals = [x.clone() for x in chunks]
        expected = legacy(chunks, segments, plan)
        with Allocations() as allocations:
            result = c.concat_continuous_chunks(chunks, segments, plan)
        self.assertTrue(torch.equal(result, expected))
        self.assertEqual(result.shape[0], 906)
        self.assertEqual(allocations.empty.count(tuple(result.shape)), 1)
        self.assertEqual(allocations.clones, [])
        self.assertEqual(allocations.cats, 0)
        for before, after in zip(originals, chunks):
            self.assertTrue(torch.equal(before, after))
        result.zero_()
        self.assertTrue(torch.equal(chunks[0], originals[0]))

    def test_disconnected_gaps_short_empty_and_repeated_views_match(self):
        for lengths in [(1, 2, 3, 12, 13), (0, 16, 0, 17), (277, 277, 277)]:
            chunks, segments, plan = self.fixtures(lengths)
            if len(chunks) == 3:
                chunks[2] = chunks[0][:]  # shared source storage, different guide
            segments[1].continuity_from_prev = False
            if len(segments) > 3:
                segments[3].index += 10
            before = [x.clone() for x in chunks]
            expected = legacy(chunks, segments, plan)
            result = c.concat_continuous_chunks(chunks, segments, plan)
            self.assertTrue(torch.equal(result, expected))
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(chunks, before)))

    def test_mixed_geometry_dtype_and_noncontiguous_views_preserve_native_seams(self):
        chunks, segments, plan = self.fixtures((21, 17, 18))
        chunks[0] = chunks[0][:, ::2, 1:8].to(torch.float64)
        chunks[1] = chunks[1][:, 1:6, ::2]
        chunks[2] = chunks[2].transpose(1, 2).to(torch.float16)
        before = [x.clone() for x in chunks]
        expected = legacy(chunks, segments, plan)
        result = c.concat_continuous_chunks(chunks, segments, plan)
        self.assertTrue(torch.equal(result, expected), (result - expected).abs().max())
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(chunks, before)))

    def test_no_continuity_and_single_segment_keep_legacy_layout(self):
        chunks, segments, plan = self.fixtures((5, 6))
        plan.continuity_enabled = False
        self.assertTrue(torch.equal(c.concat_continuous_chunks(chunks, segments, plan),
                                    legacy(chunks, segments, plan)))
        self.assertIs(c.concat_continuous_chunks(chunks[:1], segments[:1], plan), chunks[0])
        with self.assertRaises(ValueError):
            c.concat_continuous_chunks([], [], plan)

    def test_failure_leaves_sources_unchanged_and_no_false_seam_completion(self):
        chunks, segments, plan = self.fixtures((27, 27, 27))
        originals = [x.clone() for x in chunks]
        events = []
        real = c.prepare_export_seam
        def fail(left, body, **kw):
            real(left, body, **kw)
            raise RuntimeError('after modifying destination')
        with mock.patch.object(c, 'prepare_export_seam', fail):
            with self.assertRaisesRegex(RuntimeError, 'destination'):
                c.concat_continuous_chunks(chunks, segments, plan,
                    observe=lambda stage, *a, **kw: events.append(stage))
        self.assertEqual(events[-1], 'merge_seam_before')
        self.assertNotIn('merge_seam_after', events)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(chunks, originals)))


class StandardExecutorTests(unittest.TestCase):
    def setUp(self):
        self.case = f.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def trace(self):
        files = list(self.case.output.glob('cinestack_diagnostics/*/memory_diagnostics.jsonl'))
        self.assertEqual(len(files), 1)
        return [json.loads(s) for s in files[0].read_text().splitlines()]

    def test_strict_second_pass_preserves_cache_and_records_both_output_allocations(self):
        plan = self.case.build((561215411,) * 6)
        self.case.store(plan)
        root = f.cache._cache_dir('fixture')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.pre.*')}
        first, second = [], []
        result = self.case.execute(plan, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [561215411] * 6)
        self.assertEqual(result[0].shape[0], 30)
        self.assertEqual(result[5].shape[0], 30)
        for whole, pieces in ((result[0], result[1]), (result[5], result[6])):
            self.assertTrue(all(p.untyped_storage().data_ptr() == whole.untyped_storage().data_ptr()
                                for p in pieces))

        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.pre.*') if p.name in before})
        rows = self.trace()
        allocations = [r for r in rows if r['stage'] == 'merge_allocate_before']
        self.assertEqual([r['counters']['output_stage'] for r in allocations], ['final', 'first'])
        self.assertEqual([r['counters']['requested_output_bytes'] for r in allocations], [30*32*32*3*4]*2)
        self.assertEqual(len([r for r in rows if r['stage'] == 'merge_copy_after']), 12)
        names = [r['stage'] for r in rows]
        self.assertLess(names.index('merge_before'), names.index('merge_after'))
        self.assertEqual(names[-1], 'execution_exit')
        self.assertFalse(list(self.case.output.glob('minimax_seg_export/*')))  # diagnostics only

    def test_merge_allocation_failure_does_not_mark_finished_or_rewrite_first_cache(self):
        plan = self.case.build((12, 34))
        self.case.store(plan)
        events = []
        def merge(chunks, segments, plan, **kw):
            kw['observe']('merge_allocate_before', output_stage=kw['output_stage'])
            raise MemoryError('fixture allocation')
        with mock.patch.object(f.core, 'report_director_finish', side_effect=lambda *a: events.append('finish')):
            with self.assertRaises(MemoryError):
                self.case.execute(plan, concat_continuous_chunks=merge)
        self.assertEqual(events, [])
        names = [r['stage'] for r in self.trace()]
        self.assertNotIn('merge_after', names)
        self.assertEqual(names[-3:], ['merge_allocate_before', 'execution_failed', 'execution_exit'])
        self.assertTrue(f.cache.inspect_first_pass_cache('fixture', plan)['can_confirm_refine'])

    def test_default_diagnostics_and_explicit_disable_do_not_change_fingerprint(self):
        plan = self.case.build((12,))
        before = f.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        diag = m.MemoryDiagnostics(plan, None)
        self.assertTrue(diag.enabled)
        self.assertIsNotNone(diag.path)
        plan.raw['output']['memoryDiagnostics'] = False
        self.assertFalse(m.MemoryDiagnostics(plan, None).enabled)
        self.assertEqual(before, f.cache.first_pass_cache_fingerprint(plan.segments[0], plan))

    def test_normal_connected_execution_reports_each_seam_and_finishes_after_merge(self):
        runner = rolling.RollingTests()
        runner.case = self.case
        plan = runner.continuity_plan(False)
        events = []
        record = m.MemoryDiagnostics.record
        def observe(diag, stage, *args, **kwargs):
            events.append(stage)
            return record(diag, stage, *args, **kwargs)
        with mock.patch.object(m.MemoryDiagnostics, 'record', observe), \
             mock.patch.object(f.core, 'report_director_finish', side_effect=lambda *a: events.append('finish')):
            result, pins = runner.continuity_run(plan)
        self.assertEqual(pins, [39, 51])
        self.assertEqual(result[4], [38, 50, 51])
        self.assertEqual(events.count('merge_seam_before'), 4)
        self.assertEqual(events.count('merge_seam_after'), 4)
        self.assertLess(events.index('merge_after'), events.index('finish'))
        self.assertTrue(torch.equal(result[0], result[5]))  # first-pass confirmation copies remain equivalent
