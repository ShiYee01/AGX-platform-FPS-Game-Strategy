"""Check V0/V1 actions against fixed observations, without simulating a match."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT/'策略更新/V1-炸弹目标记忆'


def policy(path):
    scope = {}
    exec(compile(path.read_bytes(), str(path), 'exec'), scope)
    scope['init']({})
    return scope


def equivalent(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if type(a) in (float, int) and type(b) in (float, int):
        return math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)
    return type(a) == type(b) and a == b


def validate(action):
    bools = {'jump', 'crouch', 'duck', 'walk', 'fire', 'fire_secondary',
             'reload', 'sprint', 'ads'}
    analog = {'move_forward', 'move_right', 'yaw_rate', 'pitch_rate', 'climb'}
    allowed = bools | analog | {'weapon_slot', 'buy', 'use', 'pickup_id'}
    assert isinstance(action, dict) and set(action) <= allowed
    json.dumps(action, allow_nan=False)
    for k, value in action.items():
        if k in bools:
            assert type(value) is bool
        elif k in analog:
            assert type(value) in (int, float) and math.isfinite(value) and -1 <= value <= 1
        elif k == 'weapon_slot':
            assert type(value) is int and 0 <= value <= 2
        elif k == 'buy':
            assert value in {'none', 'defusekit', 'ak47', 'm4a1', 'armor'}
        elif k == 'use':
            assert value in {'none', 'plant', 'defuse', 'pickup'}
        elif k == 'pickup_id':
            assert value is None or isinstance(value, str) and 0 < len(value) <= 128


def check(log):
    v0 = policy(UPDATE/'agent-v0.py')
    v1 = policy(ROOT/'策略更新/V2-稳定目标与分级脱困/agent-v1.py')
    count = mismatches = changed = attack_changed = unplanted_changed = 0
    changes_by_round = Counter()
    remembered_calls = 0
    raw_hash, raw_bytes = hashlib.sha256(), 0
    evidence = {}
    metadata = trailer = None
    opener = gzip.open if log.suffix == '.gz' else open
    with opener(log, 'rb') as f:
        for raw in f:
            row = json.loads(raw)
            if row.get('type') == 'metadata': metadata = row; continue
            if row.get('type') == 'export_complete': trailer = row; continue
            if 'observation' not in row: continue
            raw_hash.update(raw); raw_bytes += len(raw); count += 1
            o = row['observation']
            original = v0['act'](o)
            updated = v1['act'](o)
            validate(updated)
            if not equivalent(original, row['action']): mismatches += 1
            if not equivalent(original, updated):
                changed += 1
                changes_by_round[o['round_index']+1] += 1
                attack_changed += o['side'] == 'attack'
                unplanted_changed += o['bomb']['state'] != 'planted'
            p = v1['_player']
            if (o['phase'] == 'live' and o['me']['alive'] and o['side'] == 'defend'
                    and o['bomb']['state'] == 'planted'
                    and o['bomb'].get('position') is None
                    and p.planted_bomb_position is not None):
                remembered_calls += 1
            if o['match_tick'] in (30969, 30999, 57051):
                evidence[str(o['match_tick'])] = {
                    'round': o['round_index']+1,
                    'observation_bomb': o['bomb'],
                    'v0_goal': v0['_player'].goal,
                    'v1_goal': p.goal,
                    'v1_remembered_position': p.planted_bomb_position,
                    'v0_escape_until': v0['_player'].escape_until,
                    'v1_escape_until': p.escape_until,
                    'v0_action': original, 'v1_action': updated,
                }
    assert trailer and trailer['complete'] is True
    assert count == trailer['rows'] and raw_bytes == trailer['raw_bytes']
    assert raw_hash.hexdigest() == trailer['sha256']
    assert mismatches == 0, 'V0 does not match the archived submission trace'
    assert attack_changed == 0 and unplanted_changed == 0
    assert evidence['30969']['v1_goal'] == evidence['30969']['observation_bomb']['position']
    assert evidence['30969']['v1_escape_until'] <= 30969
    assert evidence['30999']['v1_remembered_position'] == evidence['30969']['observation_bomb']['position']
    assert evidence['30999']['v1_goal'] == evidence['30969']['observation_bomb']['position']
    assert evidence['57051']['v1_goal'] == evidence['57051']['v1_remembered_position']
    return {
        'kind': 'fixed_observation_action_regression', 'match_id': metadata['job_id'],
        'decision_rows': count, 'log_integrity_passed': True,
        'v0_recorded_action_mismatches_at_1e_12': mismatches,
        'v1_invalid_actions': 0, 'v1_changed_action_calls': changed,
        'v1_changed_calls_by_round': dict(changes_by_round),
        'attack_changed_calls': attack_changed,
        'non_planted_changed_calls': unplanted_changed,
        'defend_alive_hidden_position_memory_calls': remembered_calls,
        'critical_observations': evidence,
        'code_sha256': {label: hashlib.sha256(path.read_bytes()).hexdigest()
            for label, path in [('v0', UPDATE/'agent-v0.py'), ('v1', ROOT/'策略更新/V2-稳定目标与分级脱困/agent-v1.py')]},
        'limitations': 'Observations remain the recorded V0 trajectory after actions diverge. '
                        'This checks legal-information memory and action output only. '
                        'It does not simulate new positions, combat, objective outcomes or win rate.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, default=ROOT/'比赛日志/对局01'/
                        'training-633b4a9d-c271-444b-9155-14f67e96aae0.jsonl.gz')
    parser.add_argument('--output', type=Path, default=UPDATE/'验证结果.json')
    args = parser.parse_args()
    result = check(args.log)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('critical_observations','code_sha256')},
                     ensure_ascii=False, indent=2))
