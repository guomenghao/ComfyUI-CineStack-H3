"""Exercise the real sampler/cleanup with a CPU model of Comfy's pin lifecycle.

The fixture models fresh patch objects held by HostBuffer stacks on reload.
It does not emulate CUDA registration, native HostBuffer residency or GPU output.
See docs/host-memory-lifecycle.txt for the inspected official source paths.
"""
from contextlib import ExitStack
import gc
import importlib
import json
from types import SimpleNamespace as NS, ModuleType
import sys
import unittest
from unittest import mock
import weakref

import test_segment_seed_refine_only as f

sampling = importlib.import_module(f.PKG + '.director.core_sampling')
cleanup = importlib.import_module(f.PKG + '.director.vram_cleanup')
diag = importlib.import_module(f.PKG + '.director.memory_diagnostics')


class HostMemoryTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.refs = []
        self.state = {'active': False}
        for subset in ('weights', 'weights-loaded', 'weights-fast', 'patches', 'patches-loaded', 'patches-fast'):
            self.state[subset] = (NS(size=0), [], [-1], [0], [0], {})
        self.state['weights'][0].size = 4096
        self.state['weights'][3][0] = 4096
        self.patcher = NS(model=NS(dynamic_pins={'cuda:0': self.state}), load_device='cuda:0')
        self.mm = ModuleType('comfy.model_management')
        self.mm.current_loaded_models = [NS(model=self.patcher)]
        self.mm.TOTAL_PINNED_MEMORY = 4096
        self.mm.MAX_PINNED_MEMORY = 1 << 36
        self.mm.reset_cast_buffers = self.reset
        for name in ('cleanup_models_gc', 'cleanup_models', 'soft_empty_cache'):
            setattr(self.mm, name, lambda name=name: self.events.append(name))
        self.mm.unload_all_models = lambda: self.events.append('unload')
        self.prefetch = ModuleType('comfy.model_prefetch')
        self.prefetch.cleanup_prefetch_queues = lambda: self.events.append('drain')
        memory = ModuleType('comfy.memory_management')
        memory.aimdo_enabled = True
        custom = ModuleType('comfy_extras.nodes_custom_sampler')
        guider = NS(sample=lambda *args, **kw: None)
        custom.BasicGuider = NS(execute=lambda *args: (guider,))
        custom.CFGGuider = NS(execute=lambda *args: (guider,))
        custom.BasicScheduler = NS(execute=lambda *args: (f.torch.tensor([1., 0.]),))
        custom.KSamplerSelect = NS(execute=lambda *args: (object(),))
        custom.RandomNoise = NS(execute=lambda seed: (NS(seed=seed),))
        custom.SamplerCustomAdvanced = NS(execute=self.execute)
        h3 = ModuleType('comfy_extras.nodes_minimax_h3')
        h3.MiniMaxH3SigmaShift = NS(execute=lambda model, *args: (model,))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(sys.modules, {
            'comfy.model_management': self.mm, 'comfy.memory_management': memory,
            'comfy.model_prefetch': self.prefetch, 'comfy_extras.nodes_custom_sampler': custom,
            'comfy_extras.nodes_minimax_h3': h3}))
        self.memory, self.custom, self.guider = memory, custom, guider

    def execute(self, noise, guider, sampler, sigmas, latent):
        class Patch: pass
        patch = Patch()
        self.refs.append(weakref.ref(patch))
        entry = self.state['patches']
        entry[0].size += 1792 * 1024 ** 2  # Metadata only: no giant allocation.
        entry[1].append((patch, entry[0].size))
        entry[3][0] = entry[0].size
        self.mm.TOTAL_PINNED_MEMORY = 4096 + entry[0].size
        self.state['active'] = True
        self.events.append('sample')
        return ({'samples': latent['samples'] + noise.seed},)

    def reset(self):
        self.assertEqual(self.events[-1], 'drain')
        self.events.append('reset')
        for subset in ('patches', 'patches-loaded', 'patches-fast'):
            entry = self.state[subset]
            entry[0].size = entry[3][0] = 0
            entry[1].clear()
        self.mm.TOTAL_PINNED_MEMORY = 4096
        self.state['active'] = False

    def sample(self, seed=123, **kw):
        return sampling.sample_single_stage(model=self.patcher, positive=[], negative=[],
            latent={'samples': f.torch.ones(2)}, seed=seed, cfg=1, steps=1,
            sampler_name='euler', scheduler='simple', apply_shift=False, **kw)

    def test_19_stages_release_patch_owners_keep_weights_and_seed_outputs(self):
        # The old lifecycle leaves the strong stack owners alive across reloads.
        with mock.patch.object(cleanup, 'cleanup_sampling_buffers', return_value={}):
            for seed in (0, 7, 9):
                self.sample(seed)
        self.assertEqual(self.state['patches'][0].size, 3 * 1792 * 1024 ** 2)
        self.assertTrue(all(ref() is not None for ref in self.refs))
        cleanup.cleanup_sampling_buffers()
        for seed in range(19):
            out = self.sample(seed)
            self.assertTrue(f.torch.equal(out['samples'], f.torch.ones(2) + seed))
            self.assertEqual(self.state['patches'][0].size, 0)
            self.assertEqual(self.mm.TOTAL_PINNED_MEMORY, 4096)
        gc.collect()
        self.assertTrue(all(ref() is None for ref in self.refs))
        self.assertNotIn('unload', self.events)

    def test_sampling_error_preserved_and_buffers_cleared_before_refs_drop(self):
        original = self.execute
        def fail(*args):
            original(*args)
            raise RuntimeError('original sampler failure')
        self.custom.SamplerCustomAdvanced.execute = fail
        old_sample = self.guider.sample
        with self.assertRaisesRegex(RuntimeError, 'original sampler failure'):
            self.sample(on_step_preview=lambda *args: None)
        self.assertIs(self.guider.sample, old_sample)
        self.assertEqual(self.state['patches'][0].size, 0)
        self.assertEqual(self.events[-2:], ['drain', 'reset'])

    def test_cleanup_failure_does_not_mask_sampler_failure_or_reset_after_failed_drain(self):
        self.prefetch.cleanup_prefetch_queues = mock.Mock(side_effect=ValueError('drain failed'))
        self.mm.reset_cast_buffers = mock.Mock()
        result = cleanup.cleanup_sampling_buffers()
        self.assertEqual(result['error'], 'ValueError')
        self.mm.reset_cast_buffers.assert_not_called()
        self.custom.SamplerCustomAdvanced.execute = mock.Mock(side_effect=RuntimeError('sampler failed'))
        with self.assertRaisesRegex(RuntimeError, 'sampler failed'):
            self.sample()

    def test_legacy_hosts_and_optional_unload_order(self):
        self.memory.aimdo_enabled = False
        self.mm.reset_cast_buffers = mock.Mock()
        cleanup.cleanup_sampling_buffers()
        self.mm.reset_cast_buffers.assert_not_called()
        del self.mm.reset_cast_buffers
        self.memory.aimdo_enabled = True
        self.assertEqual(cleanup.cleanup_sampling_buffers()['cast_buffers'], 'unsupported')
        self.mm.reset_cast_buffers = self.reset
        cleanup.cleanup_segment_vram(unload_models=True)
        self.assertLess(self.events.index('reset'), self.events.index('unload'))
        self.events.clear()
        cleanup.cleanup_segment_vram(enabled=False)
        self.assertEqual(self.events, [])

    def test_old_host_missing_memory_module_still_drains_without_reset(self):
        self.mm.reset_cast_buffers = mock.Mock()
        with mock.patch.dict(sys.modules, {'comfy.memory_management': None}):
            result = cleanup.cleanup_sampling_buffers()
        self.assertEqual(result['prefetch'], 'cleared')
        self.assertEqual(result['cast_buffers'], 'not_applicable')
        self.mm.reset_cast_buffers.assert_not_called()

    def test_host_probe_deduplicates_shared_state_without_retaining_models(self):
        self.execute(NS(seed=1), None, None, None, {'samples': f.torch.ones(1)})
        self.mm.current_loaded_models.append(NS(model=self.patcher))
        with mock.patch.object(f.torch.cuda, 'is_initialized', return_value=False):
            result = diag.host_memory_snapshot()
        self.assertEqual(len(result['dynamic_models']), 1)
        self.assertEqual(result['patches_host_buffer_bytes'], 1792 * 1024 ** 2)
        self.assertEqual(result['patches_stack_entries'], 1)
        self.assertEqual(result['weights_registered_bytes'], 4096)
        self.assertIsNone(result['torch_host'])
        json.dumps(result)
        cleanup.cleanup_sampling_buffers()
        self.assertIsNone(self.refs[-1]())
        self.assertEqual(diag.host_memory_snapshot()['patches_host_buffer_bytes'], 0)

    def test_host_probe_bounds_bad_records_and_torch_allocator_is_separate(self):
        self.mm.current_loaded_models = [NS(model=NS(model=NS(dynamic_pins={'cuda:0': {'patches': ()}}),
                                                              load_device='cuda:0'))] * 70
        with mock.patch.object(f.torch.cuda, 'is_initialized', return_value=True), \
             mock.patch.object(f.torch.cuda.memory, 'host_memory_stats', create=True,
                               return_value={'allocated_bytes.current': 80, 'allocated_bytes.peak': 90}):
            result = diag.host_memory_snapshot()
        self.assertTrue(result['truncated'])
        self.assertTrue(result['errors'])
        self.assertEqual(result['torch_host'], {'allocated_bytes.current': 80})

    def test_sampler_diagnostics_have_pre_post_pin_bytes_and_phase(self):
        observer = NS(current_segment=3, record=mock.Mock())
        plan = NS(_active_memory_diagnostics=observer)
        snapshots = []
        observer.record.side_effect = lambda stage, segment, **kw: snapshots.append(
            (stage, segment, diag.host_memory_snapshot(), kw))
        token = diag.SAMPLING_PLAN.set(plan)
        try:
            self.sample(phase_name='refine_2')
        finally:
            diag.SAMPLING_PLAN.reset(token)
        self.assertEqual([r[0] for r in snapshots], ['sampler_execute_before', 'sampler_execute_after',
                                                  'sampler_buffers_before', 'sampler_buffers_after'])
        self.assertTrue(all(r[1] == 3 and r[3]['phase'] == 'refine_2' for r in snapshots))
        self.assertGreater(snapshots[2][2]['patches_registered_bytes'], 0)
        self.assertEqual(snapshots[3][2]['patches_registered_bytes'], 0)
        self.assertEqual(snapshots[3][3]['cleanup']['cast_buffers'], 'reset')

    def test_executor_context_restored_on_success_and_failure(self):
        outer = NS()
        token = diag.SAMPLING_PLAN.set(outer)
        try:
            for error in (False, True):
                def execute(plan, **kw):
                    self.assertIs(diag.SAMPLING_PLAN.get(), plan)
                    if error: raise RuntimeError('interrupted')
                    return 'done'
                with mock.patch.object(f.core, '_execute_director_plan_core', side_effect=execute):
                    if error:
                        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                            f.core.execute_director_plan_core(NS())
                    else:
                        self.assertEqual(f.core.execute_director_plan_core(NS()), 'done')
                self.assertIs(diag.SAMPLING_PLAN.get(), outer)
        finally:
            diag.SAMPLING_PLAN.reset(token)


if __name__ == '__main__':
    unittest.main()
