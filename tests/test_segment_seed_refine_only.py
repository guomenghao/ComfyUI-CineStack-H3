# Modified for CineStack on 2026-10-13; see CHANGELOG.md and NOTICE.
"""CPU integration checks of production planning/cache/executor code.

Only ComfyUI host adapters and GPU sampling/decoding are replaced. Real JSON
plans, cache metadata, torch AV payloads and the executor control flow run.
Run: python -m unittest discover -s tests -p 'test_segment_seed_refine_only.py' -v
"""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import torch

ROOT = Path(__file__).resolve().parents[1]
PKG = '_h3_seed_tests'
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules[PKG] = package
# Do not import the plugin's root __init__: it registers live ComfyUI nodes.
if 'folder_paths' not in sys.modules:
    folder_paths = types.ModuleType('folder_paths')
    folder_paths.folder_names_and_paths = {}
    folder_paths.get_folder_paths = lambda _name: []
    sys.modules['folder_paths'] = folder_paths
if 'comfy.utils' not in sys.modules:
    comfy = types.ModuleType('comfy')
    comfy.__path__ = []
    utils = types.ModuleType('comfy.utils')
    def upscale(tensor, width, height, *_args):
        return torch.nn.functional.interpolate(tensor, size=(height, width), mode='nearest')
    utils.common_upscale = upscale
    comfy.utils = utils
    sys.modules['comfy'] = comfy
    sys.modules['comfy.utils'] = utils

plan_module = importlib.import_module(PKG + '.director.plan')
cache = importlib.import_module(PKG + '.director.segment_cache')
core = importlib.import_module(PKG + '.director.executor_core')
seed_module = importlib.import_module(PKG + '.director.segment_seed')
refine_pack = importlib.import_module(PKG + '.director.refine_pack')
pack_module = importlib.import_module(PKG + '.director.pack')
groups = importlib.import_module(PKG + '.director.external_groups')


class SegmentSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        fp = sys.modules['folder_paths']
        fp.get_output_directory = lambda: str(self.output)
        fp.get_input_directory = lambda: str(self.output)
        fp.get_temp_directory = lambda: str(self.output)

    def build(self, seeds=(100, 100, 200, 100, 100), task='t2v'):
        rows = [{'id': f'g{i}', 'durationSec': .2, 'prompt': f'clip {i}',
                 **({'first_pass_seed': str(seed)} if seed is not None else {})}
                for i, seed in enumerate(seeds)]
        raw = {'version': 5, 'timelineMode': 'prompt_batch', 'editMode': 'segment',
               'frameRate': 24, 'segments': rows, 'global': {'taskType': task},
               'output': {'mode': 'fixed', 'width': 32, 'height': 32,
                          'audioMode': 'mute', 'exportMode': 'all'}}
        if task == 'fl2v':
            raw['timelineMode'] = 'fl2v'
            raw['shots'] = rows
        plan = plan_module.build_director_plan(json.dumps(raw), global_task_type=task,
                global_prompt='', total_frames=25, frame_rate=24, width=32, height=32,
                ref_max_size=32)
        plan.sample_seed = 999
        plan.sample_sampler = 'res_multistep'
        plan.sample_scheduler = 'simple'
        plan.refine = {'enabled': True, 'mode': 'refine', 'refine_only': True,
                       'skip_fl2v': False, 'sigmas_parsed': (1., .5, 0.),
                       'sigmas_tensor': torch.tensor([1., .5, 0.]), 'has_sigmas_tensor': True}
        return plan

    def store(self, plan, indices=None):
        for seg in plan.segments:
            if indices is None or seg.index in indices:
                cache.save_first_pass_cache('fixture', seg, plan,
                    av_latent={'samples': torch.zeros(1, 2, 1, 2, 2)})

    def execute(self, plan, first=None, second=None, **patches):
        latent = {'samples': torch.zeros(1, 2, 1, 2, 2)}
        def sample(**kwargs):
            if first is not None: first.append(kwargs['seed'])
            return kwargs['latent']
        def refine(_plan, _seg, **kwargs):
            if second is not None: second.append(kwargs['seed'])
            return kwargs['samples'], 'refined'
        replacements = {'run_cineStack_conditioning': mock.Mock(return_value=([], [], latent, 'test')),
                        'sample_single_stage': mock.Mock(side_effect=sample),
                        'apply_segment_refine': mock.Mock(side_effect=refine),
                        '_decode_av_latent': mock.Mock(return_value=(torch.zeros(5, 32, 32, 3), None)),
                        **patches}
        with mock.patch.multiple(core, **replacements):
            result = core.execute_director_plan_core(plan, node_id='fixture', model=object(),
                     vae=object(), audio_vae=None, clip=object(), seed=999,
                     clear_vram_between_segments=False)
        return result

    def test_seed_zero_uint64_and_invalid_inputs(self):
        self.assertEqual(seed_module.parse_segment_seed('0'), 0)
        self.assertEqual(seed_module.parse_segment_seed(str((1 << 64) - 1)), (1 << 64) - 1)
        self.assertIsNone(seed_module.parse_segment_seed(''))
        for invalid in [True, -1, 1.5, '1.5', '1e3', 'abc', str(1 << 64)]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                seed_module.parse_segment_seed(invalid)

    def test_old_workflow_inherits_and_keeps_original_fingerprint_schema(self):
        plan = self.build((None,))
        self.assertIsNone(plan.segments[0].first_pass_seed)
        self.assertEqual(seed_module.resolve_segment_seed(plan.segments[0], plan), 999)
        self.assertEqual(cache.first_pass_cache_fingerprint(plan.segments[0], plan)['seed'], 999)
        self.assertNotIn('first_pass_seed', cache.first_pass_cache_fingerprint(plan.segments[0], plan))
        self.assertFalse(refine_pack.normalize_refine_pack({'enabled': True})['refine_only'])

    def test_plans_preserve_each_mode_and_pack_reconstruction(self):
        for task in ['t2v', 'r2v', 'fl2v', 'mixed']:
            plan = self.build((0, (1 << 64) - 1), task)
            self.assertEqual([s.first_pass_seed for s in plan.segments], [0, (1 << 64) - 1])
        raw = pack_module._group_json({'first_pass_seed': str((1 << 64) - 1)})
        self.assertEqual(raw['first_pass_seed'], str((1 << 64) - 1))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'asset_groups/01').mkdir(parents=True)
            (root / 'asset_groups/01/group.json').write_text(json.dumps(raw))
            timeline = pack_module._assemble_timeline(root, {'taskType': 'fl2v'})
            self.assertEqual(timeline['segments'][0]['first_pass_seed'], str((1 << 64) - 1))
            self.assertEqual(timeline['shots'][0]['first_pass_seed'], str((1 << 64) - 1))

    def test_mixed_seeds_all_refine_no_first_pass_even_without_confirm_toggle(self):
        plan = self.build()
        self.store(plan)
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [100, 100, 200, 100, 100])
        status = cache.inspect_first_pass_cache('fixture', plan)
        self.assertTrue(status['can_confirm_refine'])
        self.assertEqual([r['expected_seed'] for r in status['segments']], second)

    def test_later_mismatch_aborts_entire_batch_before_any_work_or_cache_pruning(self):
        plan = self.build()
        self.store(plan)
        plan.segments[4].prompt = 'changed'
        first, second = mock.Mock(), mock.Mock()
        prune = mock.Mock()
        with mock.patch.object(core, 'prune_segment_cache', prune):
            with self.assertRaisesRegex(ValueError, '第 5 段.*提示词'):
                self.execute(plan, sample_single_stage=first, apply_segment_refine=second)
        first.assert_not_called()
        second.assert_not_called()
        prune.assert_not_called()

    def test_missing_seed_mismatch_and_corrupt_payload_list_exact_segments(self):
        plan = self.build()
        self.store(plan, {0, 1, 2, 3})
        plan.segments[1].first_pass_seed = 42
        (cache._cache_dir('fixture') / 'seg_0002.pre.av.pt').write_bytes(b'broken')
        first = mock.Mock()
        with self.assertRaises(ValueError) as raised:
            self.execute(plan, sample_single_stage=first)
        message = str(raised.exception)
        self.assertIn('第 2 段', message)
        self.assertIn('缓存=100，当前=42', message)
        self.assertIn('第 3 段', message)
        self.assertIn('无法读取', message)
        self.assertIn('第 5 段', message)
        self.assertIn('缺少一采缓存文件', message)
        first.assert_not_called()

    def test_selection_only_validates_selected_segments(self):
        plan = self.build()
        plan.run_indices = frozenset({2})
        self.store(plan, {2})
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual(first, [])
        self.assertEqual(second, [200])

    def test_cache_disappears_after_preflight_never_falls_back_to_first_pass(self):
        plan = self.build((100,))
        self.store(plan)
        original = core.validate_refine_only_cache
        def remove_after_check(key, p):
            original(key, p)
            (cache._cache_dir(key) / 'seg_0000.pre.av.pt').unlink()
        first = mock.Mock()
        with mock.patch.object(core, 'validate_refine_only_cache', side_effect=remove_after_check):
            with self.assertRaisesRegex(ValueError, '仅二采已停止.*第 1 段'):
                self.execute(plan, sample_single_stage=first)
        first.assert_not_called()

    def test_normal_first_pass_uses_per_segment_seeds(self):
        plan = self.build((0, 200))
        plan.refine = None
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual(first, [0, 200])
        self.assertEqual(second, [])
        self.assertIsNotNone(cache.load_first_pass_cache('fixture', plan.segments[0], plan))

    def test_selflift_receives_segment_seed(self):
        plan = self.build((123,))
        plan.refine = None
        received = []
        def sample(**kw):
            received.append(kw['seed'])
            return kw['latent'], None
        with mock.patch.object(core, 'selflift_will_run', return_value=True), \
             mock.patch.object(core, 'sample_selflift_stage', side_effect=sample):
            self.execute(plan)
        self.assertEqual(received, [123])

    def test_refine_inherit_offset_independent(self):
        self.assertEqual(refine_pack.refine_seed_for({'seed_mode': 'inherit'}, 200), 200)
        self.assertEqual(refine_pack.refine_seed_for({'seed_mode': 'offset'}, 200, 2), 203)
        self.assertEqual(refine_pack.refine_seed_for({'seed_mode': 'independent', 'seed': 99}, 200), 99)

    def test_external_group_seed_priority_and_selection(self):
        plan = self.build((100, 100))
        packed = [groups.pack_i2v_group(prompt='a', first_pass_seed='0'),
                  groups.pack_i2v_group(prompt='b', first_pass_seed='200')]
        p = groups.build_plan_from_external_groups(packed, family='i2v',
                timeline_data=json.dumps(plan.raw), task_type='t2v', global_prompt='',
                total_frames=10, frame_rate=24, width=32, height=32, ref_max_size=32)
        self.assertEqual([s.first_pass_seed for s in p.segments], [0, 200])
        p.sample_seed = 999
        p.refine = plan.refine
        self.store(p)
        status = cache.inspect_first_pass_cache('fixture', p, external_groups=p.external_groups_witness)
        self.assertTrue(status['matches'])
        self.assertEqual([r['expected_seed'] for r in status['segments']], [0, 200])

    def test_old_confirm_mode_still_runs_first_then_refine(self):
        plan = self.build((None,))
        plan.refine['refine_only'] = False
        plan.refine['confirm_first_pass'] = True
        first, second = [], []
        self.execute(plan, first, second)
        self.assertEqual(first, [999])
        self.assertEqual(second, [])
        self.execute(plan, first, second)
        self.assertEqual(first, [999])
        self.assertEqual(second, [999])

    def test_explicit_same_seed_reuses_legacy_pre_cache(self):
        plan = self.build((None,))
        self.store(plan)
        plan.segments[0].first_pass_seed = 999
        self.assertIsNotNone(cache.load_first_pass_cache('fixture', plan.segments[0], plan))
        before = cache.segment_cache_fingerprint(plan.segments[0], plan)
        plan.segments[0].first_pass_seed = 123
        self.assertNotEqual(before, cache.segment_cache_fingerprint(plan.segments[0], plan))

    def test_video_edit_plans_preserve_seeds(self):
        for task in ['v2v', 'rv2v']:
            raw = {'timelineMode': 'video', 'editMode': 'segment', 'totalFrames': 5,
                   'video': {'frames': ['frame']}, 'global': {'taskType': task},
                   'output': {'mode': 'fixed', 'width': 32, 'height': 32},
                   'segments': [{'start': 0, 'length': 5, 'first_pass_seed': '0'}]}
            with mock.patch.object(plan_module, 'load_timeline_segment', return_value=torch.zeros(1, 32, 32, 3)):
                p = plan_module.build_director_plan(json.dumps(raw), global_task_type=task,
                    global_prompt='edit', total_frames=5, frame_rate=24, width=32, height=32, ref_max_size=32)
            self.assertEqual(p.segments[0].first_pass_seed, 0)

    def test_status_rejects_skip_and_latent_only_like_executor(self):
        plan = self.build((100,), 'fl2v')
        self.store(plan)
        plan.refine['skip_fl2v'] = True
        self.assertFalse(cache.inspect_first_pass_cache('fixture', plan)['can_confirm_refine'])
        plan.refine['skip_fl2v'] = False
        plan.refine['mode'] = 'latent_upscale'
        self.assertFalse(cache.inspect_first_pass_cache('fixture', plan)['can_confirm_refine'])

    def test_refine_widget_is_appended_and_old_default_is_false(self):
        comfy = sys.modules['comfy']
        samplers = types.ModuleType('comfy.samplers')
        samplers.KSampler = types.SimpleNamespace(SAMPLERS=['euler', 'res_multistep'], SCHEDULERS=['simple'])
        with mock.patch.dict(sys.modules, {'comfy.samplers': samplers}), mock.patch.object(comfy, 'samplers', samplers, create=True):
            node = importlib.import_module(PKG + '.nodes.director_refine').CineStackH3DirectorRefine
            optional = node.INPUT_TYPES()['optional']
            self.assertEqual(list(optional)[-1], 'refine_only')
            self.assertFalse(optional['refine_only'][1]['default'])
            pack, _, _ = node().pack()
            self.assertFalse(pack['refine_only'])

    def test_group_nodes_both_legacy_and_autogrow_apis(self):
        legacy = importlib.import_module(PKG + '.nodes.director_groups')
        self.assertEqual(legacy.CineStackH3DirectorGroupImageToVideo().pack(prompt='a', first_pass_seed='0')[0]['first_pass_seed'], 0)
        self.assertEqual(legacy.CineStackH3DirectorGroupReferenceToVideo().pack(prompt='a', first_pass_seed='200')[0]['first_pass_seed'], 200)
        def input_spec(name, **kwargs):
            return types.SimpleNamespace(name=name, **kwargs)
        value_type = types.SimpleNamespace(Input=input_spec)
        io = types.SimpleNamespace(ComfyNode=object, Schema=lambda **kw: types.SimpleNamespace(**kw),
            NodeOutput=lambda *args: args, Custom=lambda _name: types.SimpleNamespace(Output=input_spec),
            String=value_type, Float=value_type, Combo=value_type, Image=value_type, Audio=value_type,
            Autogrow=types.SimpleNamespace(Input=input_spec, TemplatePrefix=lambda **kw: kw))
        api = types.ModuleType('comfy_api'); api.__path__ = []
        latest = types.ModuleType('comfy_api.latest'); latest.io = io
        name = PKG + '.nodes.director_groups_v3'
        spec = importlib.util.spec_from_file_location(name, ROOT / 'nodes/director_groups.py')
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {'comfy_api': api, 'comfy_api.latest': latest, name: module}):
            spec.loader.exec_module(module)
            node = module.CineStackH3DirectorGroupReferenceToVideo
            self.assertEqual(node.define_schema().inputs[-1].name, 'first_pass_seed')
            self.assertEqual(node.execute(prompt='a', first_pass_seed='0')[0]['first_pass_seed'], 0)

    def test_bad_handoff_and_missing_sigmas_stop_without_first_pass(self):
        plan = self.build((100,))
        self.store(plan)
        (cache._cache_dir('fixture') / 'seg_0000.pre.handoff.json').write_text('broken')
        first = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'handoff'):
            self.execute(plan, sample_single_stage=first)
        first.assert_not_called()
        plan.refine['sigmas_tensor'] = None
        with self.assertRaisesRegex(ValueError, 'SIGMAS'):
            self.execute(plan, sample_single_stage=first)
        first.assert_not_called()

    def test_status_preserves_full_uint64_seed_text(self):
        plan = self.build(((1 << 64) - 1,))
        self.store(plan)
        row = cache.inspect_first_pass_cache('fixture', plan)['segments'][0]
        self.assertEqual(row['expected_seed_text'], '18446744073709551615')
        self.assertEqual(row['cached_seed_text'], '18446744073709551615')

    def test_empty_av_payload_is_rejected_before_sampling(self):
        plan = self.build((100,))
        self.store(plan)
        torch.save({'samples': torch.zeros(0)}, cache._cache_dir('fixture') / 'seg_0000.pre.av.pt')
        first = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'AV latent 格式无效'):
            self.execute(plan, sample_single_stage=first)
        first.assert_not_called()

    def test_only_refine_rejects_skipped_fl2v_and_latent_only(self):
        plan = self.build((100,), 'fl2v')
        self.store(plan)
        plan.refine['skip_fl2v'] = True
        with self.assertRaisesRegex(ValueError, 'skip_fl2v'):
            self.execute(plan)
        plan.refine['mode'] = 'latent_upscale'
        with self.assertRaisesRegex(ValueError, 'mode 为 refine 或 upscale'):
            self.execute(plan)


if __name__ == '__main__':
    unittest.main()
