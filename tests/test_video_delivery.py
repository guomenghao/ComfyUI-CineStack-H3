"""Disk video output integration. Real FFmpeg; model/Comfy adapters are fixtures."""
import ast
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest import mock

import test_rolling_full_export as full

f = full.f
m = importlib.import_module(f.PKG + '.director.video_delivery')


class Blocker:
    def __init__(self, value): self.value = value


class FileVideo:
    def __init__(self, path): self.path = path
    def get_components(self): raise AssertionError('Full video decoding forbidden')


class VideoDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.runner = full.RollingFullExportTests()
        self.runner.setUp()
        self.addCleanup(self.runner.doCleanups)
        graph_utils = ModuleType('comfy_execution.graph_utils')
        graph_utils.ExecutionBlocker = Blocker
        self.latest = ModuleType('comfy_api.latest')
        self.latest.InputImpl = NS(VideoFromFile=FileVideo)
        self.adapter = mock.patch.dict(sys.modules, {'comfy_execution.graph_utils': graph_utils,
                                                     'comfy_api.latest': self.latest})
        self.adapter.start(); self.addCleanup(self.adapter.stop)

    def outputs(self, plan):
        old = tuple(object() for _ in range(8))
        # Delivery must never open the MP4 or materialize frames; only path wrappers.
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('video read')):
            result = m.finalize_video_delivery(plan, old)
        self.assertEqual(result['result'][:8], old)
        json.dumps(result['ui'])
        return result

    def test_first_only_full_exports_one_complete_video_and_blocks_final(self):
        plan = self.runner.build()
        self.runner.execute(plan)
        result = self.outputs(plan)
        self.assertEqual(len(result['result']), 10)
        self.assertTrue(result['result'][8].path.endswith('timeline_first_pass.mp4'))
        self.assertIsInstance(result['result'][9], Blocker)
        rows = result['ui']['cinestack_videos']
        self.assertEqual((rows[0]['scope'], rows[0]['complete']), ('timeline', True))
        self.assertEqual(rows[0]['type'], 'output')
        self.assertFalse(rows[1]['available'])
        self.assertEqual(self.runner.pixels(Path(result['result'][8].path)).shape[0], 25)

    def test_partial_second_exports_both_full_stages_without_sampling_other_segments(self):
        base = self.runner.build(mode='legacy')
        base.refine.update(confirm_first_pass=False, refine_only=False)
        self.runner.execute(base)
        plan = self.runner.build(mode='refine_only', selected={2})
        first, second = [], []
        with mock.patch.object(f.core, 'concat_continuous_chunks', side_effect=AssertionError('full RGB concat')):
            self.runner.execute(plan, first, second)
        self.assertEqual((first, second), ([], [300]))
        result = self.outputs(plan)
        self.assertTrue(all(isinstance(x, FileVideo) for x in result['result'][8:]))
        self.assertTrue(all(row['scope'] == 'timeline' and row['complete'] for row in result['ui']['cinestack_videos']))
        for video in result['result'][8:]:
            self.assertEqual(self.runner.pixels(Path(video.path)).shape[0], 25)
        manifest = self.runner.manifest(plan)
        self.assertTrue(all('first' in row and 'final' in row for row in manifest['full_export']['segments']))

    def test_face_only_final_preserves_true_first_pass_comparison(self):
        plan = self.runner.build(seeds=(100,), mode='legacy')
        plan.refine['enabled'] = False
        plan.face_refine = {'enabled': True}
        face = importlib.import_module(f.PKG + '.director.face_refine.runtime')
        with mock.patch.object(face, 'apply_segment_face_refine',
                               side_effect=lambda **kw: (kw['frames'] + .5, 'face refined')):
            self.runner.execute(plan, _decode_av_latent=lambda *a, **kw: (f.torch.full((5,32,32,3), .2), None))
        result = self.outputs(plan)
        first = self.runner.pixels(Path(result['result'][8].path))
        final = self.runner.pixels(Path(result['result'][9].path))
        self.assertLess(float(first.mean()), .3)
        self.assertGreater(float(final.mean()), .6)
        self.assertEqual(first.shape, final.shape)

    def test_segment_scope_only_delivers_selected_ranges(self):
        plan = self.runner.build(selected={2})
        plan.export_mode = plan.raw['output']['exportMode'] = 'segments'
        self.runner.execute(plan)
        result = self.outputs(plan)
        self.assertTrue(result['result'][8].path.endswith('/first_pass.mp4'))
        self.assertEqual(self.runner.pixels(Path(result['result'][8].path)).shape[0], 5)
        self.assertEqual(result['ui']['cinestack_videos'][0]['scope'], 'selected')

    def test_missing_unselected_first_video_does_not_fake_complete_preview_or_resample(self):
        base = self.runner.build(mode='legacy'); base.refine.update(confirm_first_pass=False, refine_only=False)
        self.runner.execute(base)
        index = self.runner.index(); data = json.loads(index.read_text())
        del data['segments']['0']['first']
        index.write_text(json.dumps(data))
        plan = self.runner.build(mode='refine_only', selected={2})
        first, second = [], []; self.runner.execute(plan, first, second)
        result = self.outputs(plan)
        self.assertEqual((first, second), ([], [300]))
        self.assertIsInstance(result['result'][8], Blocker)
        self.assertIsInstance(result['result'][9], FileVideo)
        self.assertIn('第 1 段', result['ui']['cinestack_videos'][0]['reason'])

    def test_normal_workflow_preserves_old_outputs_and_clears_previous_ui(self):
        plan = self.runner.build(); plan.raw['output']['rollingGeneration'] = False
        plan._rolling_video_results = [{'stage': 'first', 'available': True, 'path': 'stale.mp4'}]
        result = self.outputs(plan)
        self.assertEqual(result['ui']['cinestack_videos'], [])
        self.assertTrue(all(isinstance(x, Blocker) for x in result['result'][8:]))

    def test_older_host_keeps_download_preview_with_explicit_video_port_warning(self):
        plan = self.runner.build(); self.runner.execute(plan)
        del self.latest.InputImpl
        result = self.outputs(plan)
        self.assertIsInstance(result['result'][8], Blocker)
        row = result['ui']['cinestack_videos'][0]
        self.assertTrue(row['available'])
        self.assertIn('更新 ComfyUI', row['port_warning'])

    def test_unavailable_or_external_file_is_not_exposed_and_partial_is_labeled(self):
        output = Path(self.runner.runner.case.output)
        path = output / 'part.mp4'; path.write_bytes(b'file metadata fixture')
        run = NS(store=None, full_export=None, merged={'first': {'path': str(path), 'complete': False}})
        rows = m.rolling_video_results(run)
        self.assertTrue(rows[0]['available']); self.assertFalse(rows[0]['complete'])
        run.merged['first']['path'] = str(output.parent / 'outside.mp4')
        self.assertFalse(m.rolling_video_results(run)[0]['available'])
        run.merged['first']['path'] = str(output / 'gone.mp4')
        self.assertFalse(m.rolling_video_results(run)[0]['available'])

    def test_real_director_execute_returns_ui_and_video_while_images_stay_blocked(self):
        plan = self.runner.build()
        env = {"__package__": f.PKG + '.nodes', "ExecutionBlocker": Blocker,
               "prepare_director_plan": lambda **kw: plan,
               "execute_director_plan_core": lambda plan, **kw: self.runner.execute(plan)}
        common = ast.parse((f.ROOT / 'nodes/director_common.py').read_text())
        finalize = next(n for n in common.body if isinstance(n, ast.FunctionDef) and n.name == 'finalize_director_outputs')
        tree = ast.parse((f.ROOT / 'nodes/director.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        execute = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
        exec(compile(ast.Module(body=[finalize, execute], type_ignores=[]), 'director_fixture', 'exec'), env)
        result = env['execute'](None, model=object(), video_vae=object(), audio_vae=None, clip=object(),
                                task_type='t2v', global_prompt='', frame_rate=24, width=32, height=32,
                                ref_max_size=32, total_frames=25, timeline_data='{}')
        self.assertEqual(len(result['result']), 10)
        self.assertTrue(all(isinstance(result['result'][i], Blocker) for i in (0,1,4,6,7)))
        self.assertIsInstance(result['result'][8], FileVideo)
        self.assertEqual(result['result'][3], 25)
        self.assertEqual(result['ui']['cinestack_videos'][0]['filename'], 'timeline_first_pass.mp4')

    def test_schema_appends_video_without_changing_original_slots_or_inputs(self):
        tree = ast.parse((f.ROOT / 'nodes/director.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in cls.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in ('RETURN_TYPES', 'RETURN_NAMES', 'OUTPUT_IS_LIST')}
        self.assertEqual(values['RETURN_NAMES'][:8], ('images','audio','fps','frame_count','source_images','report','images_pre_refine','images_pre_face_refine'))
        self.assertEqual(values['RETURN_TYPES'][8:], ('VIDEO','VIDEO'))
        self.assertEqual(values['OUTPUT_IS_LIST'], (True,True,False,False,True,False,True,True,False,False))


if __name__ == '__main__': unittest.main()
