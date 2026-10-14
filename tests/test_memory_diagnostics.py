"""Diagnostic storage accounting and real executor placement; no GPU required."""
import gc
import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import weakref

import test_segment_seed_refine_only as f

m = importlib.import_module(f.PKG + '.director.memory_diagnostics')


class MemoryDiagnosticsTests(unittest.TestCase):
    def test_shared_views_count_complete_storage_once_without_retaining_it(self):
        tensor = f.torch.zeros(100)
        view = tensor[10:12]
        ref = weakref.ref(tensor)
        data = {'a': tensor, 'b': view}
        data['cycle'] = data
        result = m.storage_snapshot({'frames': data, 'latents': [tensor, view]})
        self.assertEqual(result['cpu_bytes'], 400)
        self.assertEqual(result['storage_count'], 1)
        self.assertEqual(result['groups']['latents']['cpu'], 0)
        del data, view, tensor
        gc.collect()
        self.assertIsNone(ref())

    def test_comfy_av_wrapper_and_distinct_clones_are_counted(self):
        class NestedTensor:
            __module__ = 'comfy.nested_tensor'
            def __init__(self, tensors): self.tensors = tensors
            def unbind(self): return self.tensors
        tensor = f.torch.zeros(10)
        payload = NestedTensor((tensor, tensor.clone()))
        result = m.storage_snapshot({'latents': {'samples': payload}})
        self.assertEqual(result['cpu_bytes'], 80)
        self.assertEqual(result['storage_count'], 2)

    def test_traversal_is_bounded_and_reports_incompleteness(self):
        rows = [f.torch.zeros(1) for _ in range(100)]
        result = m.storage_snapshot({'frames': rows}, max_objects=5)
        self.assertTrue(result['truncated'])
        self.assertLessEqual(result['visited_objects'], 5)
        self.assertLessEqual(result['cpu_bytes'], 16)

    def test_json_trace_has_real_deltas_and_does_not_record_content(self):
        with tempfile.TemporaryDirectory() as root:
            diag = m.MemoryDiagnostics(SimpleNamespace(raw={}), root, rolling=True)
            tensor = f.torch.zeros(10)
            ref = weakref.ref(tensor)
            with mock.patch.object(m, 'process_snapshot', side_effect=[{'VmRSS': 1000}, {'VmRSS': 1400}]):
                diag.record('segment_start', 3, {'frames': tensor})
                diag.record('decode_after', 3, {'frames': tensor, 'prompt': 'secret prompt'})
            rows = [json.loads(s) for s in diag.path.read_text().splitlines()]
            self.assertEqual(rows[1]['delta_segment_rss'], 400)
            self.assertEqual(rows[1]['delta_previous_rss'], 400)
            self.assertEqual(rows[1]['tensors']['cpu_bytes'], 40)
            self.assertNotIn('secret prompt', diag.path.read_text())
            del tensor
            gc.collect()
            self.assertIsNone(ref())

    def test_disable_and_probe_or_output_failures_never_fail_generation(self):
        with tempfile.TemporaryDirectory() as root:
            plan = SimpleNamespace(raw={})
            diag = m.MemoryDiagnostics(plan, root, rolling=False)
            diag.record('test')
            self.assertFalse(diag.path.exists())
            with mock.patch.dict('os.environ', {'CINESTACK_MEMORY_DIAGNOSTICS': '0'}):
                self.assertFalse(m.MemoryDiagnostics(plan, root, rolling=True).enabled)
            diag = m.MemoryDiagnostics(plan, root, rolling=True)
            with mock.patch.object(m, 'allocator_snapshot', side_effect=RuntimeError('unsupported')):
                diag.record('test')
            row = json.loads(diag.path.read_text())
            self.assertIsNone(row['tensors'])  # Unmeasured is not zero.
            self.assertIsNone(row['allocator'])
            self.assertEqual(row['probe_errors']['allocator'], 'RuntimeError')
            diag.path = Path(root) / 'missing' / 'trace'
            diag.record('test')
            self.assertTrue(diag.file_failed)

    def test_process_fields_and_mallinfo_are_not_confused_with_rss(self):
        with mock.patch.object(Path, 'read_text', return_value='VmRSS: 123 kB\nRssAnon: 100 kB\nVmSwap: 4 kB\n'):
            self.assertEqual(m.process_snapshot(), {'VmRSS': 123*1024, 'RssAnon': 100*1024, 'VmSwap': 4*1024})
        fake = m.Mallinfo2()
        fake.uordblks, fake.fordblks, fake.hblkhd = 20, 30, 40
        with mock.patch.object(m, '_mallinfo', return_value=lambda: fake):
            self.assertEqual(m.allocator_snapshot()['fordblks'], 30)


class DiagnosticExecutorTests(unittest.TestCase):
    def setUp(self):
        self.case = f.SegmentSeedTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def build(self, mode='first_pass'):
        plan = self.case.build((100, 200, 300))
        plan.raw['executionMode'] = mode
        plan.raw['output']['rollingGeneration'] = True
        plan.raw['output']['exportMode'] = 'segments'
        plan.export_mode = 'segments'
        return plan

    def trace(self, plan):
        return [json.loads(s) for s in (Path(plan.segment_mp4_run_dir) / 'memory_diagnostics.jsonl').read_text().splitlines()]

    def test_rolling_stage_order_and_bounded_storage_preserve_seeds_and_outputs(self):
        plan = self.build()
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual((first, second), ([100, 200, 300], []))
        rows = self.trace(plan)
        names = [r['stage'] for r in rows]
        for before, after in [('conditioning_before', 'conditioning_after'), ('decode_before', 'decode_after'),
                              ('release_before', 'release_after'), ('merge_before', 'merge_after')]:
            self.assertLess(names.index(before), names.index(after))
        ends = [r for r in rows if r['stage'] == 'segment_end']
        self.assertEqual(len(ends), 3)
        self.assertTrue(all(r['counters']['frame_slots'] <= 1 for r in ends))
        self.assertLess(max(r['tensors']['groups']['frames']['cpu'] for r in ends), 100000)
        self.assertEqual(names[-1], 'execution_exit')
        self.assertFalse(hasattr(plan, '_active_memory_diagnostics'))

    def test_strict_second_pass_is_reused_and_diagnostics_do_not_change_identity(self):
        base = self.build()
        self.case.execute(base)
        plan = self.build('refine_only')
        before = f.cache.first_pass_cache_fingerprint(plan.segments[0], plan)
        plan.raw['output']['memoryDiagnostics'] = True
        self.assertEqual(before, f.cache.first_pass_cache_fingerprint(plan.segments[0], plan))
        first, second = [], []
        self.case.execute(plan, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [100, 200, 300])
        names = [r['stage'] for r in self.trace(plan)]
        self.assertIn('first_pass_reused', names)
        self.assertNotIn('first_pass_sampled', names)

    def test_real_refine_loop_records_each_pass_without_export_hook(self):
        refinement = importlib.import_module(f.PKG + '.director.refine_sampling')
        plan = self.build('refine_only')
        plan.refine['passes'] = 2
        plan._active_memory_diagnostics = m.MemoryDiagnostics(plan, self.case.output, rolling=True)
        work = {'samples': f.torch.zeros(1, 2, 1, 2, 2)}
        with mock.patch.object(refinement, 'sample_single_stage', side_effect=lambda **kw: kw['latent']) as sample:
            result, _ = refinement.apply_segment_refine(plan, plan.segments[0], samples=work,
                model=object(), vae=None, audio_vae=None, positive=[], negative=[], seed=100, cfg=1,
                first_steps=4, sampler_name='euler', scheduler='simple', shift_video=12, shift_audio=3,
                on_pass=None)
        self.assertTrue(f.torch.equal(result["samples"], work["samples"]))
        self.assertEqual(sample.call_count, 2)
        rows = [json.loads(line) for line in plan._active_memory_diagnostics.path.read_text().splitlines()]
        self.assertEqual([row['stage'] for row in rows],
                         ['refine_pass_1_before', 'refine_pass_1_after', 'refine_pass_2_before', 'refine_pass_2_after'])

    def test_sampling_failure_keeps_original_exception_and_partial_trace(self):
        plan = self.build()
        with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            self.case.execute(plan, sample_single_stage=mock.Mock(side_effect=RuntimeError('fixture failure')))
        names = [r['stage'] for r in self.trace(plan)]
        self.assertIn('sampling_before', names)
        self.assertIn('execution_failed', names)
        self.assertEqual(names[-1], 'execution_exit')
