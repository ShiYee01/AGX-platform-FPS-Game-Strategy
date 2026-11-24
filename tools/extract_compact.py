"""Write a small, lossy analysis extract of one match for sharing.

The full training export (~3-5 MB gzipped) is the archival record; this extract
keeps only what offline strategy analysis needs, so ten matches fit in a few MB:

  * per live decision while alive: tick, round, side, own state, the recorded
    action, visible enemies, bomb fields, bomb beeps and teammate zones
  * public events of the kinds used for statistics, without per-seat `views`
  * metadata, outcome and export_complete as-is

Floats are rounded to 2 decimals (0.01 m / 0.01 rad; inaccuracy to 4). The
extract cannot replay the policy (observations are incomplete); run
tools/check_fps_v3.py on the full log locally for that.

  python3 tools/extract_compact.py 比赛日志/对局19 --output 交接/compact/对局19.jsonl.gz
"""
import argparse
import gzip
import json
from pathlib import Path

ME = ('x', 'y', 'z', 'yaw', 'pitch', 'vx', 'vy', 'vz', 'hp', 'armor', 'alive', 'crouch',
      'grounded', 'carrying_bomb', 'has_kit', 'cash', 'blind_ticks', 'active_slot')
EVENTS = {'kill', 'kill_reward', 'hit', 'fire', 'plant_start', 'plant_cancel', 'plant_complete',
          'plant_complete_detail', 'defuse_start', 'defuse_complete', 'bomb_explode',
          'round_start', 'round_end', 'side_swap', 'match_end', 'buy', 'pickup', 'drop', 'throw'}


def r(value, places=2):
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, list):
        return [r(v, places) for v in value]
    if isinstance(value, dict):
        return {k: r(v, places) for k, v in value.items()}
    return value


def decision(row):
    o = row['observation']; m = o.get('me') or {}
    if o.get('phase') != 'live' and not o.get('map'):
        return None
    weapons = m.get('weapons') or []
    slot = (row.get('action') or {}).get('weapon_slot', 0 if weapons and weapons[0] else 1)
    gun = weapons[slot] if isinstance(slot, int) and 0 <= slot < len(weapons) else None
    out = dict(t=o['match_tick'], ri=o['round_index'], rt=o['round_tick'], ph=o['phase'],
               side=o['side'], rem=o.get('phase_remaining_ticks'),
               me={k: r(m.get(k)) for k in ME},
               gun=None if not gun else dict(id=gun.get('id'), ammo=gun.get('ammo'),
                                              inacc=r(gun.get('inaccuracy'), 4)),
               a=r(row.get('action') or {}), f=row.get('fault'))
    if not m.get('alive'):
        return dict(t=out['t'], ri=out['ri'], ph=out['ph'], side=out['side'], dead=True)
    if o.get('visible'):
        out['vis'] = [{k: r(e.get(k)) for k in ('seat', 'x', 'y', 'z', 'crouch', 'parts', 'weapon')}
                      for e in o['visible']]
    b = o.get('bomb') or {}
    out['bomb'] = {k: r(v) for k, v in b.items() if v is not None and k != 'id'}
    beeps = [s.get('distance_band') for s in o.get('sounds') or ()
             if str(s.get('type', '')).startswith('bomb')]
    if beeps:
        out['beep'] = beeps
    out['mates'] = [[t.get('seat'), t.get('alive'), t.get('zone')] for t in o.get('teammates') or ()]
    if o.get('map'):
        out['map_id'], out['schema'] = o.get('map_id'), o.get('static_schema_hash')
        out['sites'] = o['map'].get('sites')
        out['geometry_hash'] = o['map'].get('geometry_hash')  # to match maps archived from 01-18
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('match', type=Path, help='match directory with training-*.jsonl[.gz]')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logs = sorted(args.match.glob('training-*.jsonl.gz')) or sorted(args.match.glob('training-*.jsonl'))
    log = logs[0]
    opener = gzip.open if log.suffix == '.gz' else open
    args.output.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with gzip.open(args.output, 'wt', encoding='utf-8', compresslevel=9) as out:
        for raw in opener(log, 'rt', encoding='utf-8'):
            row = json.loads(raw)
            if isinstance(row.get('observation'), dict):
                d = decision(row)
                if d is None:
                    continue
                out.write(json.dumps(dict(rec='decision', **d), ensure_ascii=False, separators=(',', ':')) + '\n')
                kept += 1
            else:
                out.write(json.dumps(dict(rec=row.get('type'), **row), ensure_ascii=False,
                                     separators=(',', ':')) + '\n')
        events = args.match/'public-events.jsonl'
        if events.is_file():
            for raw in open(events, encoding='utf-8'):
                e = json.loads(raw)
                if e.get('type') in EVENTS:
                    e.pop('views', None)
                    out.write(json.dumps(dict(rec='event', **r(e)), ensure_ascii=False,
                                         separators=(',', ':')) + '\n')
    print(f'{args.output}: {kept} decisions, {args.output.stat().st_size / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
