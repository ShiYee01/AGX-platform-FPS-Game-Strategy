"""V4 behavior checks: full-speed movement, threat pre-aim, fire gate under fire.

Hand-made observations only; no physics, collision or match result is simulated.
"""
import math
import unittest
from test_agent_objective_memory import agent, observation, player


def world_heading(o, action):
    """Direction the move input pushes us in the world (V2 sign convention)."""
    return o['me']['yaw'] + math.atan2(-action['move_right'], action['move_forward'])


class FullSpeedTests(unittest.TestCase):
    def test_route_following_uses_full_input(self):
        p = player()
        a = p.act(observation(900, state='unknown'))
        self.assertAlmostEqual(math.hypot(a['move_forward'], a['move_right']), 1.0)

    def test_recovery_strength_is_unchanged(self):
        p = player()
        p.act(observation(900, state='unknown'))
        a = p.act(observation(963, state='unknown'))
        self.assertAlmostEqual(math.hypot(a['move_forward'], a['move_right']), .9)


class ThreatWatchTests(unittest.TestCase):
    def attack(self, tick, pos, map_id='molo-r3-v54'):
        o = observation(tick, state='held', pos=pos)
        o['side'], o['map_id'] = 'attack', map_id
        return o

    def test_attacker_faces_threat_while_walking_the_route(self):
        p = player()
        o = self.attack(900, (100., 18., 0.))
        a = p.act(o)
        threat = agent.THREATS['molo-r3-v54'][0]
        look = math.atan2(-(threat[1] - 18.), threat[0] - 100.)
        # The view turns toward the threat (north-east, up the B lane)...
        self.assertAlmostEqual(a['yaw_rate'], agent.clip(agent.angle(look - 0.) / .15))
        # ...while the legs still follow the route to the first waypoint.
        point = p.path[0]
        heading = math.atan2(-(point[1] - 18.), point[0] - 100.)
        self.assertAlmostEqual(agent.angle(world_heading(o, a) - heading), 0., places=6)
        self.assertAlmostEqual(math.hypot(a['move_forward'], a['move_right']), 1.0)

    def test_no_watch_out_of_range_on_unknown_maps_or_when_defending(self):
        p = player()
        self.assertIsNone(p.watch_point(self.attack(900, (0., 0., 0.)), [0., 0., 0.]))
        self.assertIsNone(p.watch_point(self.attack(900, (100., 18., 0.), 'dust2-cs2-v54'),
                                        [100., 18., 0.]))
        o = self.attack(900, (100., 18., 0.)); o['side'] = 'defend'
        self.assertIsNone(p.watch_point(o, [100., 18., 0.]))
        # Standing on the threat point itself: watch something else or nothing.
        self.assertIsNone(p.watch_point(self.attack(900, (108., 45., 0.)), [108., 45., 0.]))


class UnderFireTests(unittest.TestCase):
    def fight(self, p, tick, hp, inaccuracy):
        o = observation(tick, state='unknown')
        o['me'].update(hp=hp, crouch=True,
                       pitch=math.atan2(1.18 - .95, 20.))
        rifle = {'ammo': 30, 'reserve': 90, 'reload_until': None,
                 'inaccuracy': inaccuracy, 'aim_punch': {}}
        o['me']['weapons'] = [rifle, dict(rifle)]
        o['visible'] = [{'x': 20., 'y': 0., 'z': 0., 'parts': ['chest'],
                         'crouch': False, 'seat': 7}]
        return p.act(o)

    def test_spread_gate_is_waived_right_after_taking_damage(self):
        p = player()
        self.assertFalse(self.fight(p, 900, 100., .03)['fire'])
        self.assertTrue(self.fight(p, 903, 80., .03)['fire'])
        # Half a second without new damage restores the V3 gate.
        self.assertTrue(self.fight(p, 930, 80., .03)['fire'])
        self.assertFalse(self.fight(p, 936, 80., .03)['fire'])

    def test_new_round_forgets_damage(self):
        p = player()
        self.fight(p, 900, 100., 0.)
        self.fight(p, 903, 50., 0.)
        o = observation(906, state='unknown', round_index=1)
        o['me']['hp'] = 100.
        p.act(o)
        self.assertEqual(p.hurt_tick, -99)
        self.assertEqual(p.last_hp, 100.)


if __name__ == '__main__':
    unittest.main()
