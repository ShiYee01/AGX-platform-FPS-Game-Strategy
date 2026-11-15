"""Behavior checks for the first FPS update; no game engine is simulated."""
import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fps_agent_v1', ROOT/'agent/agent.py')
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

MAP = {
    'sites': [{'center': [10., 0., 0.], 'radius': 4.},
              {'center': [0., 10., 0.], 'radius': 4.}],
    'nav': {'nodes': [{'id': 'spawn', 'position': [0., 0., 0.]},
                      {'id': 'A', 'position': [10., 0., 0.]},
                      {'id': 'B', 'position': [0., 10., 0.]}],
            'edges': [{'from': 'spawn', 'to': 'A', 'kind': 'walk'},
                      {'from': 'spawn', 'to': 'B', 'kind': 'walk'}]},
}


def observation(tick=900, *, position=None, state='planted', fuse=4000,
                round_index=0, pos=(0., 0., 0.)):
    bomb = {'state': state, 'fuse_end_tick': fuse if state == 'planted' else None}
    if position is not None:
        bomb['position'] = list(position)
    return {
        'seat': 4, 'side': 'defend', 'phase': 'live',
        'round_index': round_index, 'round_tick': tick, 'match_tick': tick,
        'visible': [], 'bomb': bomb,
        'me': {'x': pos[0], 'y': pos[1], 'z': pos[2],
               'yaw': 0., 'pitch': 0., 'alive': True, 'cash': 0,
               'has_kit': True, 'armor': 100., 'carrying_bomb': False,
               'weapons': [None, {'ammo': 12, 'reserve': 24, 'reload_until': None}],
               'blind_ticks': 0, 'crouch': False, 'grounded': True},
    }


def player():
    p = agent.Player()
    # Exercise the opening map cache through the actual callbacks.
    opening = observation(0, state='unknown')
    opening['phase'] = 'buy'
    opening['map'] = copy.deepcopy(MAP)
    p.act(opening)
    del opening['map']
    opening['match_tick'] = opening['round_tick'] = 3
    p.act(opening)
    return p


class ObjectiveMemoryTests(unittest.TestCase):
    def test_hidden_position_keeps_route_across_patrol_boundary(self):
        p = player()
        p.act(observation(1770, position=[10., 0., 0.]))
        action = p.act(observation(1800))
        # The original patrol now selects B. A remembered A still points east.
        self.assertGreater(action['move_forward'], .7)
        self.assertAlmostEqual(action['move_right'], 0.)

    def test_new_legal_target_interrupts_an_existing_escape(self):
        p = player()
        p.act(observation(900, state='unknown'))
        escaping = p.act(observation(963, state='unknown'))
        self.assertAlmostEqual((escaping['move_forward']**2 +
                                escaping['move_right']**2)**.5, .9)
        action = p.act(observation(966, position=[0., 10., 0.]))
        self.assertGreater(action['move_right'], .7)
        self.assertAlmostEqual(action['move_forward'], 0., places=10)

    def test_hidden_but_remembered_nearby_bomb_can_request_defuse(self):
        p = player()
        p.act(observation(900, position=[10., 0., 0.]))
        action = p.act(observation(930, pos=(9., 0., 0.)))
        self.assertEqual(action.get('use'), 'defuse')

    def test_new_round_cannot_reuse_previous_bomb(self):
        p = player()
        p.act(observation(900, position=[10., 0., 0.]))
        action = p.act(observation(930, round_index=1, fuse=8000))
        self.assertNotEqual(action.get('use'), 'defuse')
        self.assertGreater(action['move_right'], .7)

    def test_changed_fuse_cannot_reuse_previous_bomb(self):
        p = player()
        p.act(observation(900, position=[0., 10., 0.]))
        action = p.act(observation(930, fuse=8000))
        self.assertGreater(action['move_forward'], .7)
        self.assertAlmostEqual(action['move_right'], 0.)

    def test_non_planted_state_clears_memory(self):
        for state in ('unknown', 'held', 'world'):
            with self.subTest(state=state):
                p = player()
                p.act(observation(900, position=[0., 10., 0.]))
                p.act(observation(930, state=state))
                action = p.act(observation(960))
                self.assertGreater(action['move_forward'], .7)
                self.assertAlmostEqual(action['move_right'], 0.)

    def test_unknown_planted_position_is_not_invented(self):
        p = player()
        action = p.act(observation(900))
        self.assertNotEqual(action.get('use'), 'defuse')
        # With no known coordinates this version still follows the original A route.
        self.assertGreater(action['move_forward'], .7)

    def test_same_target_does_not_cancel_subsequent_needed_recovery(self):
        for show_position in (True, False):
            with self.subTest(show_position=show_position):
                p = player()
                p.act(observation(900, position=[0., 10., 0.]))
                p.act(observation(963))
                action = p.act(observation(
                    966, position=[0., 10., 0.] if show_position else None))
                self.assertAlmostEqual((action['move_forward']**2 +
                                        action['move_right']**2)**.5, .9)

    def test_memory_does_not_change_the_supplied_observation(self):
        p = player()
        o = observation(900, position=[10., 0., 0.])
        before = copy.deepcopy(o)
        p.act(o)
        self.assertEqual(o, before)
        # Memory owns a copy, so a caller's later mutation cannot redirect it.
        o['bomb']['position'][0] = -100.
        action = p.act(observation(930, pos=(9., 0., 0.)))
        self.assertEqual(action.get('use'), 'defuse')


if __name__ == '__main__':
    unittest.main()
