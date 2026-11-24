"""Check V3 on archived observations (matches 01-18); this does not simulate a match.

Positions, enemies and outcomes stay those recorded with V0/V1. The check only
shows that V3 runs on real observations without exceptions or invalid actions,
how often its new rules would engage, and its local CPU cost.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

from check_fps_v1 import equivalent, validate

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT/'策略更新/V3-可达寻路与开火门限'
V3_SOURCE = ROOT/'agent/agent.py'
V2_SOURCE = UPDATE/'agent-v2.py'


def load(path):
    scope = {'__name__': 'fps_checked'}
    exec(compile(path.read_bytes(), str(path), 'exec'), scope)
    scope['init']({})
    return scope


def check(log):
    v2, v3 = load(V2_SOURCE), load(V3_SOURCE)
    p3 = v3['_player']
    route = p3.route
    route_calls, route_seconds, route_max = [0], [0.], [0.]

    def timed_route(*args, **kwargs):
        started = time.process_time()
        result = route(*args, **kwargs)
        spent = time.process_time() - started
        route_calls[0] += 1; route_seconds[0] += spent; route_max[0] = max(route_max[0], spent)
        return result
    p3.route = timed_route
    counts = Counter()
    cpu = first_act = max_act = 0.
    max_act_tick = None
    hits, fires = set(), set()
    events = log.parent/'public-events.jsonl'
    seat = None
    recorded_fire_ticks, v3_fire_ticks = [], []
    for raw in gzip.open(log, 'rb'):
        row = json.loads(raw)
        if not isinstance(row.get('observation'), dict):
            continue
        o = row['observation']; seat = o['seat']
        before_ruled = set(p3.ruled_out_sites)
        started = time.process_time()
        action = v3['act'](o)
        spent = time.process_time() - started
        if counts['decisions'] == 0:
            first_act = spent
        cpu += spent
        if spent > max_act:
            max_act, max_act_tick = spent, o['match_tick']
        validate(action)
        old = v2['act'](o)
        counts['decisions'] += 1
        counts['changed_vs_v2'] += not equivalent(old, action)
        recorded = row.get('action') or {}
        if recorded.get('fire') and o['visible']:
            counts['recorded_fire_decisions'] += 1
            recorded_fire_ticks.append(o['match_tick'])
        if action.get('fire'):
            counts['v3_fire_decisions'] += 1
            v3_fire_ticks.append(o['match_tick'])
        if old.get('fire') and not action.get('fire'):
            counts['v2_fire_held_by_v3_gate'] += 1
        live = o['phase'] == 'live' and o['me']['alive']
        if (live and o['side'] == 'defend' and o['bomb']['state'] == 'planted'
                and p3.planted_bomb_position is None and not o['visible']):
            counts['retake_unknown_position_decisions'] += 1
            counts['retake_band_' + str(p3.bomb_band)] += 1
        counts['retake_sites_ruled_out'] += len(p3.ruled_out_sites - before_ruled)
    if events.is_file():
        for line in open(events, 'rb'):
            e = json.loads(line)
            if e.get('player') == seat and e['type'] == 'hit':
                hits.add(e['match_tick'])
            if e.get('player') == seat and e['type'] == 'fire' and not e.get('pellet'):
                fires.add(e['match_tick'])

    def hit_rate(ticks):
        shot = [t for t in ticks if any(x in fires for x in range(t, t + 3))]
        hit = [t for t in shot if any(x in hits for x in range(t, t + 7))]
        return dict(recorded_shots=len(shot), recorded_hits=len(hit),
                    hit_rate=round(len(hit) / len(shot), 3) if shot else None)
    both = sorted(set(recorded_fire_ticks) & set(v3_fire_ticks))
    return dict(log=str(log.relative_to(ROOT)), **counts,
                recorded_fire_hit_rate=hit_rate(recorded_fire_ticks),
                recorded_shots_v3_would_also_fire=hit_rate(both),
                route_calls=route_calls[0], route_cpu_s=round(route_seconds[0], 4),
                route_max_ms=round(route_max[0] * 1000, 3),
                local_cpu_s=round(cpu, 3), local_first_act_ms=round(first_act * 1000, 3),
                local_max_act_ms=round(max_act * 1000, 3), local_max_act_tick=max_act_tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', nargs='*', type=Path)
    parser.add_argument('--output', type=Path, default=UPDATE/'固定观察验证结果.json')
    args = parser.parse_args()
    logs = args.logs or [next((ROOT/f'比赛日志/对局{n:02}').glob('training-*.jsonl.gz'))
                         for n in range(1, 19)]
    results = []
    for log in logs:
        result = check(log.resolve()); results.append(result)
        print(json.dumps({k: result[k] for k in ('log', 'decisions', 'changed_vs_v2', 'v3_fire_decisions',
                                                   'recorded_fire_decisions', 'retake_sites_ruled_out',
                                                   'local_cpu_s', 'local_max_act_ms')}, ensure_ascii=False),
              flush=True)
    total = Counter()
    for r in results:
        for k, v in r.items():
            if isinstance(v, int) and not isinstance(v, bool):
                total[k] += v
    shots = sum(r['recorded_fire_hit_rate']['recorded_shots'] for r in results)
    hit = sum(r['recorded_fire_hit_rate']['recorded_hits'] for r in results)
    kept = sum(r['recorded_shots_v3_would_also_fire']['recorded_shots'] for r in results)
    kept_hit = sum(r['recorded_shots_v3_would_also_fire']['recorded_hits'] for r in results)
    output = dict(
        kind='fixed_observation_check_not_simulation',
        code_sha256={'v2': hashlib.sha256(V2_SOURCE.read_bytes()).hexdigest(),
                     'v3': hashlib.sha256(V3_SOURCE.read_bytes()).hexdigest()},
        totals=dict(total), invalid_actions=0, exceptions=0,
        recorded_shots=dict(all=shots, hits=hit, hit_rate=round(hit / shots, 3) if shots else None,
                            v3_would_also_fire=kept, v3_kept_hits=kept_hit,
                            v3_kept_hit_rate=round(kept_hit / kept, 3) if kept else None),
        max_local_act_ms=max(r['local_max_act_ms'] for r in results),
        max_local_first_act_ms=max(r['local_first_act_ms'] for r in results),
        max_route_ms=max(r['route_max_ms'] for r in results),
        max_match_local_cpu_s=max(r['local_cpu_s'] for r in results),
        matches=results,
        limitations='Observations, positions and hits are recorded V0/V1 outcomes. V3 actions are '
                    'not applied to a game engine, so held shots are not replayed later and route '
                    'changes do not move the player. Hit rates describe recorded shots only. '
                    'Local timing is descriptive; the platform may be about 1.5x slower.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('totals', 'recorded_shots', 'max_local_act_ms',
                                             'max_local_first_act_ms', 'max_route_ms',
                                             'max_match_local_cpu_s')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
