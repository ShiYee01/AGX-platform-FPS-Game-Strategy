"""Validate V2 using recorded V1 observations; this does not simulate a match."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

from check_fps_v1 import equivalent, policy, validate

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT/'策略更新/V2-稳定目标与分级脱困'
# Since V3 the entry point is no longer V2; check the frozen V2 snapshot.
V2_SOURCE = ROOT/'策略更新/V3-可达寻路与开火门限/agent-v2.py'


def check(log):
    v1 = policy(UPDATE/'agent-v1.py')
    v2 = policy(V2_SOURCE)
    rows = size = faults = baseline_mismatches = changed = 0
    memory_calls = memory_mismatches = premature_switches = switches = 0
    route_wait_calls = escapes = 0
    known_position = fuse = last_round = None
    raw_hash = hashlib.sha256()
    metadata = trailer = None
    phase_counts = Counter()
    act_seconds = decode_seconds = 0.
    maximum_act = maximum_decode_act = 0.
    maximum_act_tick = None
    opener = gzip.open if log.suffix == '.gz' else open
    for raw in opener(log, 'rb'):
        decode_start = time.perf_counter()
        row = json.loads(raw)
        decoded = time.perf_counter() - decode_start
        if row.get('type') == 'metadata': metadata = row; continue
        if row.get('type') == 'export_complete': trailer = row; continue
        if 'observation' not in row: continue
        raw_hash.update(raw); rows += 1; size += len(raw)
        o = row['observation']; m = o['me']; b = o['bomb']
        pos = [m[k] for k in ('x', 'y', 'z')]
        original = v1['act'](o)
        faults += bool(row.get('fault'))
        baseline_mismatches += not equivalent(original, row.get('action') or {})
        p = v2['_player']; previous_index = p.patrol_index
        previous_round = p.round; previous_escapes = p.escapes
        started = time.perf_counter()
        action = v2['act'](o)
        elapsed = time.perf_counter() - started
        act_seconds += elapsed; decode_seconds += decoded
        if elapsed > maximum_act:
            maximum_act, maximum_act_tick = elapsed, o['match_tick']
        maximum_decode_act = max(maximum_decode_act, decoded + elapsed)
        validate(action)
        changed += not equivalent(original, action)
        phase_counts[o['phase']] += 1
        if last_round != o['round_index']:
            known_position = fuse = None; last_round = o['round_index']
        if b['state'] != 'planted':
            known_position = fuse = None
        else:
            if b['fuse_end_tick'] != fuse: known_position = None
            fuse = b['fuse_end_tick']
            if b.get('position') is not None: known_position = list(b['position'])
        memory_mismatches += known_position != p.planted_bomb_position
        active = o['phase'] == 'live' and m['alive']
        if active:
            hidden = (o['side'] == 'defend' and b['state'] == 'planted'
                      and b.get('position') is None and known_position is not None)
            memory_calls += hidden
            if previous_round == p.round:
                escapes += p.escapes > previous_escapes
                if previous_index != p.patrol_index:
                    switches += 1
                    old_site = p.sites[previous_index % len(p.sites)]
                    premature_switches += math.dist(pos, old_site['center']) > 5
            route_wait_calls += bool(p.goal and not p.path and
                                     o['match_tick'] < p.route_retry_tick)
    assert metadata and trailer and trailer['complete']
    assert trailer['rows'] == rows and trailer['raw_bytes'] == size
    assert trailer['sha256'] == raw_hash.hexdigest()
    assert not baseline_mismatches, 'The archived V1 does not reproduce this log'
    assert not memory_mismatches, 'V2 memory differs from legally observed coordinates'
    assert not premature_switches, 'V2 rotated before reaching the old site'
    assert not faults
    return dict(match_id=metadata['job_id'],decision_rows=rows,
                log_integrity_passed=True,recorded_v1_action_mismatches=baseline_mismatches,
                v2_invalid_actions=0,v2_action_changes_on_old_observations=changed,
                memory_mismatches=memory_mismatches,
                hidden_bomb_memory_calls=memory_calls,
                patrol_rotations=switches,premature_patrol_rotations=premature_switches,
                recovery_starts_on_old_positions=escapes,
                route_wait_decisions_on_old_positions=route_wait_calls,
                phase_counts=dict(phase_counts),
                local_v2_act_seconds=act_seconds,
                local_json_decode_seconds=decode_seconds,
                local_max_v2_act_ms=maximum_act*1000,
                local_max_v2_act_tick=maximum_act_tick,
                local_max_decode_plus_v2_act_ms=maximum_decode_act*1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', nargs='*', type=Path)
    parser.add_argument('--output', type=Path, default=UPDATE/'固定观察验证结果.json')
    args = parser.parse_args()
    logs = args.logs or [next((ROOT/f'比赛日志/对局{n:02}').glob('training-*.jsonl.gz'))
                         for n in range(12, 19)]
    results = []
    for log in logs:
        result = check(log); results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    output = dict(kind='fixed_observation_regression_not_simulation',matches=results,
                  total_decisions=sum(r['decision_rows'] for r in results),
                  code_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for name, path in [('v1', UPDATE/'agent-v1.py'),
                                                  ('v2', V2_SOURCE)]},
                  limitations='All positions and events remain recorded V1 outcomes. '
                  'Changed V2 outputs are not applied to a game engine. '
                  'Do not interpret rotation/recovery counts as future match results. '
                  'Local timing is descriptive and does not guarantee AGX admission limits.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
