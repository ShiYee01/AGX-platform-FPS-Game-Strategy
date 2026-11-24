"""Check V4 on archived observations; this does not simulate a match.

Reuses tools/check_fps_v3.py with V3 (snapshot) as the previous version and the
current entry point as V4, and also counts the two new V4 rules: decisions
that pre-aim a known threat point and decisions inside the under-fire window.
Positions and outcomes stay those recorded with V0/V1/V2.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import check_fps_v3 as base

ROOT = base.ROOT
UPDATE = ROOT/'策略更新/V4-全速移动与危险点预瞄'
V3_SOURCE = UPDATE/'agent-v3.py'
V4_SOURCE = ROOT/'agent/agent.py'


def check(log):
    counts = Counter()

    def instrument(player):
        watch, act = player.watch_point, player.act

        def counted_watch(o, pos):
            point = watch(o, pos)
            counts['threat_watch_decisions'] += point is not None
            return point

        def counted_act(o):
            action = act(o)
            if o['me'].get('alive') and o['match_tick'] - player.hurt_tick <= 30:
                counts['under_fire_decisions'] += 1
                counts['under_fire_fire_decisions'] += bool(action.get('fire'))
            return action
        player.watch_point, player.act = counted_watch, counted_act
    result = base.check(log, V3_SOURCE, V4_SOURCE, instrument)
    result = {('changed_vs_v3' if k == 'changed_vs_v2' else
               'v3_fire_held_by_v4' if k == 'v2_fire_held_by_v3_gate' else
               'v4_fire_decisions' if k == 'v3_fire_decisions' else
               'recorded_shots_v4_would_also_fire' if k == 'recorded_shots_v3_would_also_fire' else k): v
              for k, v in result.items()}
    result.update(counts)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', nargs='*', type=Path)
    parser.add_argument('--output', type=Path, default=UPDATE/'固定观察验证结果.json')
    args = parser.parse_args()
    logs = args.logs or [next((ROOT/f'比赛日志/对局{n:02}').glob('training-*.jsonl.gz'))
                         for n in range(1, 19)]
    results = []
    for log in logs:
        r = check(log.resolve()); results.append(r)
        print(json.dumps({k: r[k] for k in ('log', 'decisions', 'changed_vs_v3', 'v4_fire_decisions',
                                             'threat_watch_decisions', 'under_fire_decisions',
                                             'local_cpu_s', 'local_max_act_ms')}, ensure_ascii=False),
              flush=True)
    total = Counter()
    for r in results:
        for k, v in r.items():
            if isinstance(v, int) and not isinstance(v, bool):
                total[k] += v
    kept = [r['recorded_shots_v4_would_also_fire'] for r in results]
    allshots = [r['recorded_fire_hit_rate'] for r in results]
    shots = sum(x['recorded_shots'] for x in allshots); hits = sum(x['recorded_hits'] for x in allshots)
    ks = sum(x['recorded_shots'] for x in kept); kh = sum(x['recorded_hits'] for x in kept)
    output = dict(
        kind='fixed_observation_check_not_simulation',
        code_sha256={'v3': hashlib.sha256(V3_SOURCE.read_bytes()).hexdigest(),
                     'v4': hashlib.sha256(V4_SOURCE.read_bytes()).hexdigest()},
        totals=dict(total), invalid_actions=0, exceptions=0,
        recorded_shots=dict(all=shots, hits=hits, hit_rate=round(hits / shots, 3) if shots else None,
                            v4_would_also_fire=ks, v4_kept_hits=kh,
                            v4_kept_hit_rate=round(kh / ks, 3) if ks else None),
        max_local_act_ms=max(r['local_max_act_ms'] for r in results),
        max_route_ms=max(r['route_max_ms'] for r in results),
        max_match_local_cpu_s=max(r['local_cpu_s'] for r in results),
        matches=results,
        limitations='Recorded positions and hits from earlier versions; V4 actions (including its '
                    'faster movement and changed view direction) are not applied to a game '
                    'engine. Threat-watch counts show how often the rule would engage, not its effect.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('totals', 'recorded_shots', 'max_local_act_ms',
                                             'max_route_ms', 'max_match_local_cpu_s')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
