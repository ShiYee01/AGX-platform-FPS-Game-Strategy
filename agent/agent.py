"""FPS V3: climbable weighted routes, informed retakes and gated firing.

Keeps V1 bomb memory and V2 staged recovery. Strategy parameters below are
our own choices measured from archived matches, not platform rules.
"""
import math
import gc
import heapq

# Logged jumps peak about 1.44 m above the take-off floor (3,086 jumps,
# matches 01-18), so steeper rises than this cannot be climbed.
MAX_CLIMB = 1.4
JUMP_RISE = 0.55        # rises above this on a steep edge need a jump
STEEP = 0.6             # rise / horizontal run separating ledges from ramps
JUMP_COST = 4.0         # metres of detour we accept to avoid one jump
RETAKE_CHECK_TICKS = 30  # look around an empty site this long before leaving


def clip(value):
    return max(-1.0, min(1.0, value))


def distance(a, b):
    return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))


def angle(value):
    return (value + math.pi) % (2 * math.pi) - math.pi


class Player:
    def __init__(self):
        self.nodes, self.edges, self.sites = {}, {}, []
        self.pending_map = None
        self.path, self.goal = [], None
        self.round = None
        self.path_ids, self.path_from = [], None
        self.watch_key, self.best_distance, self.progress_tick = None, 0., 0
        self.blocked_edges, self.blocked_nodes, self.leg_failures = {}, {}, {}
        self.route_retry_tick = 0
        self.patrol_index, self.site_arrival_tick = 0, None
        self.escape_until, self.escape_yaw, self.escapes = 0, 0.0, 0
        self.recovery_jump = False
        self.planted_bomb_position, self.planted_bomb_fuse = None, None
        self.ruled_out_sites, self.retake_site = set(), None
        self.bomb_band, self.last_fire_tick = None, -99
        self.combat_start = None

    def load_map(self, row):
        self.sites = row["sites"]
        self.nodes = {n["id"]: n["position"]
                      for n in row["nav"]["nodes"]}
        self.edges = {key: [] for key in self.nodes}
        for edge in row["nav"]["edges"]:
            kind = edge["kind"]
            if kind == "ladder":
                continue
            pairs = [(edge["from"], edge["to"])]
            if kind == "walk":
                pairs.append((edge["to"], edge["from"]))
            for a, b in pairs:
                cost = self.edge_cost(self.nodes[a], self.nodes[b], kind)
                if cost is not None:
                    self.edges[a].append((b, cost))

    @staticmethod
    def edge_cost(a, b, kind):
        """Metres plus a jump penalty; None for a ledge we cannot climb."""
        run = math.hypot(b[0] - a[0], b[1] - a[1])
        rise = b[2] - a[2]
        steep = rise > STEEP * run
        if kind != "drop" and steep and rise > MAX_CLIMB:
            return None
        cost = math.sqrt(run * run + rise * rise)
        if steep and rise > JUMP_RISE:
            cost += JUMP_COST
        return cost

    def nearest_node(self, point, candidates):
        # Vertical offset counts double so a floor above or below loses.
        return min(candidates, key=lambda k: (
            (self.nodes[k][0] - point[0])**2 + (self.nodes[k][1] - point[1])**2
            + 4 * (self.nodes[k][2] - point[2])**2))

    def reset_navigation(self):
        self.path, self.path_ids, self.path_from = [], [], None
        self.goal, self.watch_key = None, None
        self.escape_until, self.route_retry_tick = 0, 0

    def pause_navigation(self):
        # Fighting, using an objective or holding a site is not failed movement.
        self.watch_key, self.escape_until = None, 0

    def route(self, start, goal, tick=0):
        self.path_ids, self.path_from = [], None
        if not self.nodes:
            self.path_ids = [None]
            return [goal]
        self.blocked_edges = {e: until for e, until in self.blocked_edges.items()
                              if until > tick}
        self.blocked_nodes = {n: until for n, until in self.blocked_nodes.items()
                              if until > tick}
        candidates = [n for n in self.nodes if n not in self.blocked_nodes]
        if not candidates:
            return []
        first = self.nearest_node(start, candidates)
        last = self.nearest_node(goal, candidates)
        # A* on metres (V2 used breadth-first hop counts, which preferred
        # short-cuts over unclimbable boxes on the CS2 maps).
        target = self.nodes[last]
        parent, best = {first: None}, {first: 0.}
        heap, done = [(distance(self.nodes[first], target), 0., first)], set()
        while heap:
            _, cost, here = heapq.heappop(heap)
            if here == last:
                break
            if here in done:
                continue
            done.add(here)
            for there, step in self.edges[here]:
                if there in self.blocked_nodes or (here, there) in self.blocked_edges:
                    continue
                total = cost + step
                if total < best.get(there, math.inf):
                    best[there], parent[there] = total, here
                    heapq.heappush(heap, (total + distance(self.nodes[there], target),
                                          total, there))
        if last not in parent:
            # A disconnected graph is not permission to run through a wall.
            return []
        ids, cursor = [], last
        while cursor is not None:
            ids.append(cursor)
            cursor = parent[cursor]
        ids.reverse()
        self.path_ids = ids + [None]
        return [self.nodes[n] for n in ids] + [list(goal)]

    def patrol_site(self, o):
        """Rotate only after arriving and observing the site for eight seconds."""
        site = self.sites[self.patrol_index % len(self.sites)]
        pos = [o['me'][k] for k in ('x', 'y', 'z')]
        radius = max(1., min(3., site['radius'] * .5))
        arrived = distance(pos, site['center']) < radius
        if not arrived:
            self.site_arrival_tick = None
        elif self.site_arrival_tick is None:
            self.site_arrival_tick = o['match_tick']
        elif o['match_tick'] - self.site_arrival_tick >= 480:
            self.patrol_index = (self.patrol_index + 1) % len(self.sites)
            self.site_arrival_tick = None
            site = self.sites[self.patrol_index]
            radius = max(1., min(3., site['radius'] * .5))
            arrived = distance(pos, site['center']) < radius
        return site, arrived

    def retake_target(self, o):
        """Pick a site to check while a planted bomb's position is unknown."""
        m = o["me"]
        pos = [m["x"], m["y"], m["z"]]
        for sound in o.get("sounds") or ():
            if str(sound.get("type", "")).startswith("bomb_beep"):
                self.bomb_band = sound.get("distance_band")
        options = [i for i in range(len(self.sites)) if i not in self.ruled_out_sites]
        if not options:
            self.ruled_out_sites = set()
            options = list(range(len(self.sites)))
        # Beep bands were checked against real plant positions in matches
        # 01-18: near < 8 m, mid < 20 m, far >= 20 m.
        def gap(i):
            return distance(pos, self.sites[i]["center"])
        if self.bomb_band in ("near", "mid"):
            heard = [i for i in options if gap(i) < 22 + self.sites[i]["radius"]]
        elif self.bomb_band == "far":
            heard = [i for i in options if gap(i) > 18 - self.sites[i]["radius"]]
        else:
            heard = options
        options = heard or options
        if self.retake_site not in options:
            # Nearest site first; on a tie keep the V2 patrol assignment.
            preferred = self.patrol_index % len(self.sites)
            self.retake_site = min(options, key=lambda i: (round(gap(i), 1), i != preferred))
            self.site_arrival_tick = None
        site = self.sites[self.retake_site]
        radius = max(1., min(3., site["radius"] * .5))
        if gap(self.retake_site) >= radius:
            self.site_arrival_tick = None
            return site, False
        if self.site_arrival_tick is None:
            self.site_arrival_tick = o["match_tick"]
        elif (o["match_tick"] - self.site_arrival_tick >= RETAKE_CHECK_TICKS
              and self.bomb_band != "near"):
            # Standing in the site without seeing the bomb: try the other one.
            self.ruled_out_sites.add(self.retake_site)
            self.retake_site, self.site_arrival_tick = None, None
        return site, True

    def remember_planted_bomb(self, bomb):
        """Keep only a planted position actually present in our observation."""
        previous = (self.planted_bomb_fuse, self.planted_bomb_position)
        if bomb["state"] != "planted":
            self.planted_bomb_position, self.planted_bomb_fuse = None, None
            return False
        fuse = bomb["fuse_end_tick"]
        if fuse != self.planted_bomb_fuse:
            self.planted_bomb_position = None
        self.planted_bomb_fuse = fuse
        if bomb.get("position") is not None:
            self.planted_bomb_position = list(bomb["position"])
        current = (self.planted_bomb_fuse, self.planted_bomb_position)
        return self.planted_bomb_position is not None and current != previous

    def buy(self, o):
        m = o["me"]
        if (o["side"] == "defend" and not m["has_kit"]
                and m["cash"] >= 400):
            return {"buy": "defusekit"}
        rifle = "ak47" if o["side"] == "attack" else "m4a1"
        price = 2700 if o["side"] == "attack" else 2900
        if m["weapons"][0] is None and m["cash"] >= price:
            return {"buy": rifle}
        if m["armor"] < 50 and m["cash"] >= 650:
            return {"buy": "armor"}
        return {}

    def combat(self, o, action, gun):
        m = o["me"]
        enemy = min(o["visible"], key=lambda e:
                    (e["x"]-m["x"])**2 + (e["y"]-m["y"])**2)
        dx, dy = enemy["x"]-m["x"], enemy["y"]-m["y"]
        heights = {"head": 1.64, "chest": 1.18, "abdomen": 0.88}
        part = next((p for p in ("chest", "head", "abdomen")
                     if p in enemy["parts"]), "chest")
        height = heights[part] * (0.6 if enemy["crouch"] else 1.0)
        eye = 0.95 if m["crouch"] else 1.62
        dz = enemy["z"] + height - m["z"] - eye
        punch = gun.get("aim_punch", {}) if gun else {}
        yaw = angle(math.atan2(-dy, dx) - m["yaw"]
                    - 2 * punch.get("yaw", 0.0))
        pitch = math.atan2(dz, max(0.1, math.hypot(dx, dy)))
        pitch -= m["pitch"] + 2 * punch.get("pitch", 0.0)
        ready = bool(gun and gun["ammo"]
                     and not gun["reload_until"])
        # Release the trigger between pistol shots.
        trigger = (action["weapon_slot"] == 0
                   or o["match_tick"] - self.last_fire_tick > 3)
        # Fire gate from archived shots (matches 02-18): shots taken with aim
        # error inside the target's angular size, settled spread and a
        # finished crouch hit 73% versus 50% for all recorded shots; shots
        # fired before the crouch registered hit 0 of 127.
        span = max(0.1, math.hypot(dx, dy))
        tolerance = max(.008, min(.04, .25 / span))
        settled = (gun.get("inaccuracy") or 0.) <= max(.01, .2 / span) if gun else False
        # Should a crouch never register (ladder, low ceiling), stand and shoot.
        if self.combat_start is None:
            self.combat_start = o["match_tick"]
        crouched = m["crouch"] or o["match_tick"] - self.combat_start >= 9
        fire = bool(ready and trigger and settled and crouched
                    and abs(yaw) < tolerance and abs(pitch) < tolerance)
        if fire:
            self.last_fire_tick = o["match_tick"]
        action.update(yaw_rate=clip(yaw / 0.15),
                      pitch_rate=clip(pitch / 0.1), crouch=True, fire=fire)
        return action

    def recovery_action(self, o, action):
        m = o["me"]
        yaw = angle(self.escape_yaw - m["yaw"])
        return dict(action, move_forward=.9 * math.cos(yaw),
                    move_right=-.9 * math.sin(yaw),
                    yaw_rate=clip(yaw / .15),
                    pitch_rate=clip(-m["pitch"] / .1), walk=False,
                    jump=bool(self.recovery_jump and m["grounded"]
                              and o["match_tick"] % 30 == 0))

    def move(self, o, goal, action):
        m = o["me"]
        pos = [m[k] for k in ("x", "y", "z")]
        tick = o["match_tick"]
        if self.goal != goal:
            self.reset_navigation()
            self.goal = list(goal)
        if distance(pos, goal) < .75:
            self.pause_navigation()
            return dict(action, yaw_rate=.15, walk=True)
        if tick < self.escape_until:
            return self.recovery_action(o, action)
        if not self.path and tick >= self.route_retry_tick:
            self.path = self.route(pos, goal, tick)
            self.watch_key = None
            if not self.path:
                self.route_retry_tick = tick + 30
        if not self.path:
            return dict(action, yaw_rate=.15, walk=True)
        # Navmesh samples can be above the actual foot position on a slope.
        while (len(self.path) > 1 and
               math.dist(pos[:2], self.path[0][:2]) < 1.0 and
               abs(pos[2] - self.path[0][2]) < 2.0):
            self.path.pop(0)
            self.path_from = self.path_ids.pop(0)
        point = self.path[0]
        dx, dy = point[0]-pos[0], point[1]-pos[1]
        heading = math.atan2(-dy, dx)
        yaw = angle(heading - m["yaw"])
        action.update(move_forward=.75 * math.cos(yaw),
                      move_right=-.75 * math.sin(yaw),
                      yaw_rate=clip(yaw / .15),
                      pitch_rate=clip(-m["pitch"] / .1), walk=False)
        # Small sideways motion alone does not demonstrate route progress.
        key = (self.path_from, self.path_ids[0], tuple(goal))
        remaining = distance(pos, point)
        if key != self.watch_key:
            self.watch_key, self.best_distance = key, remaining
            self.progress_tick = tick
        elif self.best_distance - remaining >= .35:
            self.best_distance, self.progress_tick = remaining, tick
        if tick - self.progress_tick > 60:
            attempts = self.leg_failures.get(key, 0) + 1
            self.leg_failures[key] = attempts
            self.escapes += 1
            turn = 1 if (o["seat"] + self.escapes) % 2 else -1
            stage = (attempts - 1) % 3
            self.escape_yaw = heading + (turn * math.pi / 2
                                        if stage == 1 else math.pi)
            self.recovery_jump = stage == 1
            self.escape_until = tick + (60 if stage == 1 else 45)
            self.watch_key = None
            if stage == 2:
                # After two local attempts, avoid this leg for 15 seconds.
                source, target = self.path_from, self.path_ids[0]
                if source is not None and target is not None:
                    self.blocked_edges[(source, target)] = tick + 900
                elif target is not None:
                    self.blocked_nodes[target] = tick + 900
                elif source is not None:
                    self.blocked_nodes[source] = tick + 900
                self.path, self.path_ids = [], []
                self.route_retry_tick = self.escape_until
            return self.recovery_action(o, action)
        if point[2] - pos[2] > .45 and math.hypot(dx, dy) < 1.8:
            action["jump"] = bool(m["grounded"] and tick % 24 == 0)
        return action

    def act(self, o):
        if "map" in o:
            self.pending_map = o["map"]
        # The opening observation is large. Build the navigation graph on a
        # later buy callback so JSON decoding and graph work use separate budgets.
        if self.pending_map is not None and ("map" not in o or o["phase"] == "live"):
            self.load_map(self.pending_map)
            self.pending_map = None
        if self.round != o["round_index"]:
            self.round = o["round_index"]
            self.reset_navigation()
            self.blocked_edges, self.blocked_nodes, self.leg_failures = {}, {}, {}
            self.escapes = 0
            self.patrol_index = o["round_index"] + o["seat"] % 2
            self.site_arrival_tick = None
            self.planted_bomb_position, self.planted_bomb_fuse = None, None
            self.ruled_out_sites, self.retake_site, self.bomb_band = set(), None, None
            self.last_fire_tick, self.combat_start = -99, None
        bomb = o["bomb"]
        new_bomb_target = self.remember_planted_bomb(bomb)
        if o["side"] == "defend" and new_bomb_target:
            # A newly learned objective overrides an old escape once. Later
            # recoveries for this same target must still be able to finish.
            self.reset_navigation()
            self.site_arrival_tick = None
        m = o["me"]
        if not m["alive"] or o["phase"] not in ("buy", "live"):
            return {}
        if o["phase"] == "buy":
            return self.buy(o)
        slot = 0 if m["weapons"][0] is not None else 1
        gun = m["weapons"][slot]
        action = {"weapon_slot": slot}
        if gun and gun["ammo"] == 0 and gun["reserve"]:
            action["reload"] = True
        pos = [m["x"], m["y"], m["z"]]
        site = self.sites[self.patrol_index % len(self.sites)]
        patrol = not m["carrying_bomb"]
        goal = list(site["center"])
        planted = bomb["state"] == "planted"
        bomb_position = bomb.get("position")
        if planted and o["side"] == "defend":
            bomb_position = self.planted_bomb_position
        if planted and bomb_position is not None:
            goal = list(bomb_position)
            patrol = False
        if o["side"] == "attack" and bomb["state"] == "world" and bomb.get("position"):
            goal = list(bomb["position"])
            patrol = False
            if distance(pos, goal) < 1.2:
                self.pause_navigation()
                return dict(action, use="pickup", pickup_id=bomb["id"])
        if (o["side"] == "defend" and planted
                and bomb_position is not None
                and distance(pos, goal) < 2.0):
            self.pause_navigation()
            return dict(action, use="defuse")
        radius = site["radius"] * 0.5
        at_site = distance(pos, site["center"]) < radius
        if m["carrying_bomb"] and at_site:
            self.pause_navigation()
            return dict(action, use="plant")
        if not o["visible"] or m["blind_ticks"]:
            self.combat_start = None
        if o["visible"] and not m["blind_ticks"]:
            self.pause_navigation()
            self.site_arrival_tick = None
            return self.combat(o, action, gun)
        if (o["side"] == "attack" and planted
                and distance(pos, goal) < 8):
            self.pause_navigation()
            return dict(action, yaw_rate=0.15, walk=True)
        if patrol and planted and o["side"] == "defend":
            # Bomb down somewhere unseen: check one site briefly, then the other.
            site, arrived = self.retake_target(o)
            goal = list(site["center"])
            if arrived:
                self.pause_navigation()
                return dict(action, yaw_rate=.15, walk=True)
        elif patrol:
            site, arrived = self.patrol_site(o)
            goal = list(site["center"])
            if arrived:
                self.pause_navigation()
                return dict(action, yaw_rate=.15, walk=True)
        # Give each teammate room to leave its spawn before entering a narrow route.
        if o["round_tick"] < 360 + (o["seat"] % 5) * 45:
            self.pause_navigation()
            return action
        return self.move(o, goal, action)


_player = Player()


def init(context):
    global _player
    # Observations and this policy use acyclic containers; reference counting
    # releases them without repeatedly scanning the large public map.
    gc.disable()
    _player = Player()


def act(observation):
    return _player.act(observation)
