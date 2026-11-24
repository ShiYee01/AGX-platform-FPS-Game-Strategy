"""V3 behavior checks: climbable routes, informed retakes and fire gating.

These exercise decisions on hand-made observations; they do not simulate
physics, collisions or match results.
"""
import math
import unittest
from test_agent_objective_memory import agent, observation, player


def graph(nodes, edges):
    return {'sites': [{'id': 'A', 'center': nodes['G'], 'radius': 4.}],
            'nav': {'nodes': [{'id': k, 'position': v} for k, v in nodes.items()],
                    'edges': [{'from': a, 'to': b, 'kind': kind} for a, b, kind in edges]}}


def enemy(x, y, z=0., crouch=False):
    return {'x': x, 'y': y, 'z': z, 'parts': ['chest', 'head', 'abdomen'],
            'crouch': crouch, 'seat': 7}


class RouteTests(unittest.TestCase):
    def test_unclimbable_ledge_is_avoided_for_a_longer_flat_route(self):
        p = agent.Player()
        p.load_map(graph(
            {'S': [0., 0., 0.], 'BOX': [1., 0., 1.7], 'L': [0., 8., 0.], 'G': [2., 0., 0.]},
            [('S', 'BOX', 'source-adjacency'), ('BOX', 'G', 'source-adjacency'),
             ('S', 'L', 'source-adjacency'), ('L', 'G', 'source-adjacency')]))
        self.assertEqual([b for b, _ in p.edges['S']], ['L'])
        p.route([0., 0., 0.], [2., 0., 0.])
        self.assertEqual(p.path_ids[:3], ['S', 'L', 'G'])

    def test_ramps_and_drops_stay_usable(self):
        p = agent.Player()
        p.load_map(graph(
            {'S': [0., 0., 0.], 'R': [10., 0., 2.4], 'D': [10.5, 0., 0.], 'G': [12., 0., 0.]},
            [('S', 'R', 'walk'), ('R', 'D', 'drop'), ('D', 'G', 'walk')]))
        p.route([0., 0., 0.], [12., 0., 0.])
        self.assertEqual(p.path_ids[:4], ['S', 'R', 'D', 'G'])
        # A drop is one-way: the 2.4 m wall cannot be climbed back up.
        self.assertNotIn('R', [b for b, _ in p.edges['D']])

    def test_jumpable_step_costs_more_than_flat_ground(self):
        flat = agent.Player.edge_cost([0., 0., 0.], [1., 0., 0.], 'walk')
        step = agent.Player.edge_cost([0., 0., 0.], [1., 0., 1.], 'walk')
        self.assertGreater(step, flat + agent.JUMP_COST - .1)
        self.assertIsNone(agent.Player.edge_cost([0., 0., 0.], [1., 0., 1.6], 'walk'))

    def test_route_prefers_metres_over_hop_count(self):
        p = agent.Player()
        p.load_map(graph(
            {'S': [0., 0., 0.], 'FAR': [0., 30., 0.], 'N1': [3., 0., 0.],
             'N2': [6., 0., 0.], 'G': [9., 0., 0.]},
            [('S', 'FAR', 'walk'), ('FAR', 'G', 'walk'), ('S', 'N1', 'walk'),
             ('N1', 'N2', 'walk'), ('N2', 'G', 'walk')]))
        p.route([0., 0., 0.], [9., 0., 0.])
        self.assertEqual(p.path_ids[:4], ['S', 'N1', 'N2', 'G'])


class RetakeTests(unittest.TestCase):
    def test_far_beep_rules_out_the_near_site(self):
        p = player()
        o = observation(900, pos=(0., 0., 0.))
        o['me']['x'] = 1.          # A (10, 0) is now nearer than B (0, 10)
        o['sounds'] = [{'type': 'bomb_beep', 'direction': 'unknown', 'distance_band': 'far'}]
        p.act(o)
        # Both sites lie within 20 m, so "far" excludes none: nearest wins.
        self.assertEqual(p.retake_site, 0)
        p.sites[1] = dict(p.sites[1], center=[0., 40., 0.])
        p.retake_site = None
        p.act(o)
        self.assertEqual(p.retake_site, 1)
        self.assertEqual(p.goal, [0., 40., 0.])

    def test_empty_site_is_checked_briefly_then_the_other_is_tried(self):
        p = player()
        p.act(observation(900, pos=(9.5, 0., 0.)))
        self.assertEqual(p.retake_site, 0)
        p.act(observation(903, pos=(9.5, 0., 0.)))
        p.act(observation(933, pos=(9.5, 0., 0.)))
        self.assertIn(0, p.ruled_out_sites)
        p.act(observation(936, pos=(9.5, 0., 0.)))
        self.assertEqual(p.retake_site, 1)
        self.assertEqual(p.goal, [0., 10., 0.])

    def test_visible_bomb_still_overrides_retake_guess(self):
        p = player()
        p.act(observation(900, pos=(9.5, 0., 0.)))
        p.act(observation(903, position=[0., 10., 0.], pos=(9.5, 0., 0.)))
        self.assertEqual(p.goal, [0., 10., 0.])

    def test_new_round_forgets_ruled_out_sites(self):
        p = player()
        p.ruled_out_sites, p.bomb_band = {0}, 'far'
        p.act(observation(900, round_index=1, state='unknown'))
        self.assertFalse(p.ruled_out_sites)
        self.assertIsNone(p.bomb_band)


class FireGateTests(unittest.TestCase):
    def fight(self, p, tick, crouch=True, inaccuracy=0., target=(20., 0.), slot=0):
        o = observation(tick, state='unknown')
        o['me']['crouch'] = crouch
        rifle = {'ammo': 30, 'reserve': 90, 'reload_until': None,
                 'inaccuracy': inaccuracy, 'aim_punch': {}}
        o['me']['weapons'] = [rifle if slot == 0 else None, dict(rifle)]
        dx, dy = target
        o['me']['pitch'] = math.atan2(1.18 - 1.62 if not crouch else 1.18 - .95, math.hypot(dx, dy))
        o['visible'] = [enemy(dx, dy)]
        return p.act(o)

    def test_no_shot_until_crouch_has_finished(self):
        p = player()
        self.assertFalse(self.fight(p, 900, crouch=False)['fire'])
        self.assertTrue(self.fight(p, 903, crouch=True)['fire'])

    def test_standing_shot_allowed_if_crouch_never_registers(self):
        p = player()
        self.assertFalse(self.fight(p, 900, crouch=False)['fire'])
        self.assertFalse(self.fight(p, 906, crouch=False)['fire'])
        self.assertTrue(self.fight(p, 909, crouch=False)['fire'])

    def test_unsettled_spread_holds_fire_at_range(self):
        p = player()
        self.assertFalse(self.fight(p, 900, inaccuracy=.03)['fire'])
        self.assertTrue(self.fight(p, 903, inaccuracy=.008)['fire'])
        # Close targets accept more spread.
        self.assertTrue(self.fight(p, 906, inaccuracy=.03, target=(5., 0.))['fire'])

    def test_aim_tolerance_shrinks_with_distance(self):
        p = player()
        # 0.02 rad off: fine at 6 m, too wide at 30 m.
        self.assertTrue(self.fight(p, 900, target=(6., 6. * math.tan(.02)))['fire'])
        self.assertFalse(self.fight(p, 903, target=(30., 30. * math.tan(.02)))['fire'])

    def test_pistol_releases_trigger_between_shots(self):
        p = player()
        shots = [self.fight(p, t, slot=1, target=(5., 0.))['fire'] for t in (900, 903, 906, 909)]
        self.assertEqual(shots, [True, False, True, False])


class SpawnStaggerTests(unittest.TestCase):
    def test_last_seat_waits_three_seconds_not_six(self):
        p = player()
        o = observation(360 + 4 * 45 - 3, state='unknown')
        self.assertNotIn('move_forward', p.act(o))
        o = observation(360 + 4 * 45, state='unknown')
        self.assertIn('move_forward', p.act(o))


if __name__ == '__main__':
    unittest.main()
