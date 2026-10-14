"""Versioned browser tree: URL closure, source immutability and server lifecycle."""
import importlib
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
PKG = '_cinestack_asset_tests'
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, package)
assets = importlib.import_module(PKG + '.frontend_assets')


class FrontendAssetTests(unittest.TestCase):
    def test_discovery_and_transitive_imports_share_one_versioned_tree(self):
        bundle = assets.build_frontend_assets(ROOT / 'web/js', '0.6.2')
        try:
            discovered = list(Path(bundle.web_directory).rglob('*.js'))
            self.assertEqual(len(discovered), len(list((ROOT / 'web/js').glob('*.js'))))
            self.assertTrue(all(p.relative_to(bundle.web_directory).parts[0] == bundle.token for p in discovered))
            for prefix in ('https://host/', 'https://host/proxy/'):
                for name, data in bundle.files.items():
                    if not name.endswith('.js'):
                        continue
                    url = prefix + 'extensions/ComfyUI-CineStack-H3/' + bundle.token + '/' + name
                    for target in re.findall(r'''\bfrom\s+["']([^"']+)["']''', data.decode()):
                        resolved = urljoin(url, target)
                        if '/scripts/' in target:
                            self.assertIn(resolved, (prefix + 'scripts/app.js', prefix + 'scripts/api.js'))
                        else:
                            self.assertTrue(resolved.startswith(prefix + 'extensions/ComfyUI-CineStack-H3/' + bundle.token + '/'), resolved)
                            self.assertIn(resolved.rsplit('/', 1)[1], bundle.files)
        finally:
            bundle.directory.cleanup()

    def test_content_changes_and_version_changes_invalidate_all_module_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'cinestack_migration.js').write_text('export const value = 1;\n')
            original = assets.build_frontend_assets(source, '1.0.0')
            same = assets.build_frontend_assets(source, '1.0.0')
            version = assets.build_frontend_assets(source, '1.0.1')
            (source / 'cinestack_migration.js').write_text('export const value = 2;\n')
            content = assets.build_frontend_assets(source, '1.0.0')
            try:
                self.assertEqual(original.token, same.token)
                self.assertNotEqual(original.token, version.token)
                self.assertNotEqual(original.token, content.token)
                self.assertIn(b'value = 1', (Path(original.web_directory) / original.token / 'cinestack_migration.js').read_bytes())
            finally:
                for bundle in (original, same, version, content):
                    bundle.directory.cleanup()

    def test_runtime_snapshot_is_retained_and_source_tree_is_unchanged(self):
        before = {p.name: p.read_bytes() for p in (ROOT / 'web/js').glob('*.js')}
        bundle = assets.get_frontend_assets()
        self.assertIs(bundle, assets.get_frontend_assets())
        self.assertTrue(Path(bundle.web_directory).is_absolute())
        self.assertNotIn(str(ROOT), bundle.web_directory)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (ROOT / 'web/js').glob('*.js')})

    def test_nested_host_modules_and_static_assets_keep_correct_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source/'nested').mkdir()
            (source/'cinestack_migration.js').write_text('import "./nested/helper.js";')
            (source/'nested/helper.js').write_text('import {app} from "../../../scripts/app.js";\nconst api = import("../../../scripts/api.js");\nconst icon = new URL("./icon.svg", import.meta.url);')
            (source/'nested/icon.svg').write_text('<svg/>')
            bundle = assets.build_frontend_assets(source, '1.0.0')
            try:
                data = bundle.files['nested/helper.js'].decode()
                self.assertEqual(data.count('../../../../scripts/'), 2)
                self.assertIn('new URL("./icon.svg", import.meta.url)', data)
                self.assertEqual(bundle.files['nested/icon.svg'], b'<svg/>')
            finally:
                bundle.directory.cleanup()

    def test_missing_sources_or_version_fail_without_old_url_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            for version in ('', 'main', '1.0.0'):
                with self.assertRaises(ValueError):
                    assets.build_frontend_assets(Path(directory), version)


if __name__ == '__main__':
    unittest.main()
