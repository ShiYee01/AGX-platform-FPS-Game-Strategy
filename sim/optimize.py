"""A tiny 2D route/visibility game, for local search and simplified self-play.

二维站位搜索：格子移动 + 线段遮挡；用本人日志校准所有时间参数。
"""
import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np

def astar(cells, origin, spacing, start, goal):
    """Search a 4-neighbour XY projection; empty cells remain unknown.

    多层压成 XY 的教学近似；不模拟跳跃、梯子、碰撞或正式通行判定。
    """
    heights = {}
    for x, y, z in cells:
        heights.setdefault((int(x), int(y)), float(z))
    def nearest(position):
        qx = (position[0]-origin[0])/spacing-.5
        qy = (position[1]-origin[1])/spacing-.5
        return min(heights, key=lambda p: (p[0]-qx)**2+(p[1]-qy)**2)
    first, last = nearest(start), nearest(goal)
    heuristic = lambda p: abs(p[0]-last[0])+abs(p[1]-last[1])
    queue, costs, parent = [(heuristic(first), 0, first)], {first: 0}, {first: None}
    while queue:
        _, cost, here = heapq.heappop(queue)
        if cost != costs[here]:
            continue
        if here == last:
            path = []
            while here is not None:
                path.append([origin[0]+(here[0]+.5)*spacing,
                             origin[1]+(here[1]+.5)*spacing, heights[here]])
                here = parent[here]
            return list(reversed(path))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            there = (here[0]+dx, here[1]+dy)
            if there in heights and cost+1 < costs.get(there, float('inf')):
                costs[there], parent[there] = cost+1, here
                heapq.heappush(queue, (cost+1+heuristic(there), cost+1, there))
    return []  # No route in this approximation / 近似网格不连通，不能声称正式不可达。


def segments(a, b, c, d):
    """Conservatively test segment intersection, including collinear touching."""
    def cross(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if any(max(a[i], b[i]) < min(c[i], d[i]) or max(c[i], d[i]) < min(a[i], b[i]) for i in (0, 1)):
        return False
    return cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0


def visible(a, b, polygons):
    """Use exported 2D contours, including points inside a contour.

    Height and weapon effects are omitted / 忽略高度与武器作用。
    """
    def inside(point, polygon):
        contained=False
        for i,p in enumerate(polygon):
            q=polygon[(i+1)%len(polygon)]
            if (p[1]>point[1]) != (q[1]>point[1]):
                x=p[0]+(point[1]-p[1])*(q[0]-p[0])/(q[1]-p[1])
                if point[0]<x:
                    contained=not contained
        return contained
    return not any(inside(a,p) or inside(b,p) or
                   any(segments(a,b,p[i],p[(i+1)%len(p)]) for i in range(len(p)))
                   for p in polygons)


class GridDuel:
    """Simultaneous 2D move-and-spot game; not a shooting or match simulator.

    Args:
        grid: Exported floor candidates.
        starts: Two route start points.
        polygons: Exported cover contours.
        speed: Student-fitted speed in metres/second.
        reaction: Student-chosen spotting duration in seconds.
    """

    def __init__(self, grid, starts, polygons, speed, reaction):
        self.origin, self.spacing = grid['origin_xy'], grid['cell_size_m']
        self.free = {(int(x),int(y)) for x,y,z in grid['cells']}
        self.starts = [self.cell(p) for p in starts]
        self.polygons, self.speed, self.reaction = polygons, speed, reaction
        self.reset()

    def cell(self, p):
        """Convert an exported world point back into a floor cell."""
        return tuple(int(round((p[i]-self.origin[i])/self.spacing-.5)) for i in (0,1))

    def point(self, cell):
        """Return a cell centre in world XY."""
        return [self.origin[i]+(cell[i]+.5)*self.spacing for i in (0,1)]

    def reset(self):
        """Reset only this student's local game state."""
        self.positions=list(self.starts)
        self.time=0.
        self.exposed=0.
        return [self.point(c) for c in self.positions]

    def step(self, actions):
        """Apply one stay/four-neighbour move per side simultaneously."""
        if len(actions)!=2 or any(tuple(a) not in ((0,0),(1,0),(-1,0),(0,1),(0,-1)) for a in actions):
            raise ValueError('Use two stay/four-neighbour actions')
        planned=[(p[0]+a[0],p[1]+a[1]) for p,a in zip(self.positions,actions)]
        self.positions=[q if q in self.free else p for p,q in zip(self.positions,planned)]
        dt=self.spacing/self.speed
        self.time+=dt
        points=[self.point(c) for c in self.positions]
        sight=visible(*points,self.polygons)
        self.exposed=self.exposed+dt if sight else 0.
        return dict(time_seconds=self.time,positions=points,visible=sight,
                    contact=self.exposed>=self.reaction)


def optimize(path, params, site='A'):
    """Search both sides' spawn routes and positions in an approximate 2D game.

    Args:
        path: Public map JSON (NPZ also contains the same geometry).
        params: Student-fitted move_speed_mps and reaction_seconds.
        site: A or B objective.
    """
    speed, reaction = params.get('move_speed_mps'), params.get('reaction_seconds')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in (speed, reaction)):
        raise ValueError('Supply YOUR positive fitted move_speed_mps and reaction_seconds')
    d = json.loads(path.read_text())
    grid = d['walkable_surface_candidates']
    goal = next(s['center'] for s in d['bombsites'] if s['id'] == site)
    polygons = [p['polygon_xy'] for p in d['wall_cover_contours']]
    routes = []
    for zone in d['spawn_zones']:
        start = zone['pads'][0]['position']
        route = astar(grid['cells'], grid['origin_xy'], grid['cell_size_m'], start, goal)
        routes.append(route)
    if not all(routes):
        return dict(approximation=True, reachable=False, reason='Grid disconnected; validate gaps in your logs / 候选网格不连通，须查本人日志')
    # Build a small minimax positioning game; each side responds to the other.
    # 采样路线站位，双方交替选最佳回应；这不是正式胜率或平台分数。
    candidates = [r[::max(1, len(r)//12)]+r[-1:] for r in routes]
    arrival = [np.array([math.dist(r[0][:2], p[:2])/speed for p in r]) for r in candidates]
    payoff = np.empty((len(candidates[0]), len(candidates[1])))
    for i, a in enumerate(candidates[0]):
        for j, b in enumerate(candidates[1]):
            sight = visible(a[:2], b[:2], polygons)
            exposure = reaction if sight else 0
            payoff[i,j] = -math.dist(a[:2], goal[:2])/speed + arrival[1][j]-arrival[0][i]-exposure
    attacker = int(np.argmax(payoff.min(axis=1)))
    defender = int(np.argmin(payoff[attacker]))
    duel=GridDuel(grid,[r[0] for r in routes],polygons,speed,reaction)
    rollout=None
    for step in range(1,max(len(r) for r in routes)):
        actions=[]
        for seat,route in enumerate(routes):
            target=duel.cell(route[min(step,len(route)-1)])
            here=duel.positions[seat]
            actions.append((target[0]-here[0],target[1]-here[1]))
        rollout=duel.step(actions)
        if rollout['contact']:
            break
    return dict(approximation=True, reachable=True, site=site, local_rollout=rollout,
                route_cells=[len(r) for r in routes],
                route_seconds=[(len(r)-1)*grid['cell_size_m']/speed for r in routes],
                attack_position=candidates[0][attacker], defend_position=candidates[1][defender],
                line_of_sight=visible(candidates[0][attacker][:2], candidates[1][defender][:2], polygons),
                local_objective=float(payoff[attacker,defender]), parameters=params)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('map', type=Path)
    p.add_argument('--params', type=Path, required=True)
    p.add_argument('--site', choices=('A','B'), default='A')
    args = p.parse_args()
    fitted = json.loads(args.params.read_text())
    print(json.dumps(optimize(args.map, fitted.get('parameters', fitted), args.site), allow_nan=False))
