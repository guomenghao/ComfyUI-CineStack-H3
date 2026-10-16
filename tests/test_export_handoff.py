"""Check post-inference ownership, not GPU memory estimates."""
import importlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import torch
import test_segment_seed_refine_only as f

h = importlib.import_module(f.PKG + '.director.export_handoff')
v = importlib.import_module(f.PKG + '.director.vram_cleanup')


class HandoffTests(unittest.TestCase):
    def test_output_views_keep_selected_order_geometry_and_sources_unchanged(self):
        a, b = torch.rand(3,4,6,3), torch.rand(5,2,4,3)
        originals = [a.clone(), b.clone()]
        merged = torch.zeros(8,4,6,3)
        merged[:3].copy_(a); merged[3:,1:3,1:5].copy_(b)
        views = h.merged_segment_views([a,b], merged, [b,a])
        self.assertEqual([tuple(x.shape) for x in views], [tuple(b.shape),tuple(a.shape)])
        for x in views:
            self.assertEqual(x.untyped_storage().data_ptr(), merged.untyped_storage().data_ptr())
        views[0].fill_(.75)
        torch.testing.assert_close(a, originals[0]); torch.testing.assert_close(b, originals[1])

    def test_release_drains_unloads_syncs_then_frees_captured_patchers(self):
        events = []
        class Patcher:
            def partially_unload_ram(self, amount):
                events.append('host_release'); return 100
        p = Patcher()
        records = [SimpleNamespace(model=p), SimpleNamespace(model=p)]
        def unload():
            events.append('unload'); records.clear()
        mm = SimpleNamespace(current_loaded_models=records, unload_all_models=unload,
                             soft_empty_cache=lambda: events.append('empty'))
        with patch.dict(sys.modules, {'comfy.model_management': mm}), \
             patch.object(v, 'cleanup_sampling_buffers', side_effect=lambda: events.append('drain') or {}), \
             patch.object(torch.cuda, 'is_available', return_value=True), \
             patch.object(torch.cuda, 'synchronize', side_effect=lambda: events.append('sync')):
            result = v.release_models_for_export()
        self.assertEqual(events, ['drain','unload','sync','host_release','empty'])
        self.assertEqual(result['released_host_bytes'], 100)

    def test_failed_drain_never_truncates_active_buffers(self):
        mm = SimpleNamespace(unload_all_models=lambda: self.fail('unsafe unload'))
        with patch.dict(sys.modules, {'comfy.model_management': mm}), \
             patch.object(v, 'cleanup_sampling_buffers', return_value={'cast_buffers': 'failed'}):
            self.assertEqual(v.release_models_for_export()['status'], 'buffer_cleanup_failed')
