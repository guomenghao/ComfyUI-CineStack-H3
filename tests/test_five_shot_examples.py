"""Release examples must use stable cache identities and file VIDEO wiring."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FiveShotExamplesTests(unittest.TestCase):
    def graphs(self):
        for mode in ('first_pass', 'refine_only'):
            yield mode, json.loads((ROOT / f'example_workflows/cinestack_five_shots_{mode}.json').read_text())

    def test_stages_keep_sampling_settings_and_cache_identity(self):
        payloads = []
        for mode, graph in self.graphs():
            director = next(n for n in graph['nodes'] if n['type'] == 'CineStackH3Director')
            values = director['widgets_values']
            self.assertEqual(values[5], 'fixed')
            self.assertEqual(values[18:26], [False, False, '性能', True, True, False,
                                             'raw', 'cinestack_five_shot_demo'])
            self.assertEqual(director['widgets_values_named']['cache_frames_codec'], 'raw')
            self.assertEqual(director['widgets_values_named']['timeline_data'], values[11])
            timeline = json.loads(values[11])
            self.assertEqual(timeline.pop('executionMode'), mode)
            self.assertTrue(timeline['output']['rollingGeneration'])
            self.assertEqual(timeline['output']['exportMode'], 'all')
            self.assertTrue(timeline['output']['continuityEnabled'])
            self.assertFalse(timeline['runSelectEnabled'])
            self.assertEqual([s['first_pass_seed'] for s in timeline['segments']],
                             [str(561215411 + i) for i in range(5)])
            self.assertEqual([s['continuityFromPrev'] for s in timeline['segments']], [False, True, True, True, True])
            self.assertIn('cinestack_five_shot_demo', values)
            payloads.append((director['id'], values[:11], timeline, values[12:]))
        self.assertEqual(*payloads, 'Switching example stages must not change first-pass fingerprints')

    def test_links_and_file_output_stages(self):
        for _, graph in self.graphs():
            nodes = {n['id']: n for n in graph['nodes']}
            self.assertNotIn('CreateVideo', [n['type'] for n in nodes.values()])
            for ident, src, slot, dst, input_slot, typ in graph['links']:
                output = nodes[src]['outputs'][slot]
                target = nodes[dst]['inputs'][input_slot]
                self.assertIn(ident, output['links'])
                self.assertEqual(target['link'], ident)
                self.assertEqual(output['type'], typ)
                self.assertEqual(target['type'], typ)
            videos = [link for link in graph['links'] if link[-1] == 'VIDEO']
            self.assertEqual({link[2] for link in videos}, {8, 9})
            for link in videos:
                self.assertEqual(nodes[link[3]]['type'], 'SaveVideo')
                self.assertEqual(nodes[link[3]]['widgets_values'][1:], ['auto', 'auto'])
            refine = next(n for n in nodes.values() if n['type'] == 'CineStackH3DirectorRefine')
            self.assertEqual(refine['widgets_values'][5:8], ['inherit', 0, 'fixed'])
            self.assertEqual(refine['widgets_values'][13:19], [True, False, False, 2, 128, False])
            self.assertIsNotNone(next(i['link'] for i in refine['inputs'] if i['name'] == 'sigmas'))


if __name__ == '__main__':
    unittest.main()
