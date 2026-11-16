"""Navigation behavior checks; these are not a physics or win-rate simulation."""
import copy
import math
import unittest
from test_agent_objective_memory import agent, observation, player


def obs(tick, pos=(0., 0., 0.), **kwargs):
    return observation(tick, state='unknown', pos=pos, **kwargs)


class NavigationTests(unittest.TestCase):
    def test_unreached_site_survives_multiple_old_timer_boundaries(self):
        p = player()
        for t in (1770, 1800, 3600, 5400):
            p.act(obs(t))
            self.assertEqual(p.patrol_index, 0)
            self.assertEqual(p.goal, [10., 0., 0.])

    def test_site_rotation_requires_arrival_and_eight_seconds_of_holding(self):
        p = player()
        p.act(obs(900))
        p.act(obs(1000, (9., 0., 0.)))
        for t in (1003, 1300, 1479):
            a = p.act(obs(t, (9., 0., 0.)))
            self.assertEqual(p.patrol_index, 0)
            self.assertNotIn('move_forward', a)
        p.act(obs(1480, (9., 0., 0.)))
        self.assertEqual(p.patrol_index, 1)
        self.assertEqual(p.goal, [0., 10., 0.])
        self.assertEqual(p.escapes, 0)

    def test_leaving_site_resets_the_hold_timer(self):
        p = player()
        p.act(obs(900, (9., 0., 0.)))
        p.act(obs(1200, (0., 0., 0.)))
        p.act(obs(1500, (9., 0., 0.)))
        p.act(obs(1800, (9., 0., 0.)))
        self.assertEqual(p.patrol_index, 0)
        p.act(obs(1980, (9., 0., 0.)))
        self.assertEqual(p.patrol_index, 1)

    def test_bomb_carrier_plants_without_rotating(self):
        p = player()
        for t in (900, 1800, 3600):
            o = obs(t, (9., 0., 0.))
            o['side'] = 'attack'
            o['me']['carrying_bomb'] = True
            self.assertEqual(p.act(o).get('use'), 'plant')
            self.assertEqual(p.patrol_index, 0)

    def test_sideways_wandering_is_not_route_progress(self):
        p = player()
        for t, y in ((900, .4), (921, -.4), (942, .4), (963, -.4)):
            p.act(obs(t, (0., y, 0.)))
        self.assertEqual(p.escapes, 1)
        self.assertGreater(p.escape_until, 963)

    def test_real_progress_does_not_start_recovery(self):
        p = player()
        for i, t in enumerate(range(900, 1081, 30)):
            p.act(obs(t, (i*.5, 0., 0.)))
        self.assertEqual(p.escapes, 0)

    def test_repeated_failure_avoids_edge_and_uses_an_alternate_route(self):
        p = player()
        p.load_map({
            'sites': [{'center': [20., 0., 0.], 'radius': 4.}],
            'nav': {'nodes': [
                {'id': n, 'position': v} for n, v in
                [('S', [0., 0., 0.]), ('A', [10., 0., 0.]),
                 ('B', [0., 6., 0.]), ('G', [20., 0., 0.])]],
                'edges': [{'from': a, 'to': b, 'kind': 'walk'}
                          for a, b in [('S', 'A'), ('A', 'G'),
                                       ('S', 'B'), ('B', 'G')]]}})
        for t in range(900, 1239, 3):
            p.act(obs(t))
        self.assertEqual(p.escapes, 3)
        self.assertIn(('S', 'A'), p.blocked_edges)
        self.assertEqual(p.goal, [20., 0., 0.])
        p.act(obs(1239))
        self.assertEqual(p.path_ids[0], 'B')
        # Bans are temporary, and round boundaries cannot inherit them.
        expiry = p.blocked_edges[('S', 'A')]
        p.route([0., 0., 0.], [20., 0., 0.], expiry)
        self.assertNotIn(('S', 'A'), p.blocked_edges)
        p.blocked_edges[('S', 'A')] = expiry + 900
        p.leg_failures['example'] = 3
        p.act(obs(4000, round_index=1))
        self.assertFalse(p.blocked_edges)
        self.assertFalse(p.leg_failures)

    def test_failed_entry_node_is_avoided_without_switching_objective(self):
        p = player()
        for t in range(900, 1239, 3):
            p.act(obs(t, (-2., 0., 0.)))
        self.assertIn('spawn', p.blocked_nodes)
        p.act(obs(1239, (-2., 0., 0.)))
        self.assertEqual(p.goal, [10., 0., 0.])
        self.assertNotIn('spawn', p.path_ids)

    def test_disconnected_route_waits_instead_of_charging_directly(self):
        p = player()
        p.edges = {n: [] for n in p.nodes}
        action = p.act(obs(900))
        self.assertEqual(p.goal, [10., 0., 0.])
        self.assertNotIn('move_forward', action)
        self.assertFalse(p.path)
        self.assertEqual(p.escapes, 0)

    def test_known_bomb_overrides_a_completed_patrol_hold(self):
        p = player()
        p.act(obs(900, (9., 0., 0.)))
        o = observation(1800, position=[0., 10., 0.], pos=(9., 0., 0.))
        p.act(o)
        self.assertEqual(p.patrol_index, 0)
        self.assertEqual(p.goal, [0., 10., 0.])
        self.assertIsNone(p.site_arrival_tick)

    def test_combat_pause_does_not_count_as_stuck_movement(self):
        p = player()
        p.act(obs(900))
        o = obs(1000)
        o['visible'] = [{'x': 10., 'y': 0., 'z': 0.,
                         'parts': ['chest'], 'crouch': False}]
        p.act(o)
        p.act(obs(1200))
        self.assertEqual(p.escapes, 0)

    def test_navigation_does_not_mutate_observation(self):
        p = player()
        for t in (900, 963, 1008, 1071, 1131, 1194, 1239):
            o = obs(t)
            before = copy.deepcopy(o)
            p.act(o)
            self.assertEqual(o, before)


if __name__ == '__main__':
    unittest.main()
