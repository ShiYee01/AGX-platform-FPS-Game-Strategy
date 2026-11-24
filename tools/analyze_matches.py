"""Summarize real AGX FPS matches from one's own training export and public events.

Offline analysis only. It reads the seat's own training export (.jsonl or .jsonl.gz)
and, if present, the match's public-events.jsonl. Public events are used for
after-the-fact statistics only and never become policy input.

For every match it reports:
  * export integrity (export_complete rows / bytes / sha256)
  * platform identity (agent_id, version_id, source_hash, rules_version)
  * which archived strategy reproduces the recorded actions exactly (V0/V1/V2)
  * result, score, faults, per-round side/result/end reason
  * own kills/deaths/assists/damage/shots/plants/defuses (public events)
  * movement health: commanded-but-not-moving stalls and whole-`me` freezes
  * site arrival and time alive

Usage (from repo root):
  python3 tools/analyze_matches.py 比赛日志/对局19 比赛日志/对局20 ... --output out.json
Each argument is a match directory holding training-*.jsonl[.gz] and optionally
public-events.jsonl.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = {
    'V0': (ROOT/'策略更新/V1-炸弹目标记忆/agent-v0.py',
           'fe7f0d71b0817919fdc62831a77ec4ea6982e15441a157083579b19096946cc5'),
    'V1': (ROOT/'策略更新/V2-稳定目标与分级脱困/agent-v1.py',
           '92a052c40cc47424de0a0281698c7e4cd7334910d986724f1cc80da69186d4e9'),
}
V2_SHA = '8b7769dbecac79a8a5553ad60fd86e59c2c536f7c60fa784733047fff82e2ac8'
KNOWN_VERSION_IDS = {
    '7d30f64b-e6f0-4298-92ab-63e8910192a6': 'V0 (pre-course test, match 01)',
    'eda92062-7f1b-4b58-93d3-a4ad3569f50b': 'V0 (matches 02-11)',
    'ba765f55-4754-4d55-b738-60507f944152': 'V1 (matches 12-18)',
    'c7cb4132-ffeb-4352-957b-6941fe40491b': 'V2 (platform "v4", matches 19-28)',
}
TPS = 60
STALL_TICKS = 180          # 3 s commanded movement with < STALL_DIST progress
STALL_DIST = 0.3           # metres
FREEZE_TICKS = 300         # 5 s with the entire `me` object unchanged while alive


def find_v2():
    for path in [ROOT/'agent/agent.py', *ROOT.glob('策略更新/V3*/agent-v2.py')]:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == V2_SHA:
            return path
    return None


def policy(path):
    scope = {'__name__': 'agx_candidate'}
    exec(compile(path.read_bytes(), str(path), 'exec'), scope)
    if 'init' in scope:
        scope['init']({})
    return scope


def equivalent(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if type(a) in (float, int) and type(b) in (float, int):
        return math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)
    return type(a) == type(b) and a == b


def moving(action):
    a = action or {}
    return abs(a.get('move_forward', 0) or 0) + abs(a.get('move_right', 0) or 0) > 0.1


def open_any(path):
    return gzip.open(path, 'rb') if path.suffix == '.gz' else open(path, 'rb')


def analyze(directory, candidates, replay=True):
    directory = Path(directory)
    logs = sorted(directory.glob('training-*.jsonl.gz')) or sorted(directory.glob('training-*.jsonl'))
    if not logs:
        raise FileNotFoundError(f'no training-*.jsonl[.gz] in {directory}')
    log = logs[0]
    policies = {name: policy(path) for name, path in candidates.items()} if replay else {}
    mismatch = Counter(); first_mismatch = {}
    act_time = Counter(); act_max = Counter()
    raw_hash = hashlib.sha256(); size = rows = 0
    metadata = trailer = outcome = None
    fault_rows = 0; fault_kinds = Counter(); first_fault = None
    rounds = defaultdict(lambda: dict(calls=0, alive_calls=0, live_alive_calls=0, visible_calls=0,
                                      move_calls=0, stall_episodes=0, stall_seconds=0.0,
                                      freeze_episodes=0, freeze_seconds=0.0,
                                      freeze_nonzero_velocity=0, reached_site=False,
                                      first_live_tick=None, last_alive_tick=None,
                                      first_enemy_seen_tick=None, last_enemy_seen_tick=None, side=None))
    sites = []; map_id = None; seat = team = None
    stall_anchor = None; freeze_since = None; last_me = None; last_round = None

    def close_freeze(r, tick):
        nonlocal freeze_since
        if freeze_since is not None:
            span = tick - freeze_since[0]
            if span >= FREEZE_TICKS:
                rounds[r]['freeze_episodes'] += 1
                rounds[r]['freeze_seconds'] += span / TPS
                rounds[r]['freeze_nonzero_velocity'] += freeze_since[1]
            freeze_since = None

    for raw in open_any(log):
        row = json.loads(raw)
        if not isinstance(row, dict):
            continue
        if row.get('type') == 'metadata':
            metadata = row; continue
        if row.get('type') == 'export_complete':
            trailer = row; continue
        if row.get('type') == 'outcome':
            outcome = row; continue
        if not isinstance(row.get('observation'), dict):
            continue
        raw_hash.update(raw); size += len(raw); rows += 1
        o = row['observation']; me = o.get('me') or {}; tick = o['match_tick']; r = o['round_index']
        seat, team = o.get('seat'), o.get('team')
        if o.get('map'):
            map_id = o.get('map_id'); sites = o['map'].get('sites') or []
        if row.get('fault'):
            fault_rows += 1; fault_kinds[str(row['fault'])[:80]] += 1
            first_fault = first_fault or dict(tick=tick, round=r + 1, fault=row['fault'])
        for name, p in policies.items():
            started = time.process_time()
            try:
                action = p['act'](o)
            except Exception as error:  # a candidate crashing means it is not the deployed one
                action = {'__exception__': repr(error)}
            spent = time.process_time() - started
            act_time[name] += spent; act_max[name] = max(act_max[name], spent)
            if not equivalent(action, row.get('action') or {}):
                mismatch[name] += 1
                first_mismatch.setdefault(name, dict(tick=tick, round=r + 1))
        if r != last_round:
            close_freeze(last_round, tick); stall_anchor = None; last_me = None; last_round = r
        R = rounds[r]; R['calls'] += 1; R['side'] = o.get('side')
        alive = bool(me.get('alive')); live = o.get('phase') == 'live'
        if alive:
            R['alive_calls'] += 1; R['last_alive_tick'] = tick
        if not (alive and live):
            close_freeze(r, tick); stall_anchor = None; last_me = None
            continue
        R['live_alive_calls'] += 1
        if R['first_live_tick'] is None:
            R['first_live_tick'] = tick
        if o.get('visible'):
            R['visible_calls'] += 1
            if R['first_enemy_seen_tick'] is None:
                R['first_enemy_seen_tick'] = tick
            R['last_enemy_seen_tick'] = tick
        pos = (me.get('x', 0.), me.get('y', 0.), me.get('z', 0.))
        for s in sites:
            if math.dist(pos, s['center']) <= s['radius']:
                R['reached_site'] = True
        # whole-`me` freeze (the 88 s anomaly from match 17)
        if last_me is not None and me == last_me:
            if freeze_since is None:
                freeze_since = (prev_tick, int(bool(me.get('vx') or me.get('vy'))))
        else:
            close_freeze(r, tick)
        last_me = me; prev_tick = tick
        # commanded movement without progress
        if moving(row.get('action')) and (row.get('action') or {}).get('use', 'none') in ('none', None):
            R['move_calls'] += 1
            if stall_anchor is None:
                stall_anchor = (tick, pos, False)
            elif math.dist(pos, stall_anchor[1]) >= STALL_DIST:
                if stall_anchor[2]:
                    R['stall_seconds'] += (tick - stall_anchor[0]) / TPS
                stall_anchor = (tick, pos, False)
            elif not stall_anchor[2] and tick - stall_anchor[0] >= STALL_TICKS:
                R['stall_episodes'] += 1; stall_anchor = (stall_anchor[0], stall_anchor[1], True)
        else:
            if stall_anchor and stall_anchor[2]:
                R['stall_seconds'] += (tick - stall_anchor[0]) / TPS
            stall_anchor = None
    if rows:
        close_freeze(last_round, tick)

    integrity = bool(trailer and trailer.get('complete') and trailer.get('rows') == rows
                     and trailer.get('raw_bytes') == size and trailer.get('sha256') == raw_hash.hexdigest())
    participant = next((p for p in (metadata or {}).get('participants', []) if p.get('seat') == seat), {})
    result = None; score = None
    if outcome and team is not None:
        wins = outcome.get('round_wins') or [None, None]
        score = [wins[team], wins[1 - team]]
        result = 'draw' if outcome.get('winner') is None else ('win' if outcome['winner'] == team else 'loss')

    # public events (optional, offline only)
    events_path = directory/'public-events.jsonl'
    totals = Counter(); round_end = {}
    if events_path.is_file():
        teams = (outcome or {}).get('teams') or [0]*5 + [1]*5
        pending_plant = {}; pending_defuse = {}
        for line in open(events_path, 'rb'):
            e = json.loads(line); t = e.get('type'); ri = e.get('round_index')
            if t == 'kill_reward' and e.get('killer') == seat:
                totals['kills'] += 1; rounds[ri]['kills'] = rounds[ri].get('kills', 0) + 1
            elif t == 'kill':
                if e.get('target') == seat:
                    totals['deaths'] += 1; rounds[ri]['deaths'] = 1; rounds[ri]['death_tick'] = e['match_tick']
                elif seat in (e.get('attackers') or []) and teams[e['target']] != team:
                    totals['kill_participations'] += 1
            elif t == 'hit' and e.get('player') == seat and teams[e.get('target', seat)] != team:
                d = float(e.get('hp_damage') or 0)
                totals['hits'] += 1
                totals['damage'] += d; rounds[ri]['damage'] = rounds[ri].get('damage', 0.) + d
            elif t == 'hit' and e.get('target') == seat and e.get('player') is not None:
                totals['damage_taken'] += float(e.get('hp_damage') or 0)
            elif t == 'fire' and e.get('player') == seat and not e.get('pellet'):
                totals['shots'] += 1
            elif t == 'buy' and e.get('seat') == seat:
                totals['buy:' + str(e.get('kind'))] += 1
            elif t == 'plant_start':
                pending_plant[e.get('item_id')] = e.get('player')
                if e.get('player') == seat: totals['plant_starts'] += 1
            elif t == 'plant_complete' and pending_plant.get(e.get('item_id')) == seat:
                totals['plants'] += 1; rounds[ri]['planted_by_me'] = True
            elif t == 'defuse_start':
                pending_defuse[e.get('item_id')] = e.get('player')
                if e.get('player') == seat: totals['defuse_starts'] += 1
            elif t == 'defuse_complete' and pending_defuse.get(e.get('item_id')) == seat:
                totals['defuses'] += 1; rounds[ri]['defused_by_me'] = True
            elif t == 'round_end':
                round_end[ri] = dict(win=e.get('round_winner') == team, reason=e.get('reason'))
        # kill_participations minus own kills approximates assists (see README caveat)
        totals['assists_approx'] = max(0, totals['kill_participations'] - totals['kills'])
    round_list = []
    for ri in sorted(k for k in rounds if k is not None):
        R = dict(rounds[ri]); R['round'] = ri + 1; R.update(round_end.get(ri, {}))
        if R.get('deaths'):
            seen = R.get('last_enemy_seen_tick')
            R['death_without_enemy_seen_2s'] = seen is None or R['death_tick'] - seen > 2 * TPS
        R['stall_seconds'] = round(R['stall_seconds'], 2); R['freeze_seconds'] = round(R['freeze_seconds'], 2)
        round_list.append(R)
    by_side = defaultdict(Counter)
    for R in round_list:
        if 'win' in R:
            by_side[R['side']]['rounds'] += 1; by_side[R['side']]['wins'] += R['win']
            by_side[R['side']]['reached_site'] += R['reached_site']
            by_side[R['side']]['deaths'] += R.get('deaths', 0)
            by_side[R['side']]['no_enemy_seen'] += R['first_enemy_seen_tick'] is None
            by_side[R['side']]['deaths_unseen_2s'] += bool(R.get('death_without_enemy_seen_2s'))
            by_side[R['side']]['damage'] += round(R.get('damage', 0.), 2)
            by_side[R['side']]['kills'] += R.get('kills', 0)
    replay_info = {name: dict(mismatches=mismatch[name], first_mismatch=first_mismatch.get(name),
                              local_cpu_s=round(act_time[name], 3),
                              local_max_act_ms=round(act_max[name]*1000, 3)) for name in policies}
    reproduced = [n for n in policies if mismatch[n] == 0]
    return dict(
        directory=str(directory), log=log.name, match_id=(metadata or {}).get('job_id'),
        rules_version=(metadata or {}).get('rules_version'), map_id=map_id, seat=seat, team=team,
        platform=dict(agent_id=participant.get('agent_id'), version_id=participant.get('version_id'),
                      source_hash=participant.get('source_hash'),
                      known_as=KNOWN_VERSION_IDS.get(participant.get('version_id'), 'UNKNOWN (new version id)')),
        integrity_passed=integrity, decision_rows=rows,
        reproduced_by=reproduced, replay=replay_info,
        result=result, score=score, outcome_faults=(outcome or {}).get('faults'),
        own_fault_rows=fault_rows, fault_kinds=dict(fault_kinds), first_fault=first_fault,
        totals={k: (round(v, 2) if isinstance(v, float) else v) for k, v in totals.items()},
        movement=dict(stall_episodes=sum(R['stall_episodes'] for R in round_list),
                      stall_seconds=round(sum(R['stall_seconds'] for R in round_list), 2),
                      freeze_episodes=sum(R['freeze_episodes'] for R in round_list),
                      freeze_seconds=round(sum(R['freeze_seconds'] for R in round_list), 2)),
        by_side={k: dict(v) for k, v in by_side.items()}, rounds=round_list)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('matches', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-replay', action='store_true', help='skip V0/V1/V2 reproduction (faster)')
    args = parser.parse_args()
    candidates = {k: v[0] for k, v in CANDIDATES.items()}
    for name, (path, sha) in CANDIDATES.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, f'{name} snapshot changed: {path}'
    v2 = find_v2()
    if v2:
        candidates['V2'] = v2
    current = ROOT/'agent/agent.py'
    if hashlib.sha256(current.read_bytes()).hexdigest() != V2_SHA:
        # Label the current entry by its docstring, e.g. "FPS V3: ...".
        head = current.read_text(encoding='utf-8').split('\n', 1)[0]
        label = next((w.rstrip(':') for w in head.split() if w.startswith('V') and w[1:2].isdigit()), 'current')
        candidates[label] = current
    else:
        print('warning: no file with the V2 sha256 found; V2 reproduction skipped')
    results = []
    for directory in args.matches:
        result = analyze(directory, candidates, replay=not args.no_replay)
        results.append(result)
        brief = {k: result[k] for k in ('directory', 'map_id', 'result', 'score', 'reproduced_by',
                                         'own_fault_rows', 'integrity_passed')}
        brief['version'] = result['platform']['known_as']; brief['movement'] = result['movement']
        print(json.dumps(brief, ensure_ascii=False), flush=True)
    groups = defaultdict(lambda: Counter())
    for r in results:
        if args.no_replay:
            key = f"version_id:{r['platform']['version_id']} ({r['platform']['known_as']})"
        else:
            key = '+'.join(r['reproduced_by']) or f"unreproduced:{r['platform']['version_id']}"
        g = groups[key]; g['matches'] += 1; g[r['result'] or 'unknown'] += 1
        for k in ('kills', 'deaths', 'assists_approx', 'damage', 'hits', 'plants', 'defuses', 'shots'):
            g[k] += r['totals'].get(k, 0)
        g['rounds'] += len([x for x in r['rounds'] if 'win' in x])
        g['own_fault_rows'] += r['own_fault_rows']
        g['deaths_unseen_2s'] += sum(bool(x.get('death_without_enemy_seen_2s')) for x in r['rounds'])
        for k, v in r['movement'].items():
            g[k] += v
    for g in groups.values():
        if g['rounds']:
            g['adr'] = g['damage'] / g['rounds']; g['kpr'] = g['kills'] / g['rounds']
            g['dpr'] = g['deaths'] / g['rounds']
    output = dict(kind='real_match_analysis', tool='tools/analyze_matches.py',
                  candidate_sha256={k: hashlib.sha256(Path(p).read_bytes()).hexdigest() for k, p in candidates.items()},
                  thresholds=dict(stall_ticks=STALL_TICKS, stall_dist_m=STALL_DIST, freeze_ticks=FREEZE_TICKS),
                  groups_by_reproducing_version={k: {a: (round(b, 2) if isinstance(b, float) else b)
                                                     for a, b in v.items()} for k, v in groups.items()},
                  matches=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
