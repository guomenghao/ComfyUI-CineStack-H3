"""CineStack branding must never rename ComfyUI's official H3 modules."""
import ast
from pathlib import Path
import sys
import types
from typing import Any
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = "comfy_extras.nodes_minimax_h3"


def source_definitions(path, names):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    body = [node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert len(body) == len(names)
    body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    namespace = {"Any": Any}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                 str(ROOT / path), "exec"), namespace)
    return namespace


class OfficialMiniMaxImportsTests(unittest.TestCase):
    def test_external_comfy_imports_have_no_cinestack_module_names(self):
        bad = []
        for path in ROOT.rglob("*.py"):
            if ".git" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and not node.level:
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [item.name for item in node.names]
                else:
                    continue
                for module in modules:
                    if module.startswith(("comfy.", "comfy_extras.")) and "cinestack" in module.lower():
                        bad.append((str(path.relative_to(ROOT)), node.lineno, module))
        self.assertEqual(bad, [], bad)

    def test_conditioning_loader_uses_real_official_module_identity(self):
        namespace = source_definitions("nodes/conditioning.py", {"_load_cineStack_nodes"})
        parent = types.ModuleType("comfy_extras")
        parent.__path__ = []
        official = types.ModuleType(OFFICIAL)
        official.MiniMaxH3ImageToVideo = object()
        official.MiniMaxH3ReferenceToVideo = object()
        with patch.dict(sys.modules, {"comfy_extras": parent, OFFICIAL: official}):
            actual = namespace["_load_cineStack_nodes"]()
        self.assertIs(actual[0], official.MiniMaxH3ImageToVideo)
        self.assertIs(actual[1], official.MiniMaxH3ReferenceToVideo)

    def test_r2v_and_keyframe_conditioning_dispatch_to_official_nodes(self):
        namespace = source_definitions("nodes/conditioning.py", {
            "_load_cineStack_nodes", "_unpack_positive_latent", "_reference_videos_dict",
            "run_cineStack_conditioning"})
        namespace["_reference_images_dict_from_kwargs"] = lambda _: None
        namespace["_task_hint"] = lambda *args: "fixture"
        parent = types.ModuleType("comfy_extras")
        parent.__path__ = []
        official = types.ModuleType(OFFICIAL)
        calls = []
        positive, latent = object(), {"samples": object()}

        class Reference:
            @staticmethod
            def execute(*, clip, prompt, width, height, length, ref_image_size,
                        vae, audio_vae, ref_images, ref_videos, ref_video_audios, ref_audios):
                calls.append(("r2v", prompt, width, height, length, ref_images, ref_image_size))
                return types.SimpleNamespace(args=(positive, latent))

        class Keyframes:
            @staticmethod
            def execute(*, clip, vae, prompt, width, height, length, first_frame, last_frame):
                calls.append(("keyframes", first_frame, last_frame))
                return positive, latent

        official.MiniMaxH3ImageToVideo = Keyframes
        official.MiniMaxH3ReferenceToVideo = Reference
        kwargs = dict(clip=object(), vae=object(), audio_vae=object(), prompt="reference shot",
                      width=864, height=480, length=158)
        refs = {"ref_image_0": object(), "ref_image_1": object()}
        with patch.dict(sys.modules, {"comfy_extras": parent, OFFICIAL: official}):
            result = namespace["run_cineStack_conditioning"](task_key="r2v", ref_images=refs, **kwargs)
            self.assertIs(result[0], positive)
            self.assertIs(result[2], latent)
            self.assertEqual(calls[0], ("r2v", "reference shot", 864, 480, 158, refs, "match"))
            for task in ("t2v", "i2v", "fl2v"):
                first = None if task == "t2v" else object()
                last = object() if task == "fl2v" else None
                result = namespace["run_cineStack_conditioning"](
                    task_key=task, first_frame=first, last_frame=last, **kwargs)
                self.assertIs(result[2], latent)
                self.assertEqual(calls[-1], ("keyframes", first, last))

    def test_conditioning_error_preserves_original_dependency_failure(self):
        namespace = source_definitions("nodes/conditioning.py", {"_load_cineStack_nodes"})
        failure = ImportError("missing fixture dependency")
        with patch("builtins.__import__", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                namespace["_load_cineStack_nodes"]()
        self.assertIn(OFFICIAL, str(caught.exception))
        self.assertIn(str(failure), str(caught.exception))
        self.assertIs(caught.exception.__cause__, failure)

    def test_sigma_shift_cache_import_and_reuse_with_official_node(self):
        namespace = source_definitions("director/core_sampling.py", {"_unpack_node_output", "ShiftedModelCache"})
        parent = types.ModuleType("comfy_extras")
        parent.__path__ = []
        official = types.ModuleType(OFFICIAL)
        calls = []

        class SigmaShift:
            @staticmethod
            def execute(model, video, audio):
                calls.append((model, video, audio))
                return types.SimpleNamespace(args=(object(),))

        official.MiniMaxH3SigmaShift = SigmaShift
        model = object()
        with patch.dict(sys.modules, {"comfy_extras": parent, OFFICIAL: official}):
            cache = namespace["ShiftedModelCache"]()
            first = cache.get(model, 12.0, 3.0)
            self.assertIs(cache.get(model, 12.0, 3.0), first)
            self.assertEqual(len(calls), 1)
            self.assertTrue(cache.holds(first))
            self.assertIsNot(cache.get(model, 10.0, 3.0), first)
            self.assertEqual(len(calls), 2)

    def test_sampling_and_selflift_import_official_sigma_shift(self):
        for relative in ("director/core_sampling.py", "director/selflift/sample.py"):
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            imports = [node.module for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom)
                       and any(item.name == "MiniMaxH3SigmaShift" for item in node.names)]
            self.assertTrue(imports, relative)
            self.assertTrue(all(module == OFFICIAL for module in imports), (relative, imports))

    def test_single_stage_dispatch_uses_official_shift_and_sampler(self):
        import torch

        namespace = source_definitions("director/core_sampling.py", {
            "_unpack_node_output", "_use_basic_guider", "_FixedNoise", "_ZeroNoise",
            "ShiftedModelCache", "sample_single_stage"})
        parent = types.ModuleType("comfy_extras")
        parent.__path__ = []
        official = types.ModuleType(OFFICIAL)
        custom = types.ModuleType("comfy_extras.nodes_custom_sampler")
        model, shifted, guider, sampler, noise = (object() for _ in range(5))
        latent = {"samples": torch.zeros(1)}
        sigmas = torch.tensor([1., .5, 0.])
        sampled = {"samples": torch.ones(1)}
        official.MiniMaxH3SigmaShift = types.SimpleNamespace(execute=Mock(return_value=(shifted,)))
        outputs = {"BasicScheduler": (sigmas,), "BasicGuider": (guider,), "CFGGuider": (object(),),
                   "KSamplerSelect": (sampler,), "RandomNoise": (noise,),
                   "SamplerCustomAdvanced": (sampled,)}
        for name, output in outputs.items():
            setattr(custom, name, types.SimpleNamespace(execute=Mock(return_value=output)))
        with patch.dict(sys.modules, {"comfy_extras": parent, OFFICIAL: official,
                                     custom.__name__: custom}):
            result = namespace["sample_single_stage"](
                model=model, positive=[], negative=[], latent=latent, seed=123,
                cfg=1.0, steps=4, sampler_name="res_multistep", scheduler="simple",
                shift_video=12.0, shift_audio=3.0)
        self.assertIs(result, sampled)
        official.MiniMaxH3SigmaShift.execute.assert_called_once_with(model, 12.0, 3.0)
        custom.BasicScheduler.execute.assert_called_once_with(shifted, "simple", 4, 1.0)
        custom.RandomNoise.execute.assert_called_once_with(123)
        custom.KSamplerSelect.execute.assert_called_once_with("res_multistep")
        custom.CFGGuider.execute.assert_not_called()
        args = custom.SamplerCustomAdvanced.execute.call_args.args
        self.assertIs(args[0], noise)
        self.assertIs(args[1], guider)
        self.assertIs(args[2], sampler)
        torch.testing.assert_close(args[3], sigmas)
        self.assertIs(args[4], latent)

    def test_continuity_recognizes_original_solattn_module_identity(self):
        namespace = source_definitions("director/h3_context_patches.py", {"_classify_layout_owner"})
        namespace["LAYOUT_MARKER"] = "_fixture_director_layout"

        def observer(self):
            pass

        observer.__module__ = "custom_nodes.sol_attn_minimax_v5"
        observer.__qualname__ = "_patch_packed_layout.<locals>.__init__"
        layout = type("PackedLayout", (), {"__init__": observer})
        layout.__module__ = "comfy.ldm.minimax.model"
        namespace["_mm"] = lambda: types.SimpleNamespace(PackedLayout=layout)
        self.assertEqual(namespace["_classify_layout_owner"](), "compatible_solattn")
        observer.__module__ = "custom_nodes.unknown_attention"
        self.assertEqual(namespace["_classify_layout_owner"](), "foreign_other")


if __name__ == "__main__":
    unittest.main()
