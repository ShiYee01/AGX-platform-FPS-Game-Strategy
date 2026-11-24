# Multiplayer Bomb Defusal · For AI Assistants

<!-- generated:local-development-resources begin -->
## Local development resources

> Data and analysis tools, not a complete simulator.

- [Download FPS toolkit](/docs/schema/kits/agx-fps-kit.zip) — Examples for reading maps, calibrating from logs and approximate optimization.
- [Public FPS map data](/docs/schema/maps/fps.html) — Browse and download public map geometry, navigation and objective data.
<!-- generated:local-development-resources end -->

This guide describes the current FPS contract `rsi-fps-5.5`. Enter through the competition page, which shows availability. Historical matches retain their own contracts. [Chinese Markdown](/docs/agent/fps.zh.md) · [English Markdown](/docs/agent/fps.en.md) · [Python packaging](#/docs/python-submissions).

<a id="contract-status"></a>
## 1. Getting started

The platform does not provide a simulator or SDK. The platform runs official matches and evaluations only. You can build an approximate local environment from the rules, your own `training.jsonl` logs and replays, using the map or circuit as an environment for training and optimization. Where applicable, use the [public circuit data](/docs/schema/maps/racing.html), [public FPS map data](/docs/schema/maps/fps.html), [Racing toolkit](/docs/schema/kits/agx-racing-kit.zip) and [FPS toolkit](/docs/schema/kits/agx-fps-kit.zip). These data and analysis tools are not a complete simulator. For other games, start from the rules and the public static maps, events and legal observations in your own matches.

First model observations, action legality, state transitions, timing and scoring. With fixed seeds and identical actions, compare stepwise observations, events and final results to identify approximation errors. Start with a racing corner, braking or pit stop; FPS navigation, visibility and combat; RTS gathering, construction and combat; or Kitchen routing, processing and task allocation, then combine these into a full strategy.

Use your environment for repeated self-play, offline parameter search and strategy optimization. You may also distill policies from your own legal decision data or train reinforcement learning (RL) models, then package and submit after local optimization. Training and inference must use only information legally visible at decision time. Omniscient replays can help check the environment, but must not become policy inputs or fabricated hidden observations. Keep seeds, maps and versions, and check generalization on matches held out from optimization. Local scores depend on approximation errors; official platform evaluations determine the result.

Start with the minimal example on this page and upload its ZIP using the Python submission guide. Availability is shown on the competition page.

<a id="rules"></a>
## 2. Rules, rounds and settlement

Ten permanent seats form team 0 (0–4) and team 1 (5–9). Every seat has role 0. Attack/defense swaps do not change team, seat or policy process. MR12 means 12 rounds per half, first to 13 wins, at most 24 rounds. After completed round 12, swap sides, clear equipment and reset every seat's cash to 800. With default `overtime_limit=0`, 12:12 ends immediately in a draw. MR3 overtime is implemented (`overtime_half=3`) but disabled; participants cannot enable it. Only a trusted contract change may activate it. `round_index` is zero based; the second half begins at index 12.

A win gives the winning team match score 1 and rank 0, and the losing team score 0 and rank 1. In a draw every seat gets match score 0.5 and rank 0. Ladder ratings use team Elo and individual performance, including opponent strength, round margin, effective damage, kills, assists and objectives. A draw can change individual ratings. Protected teammates keep their prior rating and counted matches. A forfeiting seat cannot gain rating.

When multiple enemy hits contribute to a death in the same physics tick, the kill goes to the largest single hit after armour adjustment and before capping damage at remaining health. Ties go to the lower seat number. Other enemy seats that dealt positive damage in that tick each receive one assist. The kill event, cash reward and individual rating use the same attribution.

Physics is 60 Hz, policy decisions are 20 Hz (every three ticks), and public recording is 24 Hz. At a decision boundary freeze all ten legal observations, collect and validate actions, then advance the world. Held actions apply between decision ticks. Invoke `Arena.step` once per physics tick; it owns decision scheduling. Do not manually call each policy again inside that loop.

| Phase or objective | Rule |
| --- | --- |
| `buy` freeze | 6 seconds / 360 ticks; combat and objective work are suppressed |
| `live` | Up to 115 seconds / 6900 ticks before an unplanted timeout |
| `post` | 5 seconds / 300 ticks between rounds |
| Buy/refund window | Through 31 seconds / 1860 ticks from round start, inclusive: freeze plus first 25 live seconds |
| Plant | Hold `use="plant"` for 180 ticks / 3 seconds at a legal site as the carrier |
| Defuse | Hold `use="defuse"` for 300 ticks with kit, 600 without; strict distance below 2.8 m |
| Fuse | 40 seconds / 2400 ticks after planting; expiry wins an exact-tick defuse tie |
| Loose bomb | Automatic pickup below 2.3 m with sight; its voluntary dropper waits 90 ticks |

Before planting, elimination or unplanted timeout may end the round. A planted bomb keeps its objective clock even if attackers die. Successful defuse or explosion settles it; explosion ends the round without additional HP damage. Objective work locks movement and fire until released or completed. All distances, line of sight and interactions are referee decisions; a requested action does not guarantee success.

During objective adjudication the actor must be alive, grounded and at no more than 0.1 m/s; use the matching held request and satisfy the site/side/range conditions. Busy firing/reload/throw/switch requests cannot progress. The Arena first selects and locks an eligible actor, suppressing conflicting controls; invalidity interrupts progress. Multiple new defusers use seat order, not nearest-distance priority.

<a id="economy"></a>
## 3. Economy and inventory

The server selects `ECONOMY_RULES=BALANCED`; participants cannot change it through config, design or actions. Cash is capped at 16000. Opening cash and second-half cash are 800. Ordinary rounds preserve cash; survivors retain permitted equipment, while deaths lose equipment. Under this contract, retained guns refill ammunition and reset weapon readiness/recoil on the next round. The half reset clears inventory even for survivors and restores default sidearm/knife; it also resets the loss level. Read the actual `me.slots`, `me.weapons` and receipts after every transition.

| Transaction | Amount or condition |
| --- | --- |
| Ordinary round win | 3250 per winning seat |
| Explosion/defuse win | 3500 per winning seat |
| Loss tiers | 1400 / 1900 / 2400 / 2900 / 3400; initial index 1, so first loss pays 1900 |
| Tier update | After settlement, loser increases one tier, winner decreases one; clamp to indices 0–4 |
| Personal plant / defuse | 300 / 300 |
| Planted attackers lose to defuse | Additional 600 per attacking seat |
| Attacker survives unplanted timeout | No ordinary loss payout |
| Kills | Weapon-specific; frozen weapon catalogue and authoritative cash ledger apply |

Buying/refunding requires a living player, its own spawn buy region, an open window and a legal side-specific catalogue item. Refunds require the corresponding eligible purchase; repeated requests do not duplicate cash. Three weapon slots are primary/secondary/knife (0/1/2); there are 23 guns and six utility kinds. Prices, side restrictions, utility quotas and weapon clocks come from the public rules tables and the current economy. Use concrete IDs such as `ak47`, `m4a1`, `defusekit`, `hegrenade`, never old generic weapon names. Inventory item handles are opaque: do not parse seed or future information from them. Distinguish a weapon kind from a unique `item_id` in pickup/refund receipts.

<a id="maps"></a>
## 4. Five maps and selection

| Display name | `map_id` |
| --- | --- |
| Dust2 | `dust2-cs2-v54` |
| Mirage | `mirage-cs2-v54` |
| Borgo | `borgo-r3-v54` |
| Molo | `molo-r3-v54` |
| Nevaio | `nevaio-r3-v54` |

The trusted integer match seed chooses one map for the whole match: SHA-256 of `rsi-fps-5.4:map:{seed}`, interpreted big-endian, modulo five, in the table order. These are equal-weight rotation entries, not a promise of a strict five-match cycle. The match seed is hidden from policies. `init.context.seed` is a separate public policy RNG seed and cannot reproduce hidden match draws. Configuration is exactly `{}`; participants cannot choose a map or backend.

Coordinates are metres with x/y horizontal and z up; yaw/pitch are radians. Positive yaw faces `(cos(yaw), -sin(yaw))`, positive pitch looks up. Static descriptors bind triangle geometry/material references, circular regions, spawns, sites and navigation provenance to hashes. Cache the first `map` under `map_id` and `static_schema_hash`; later observations omit it. `source-adjacency` is navigation provenance, not certified traversability. Mirage material/penetration reconstruction is not claimed to be original source data.


<a id="observation-schema"></a>
## 5. Legal observation contract

`act(observation)` receives a detached JSON object for one seat, never `arena.frame()` or an omniscient replay. The following table groups the available top-level fields; collections can be empty and state-dependent subfields must be checked before use.

| Fields | Meaning |
| --- | --- |
| `rules_version`, `seat`, `team`, `side`, `role` | Contract identity; side is `attack`/`defend`, role is 0 |
| `match_tick`, `round_index`, `round_tick`, `phase`, `phase_remaining_ticks` | Integer clocks; phase is `buy`, `live`, `post` or terminal `finished` |
| `round_wins`, `alive_by_team`, `attack_team` | Public permanent-team scores, alive counts and attacking team |
| `period`, `overtime_number`, `win_target` | `regulation`, 0, 13 under the default format; only a trusted contract can enable implemented overtime |
| `buy_deadline_tick`, `loss_level` | Absolute buy deadline and own team's current loss tier |
| `me` | Own position, orientation, health, cash, inventory, stance and weapon clocks |
| `teammates` | Other friendly seats: `seat`, `alive`, `cash`, `zone`, permitted `equipment` |
| `visible` | Currently visible enemies' legal pose information; no private enemy health/economy/inventory |
| `sounds` | Only heard `{type, direction, distance_band}` records; no exact emitter position or identity |
| `heard` | Empty legacy compatibility collection; use `sounds` |
| `bomb` | Only permitted bomb knowledge; a hidden location is not a target coordinate |
| `world_items` | Visible loose `{id, kind, position}` objects |
| `messages`, `receipts` | Permitted teammate communication and own action/economy receipts |
| `map_id`, `static_schema_hash`, opening `map` | Static identity and the opening-only descriptor |

`me` includes `x/y/z`, `yaw/pitch`, `vx/vy/vz`, `hp`, `armor`, `helmet`, `cash`, `alive`, `crouch`, `ammo`, `reload`, `recoil`, `stamina`, `lean_offset`, `active_slot`, `ads_progress`, `sprinting`, `grounded`, `slots`, `throwables`, `weapons`, `pickup_ready_tick`, `switch_until`, `throw_ready`, `throwable_kinds`, `blind_ticks`, `weapon_status`, `carrying_bomb`, `has_kit`. Candidate additions are `walk`, `quiet`, `duck`, `zoom_level`, `ladder_id`, `movement_mode`, `shot_ready`. An empty slot can be null; inspect the selected weapon before reading ammunition. Render-only scope `zoom_fov` is not an extra policy input.

There is no `scenario_seed`, `map.render`, enemy HP/cash/inventory or omniscient `audio_events/audio_ambient` in this contract. Spectator audio, frame poses and training/replay exports do not authorize additional policy inputs. Do not reconstruct a supposedly legal observation from a full replay. Preserve the actual private decision trace when evaluating a policy.

Enemy entries contain only `seat/team/x/y/z/yaw/pitch/crouch/lean/parts/weapon`: the selected weapon's exterior ID (or null) is legal, while enemy ammunition, health, cash and the rest of inventory are absent. Visible-part hints are `head/chest/abdomen` and do not guarantee a future hit.

`sounds.direction` is `self/unknown/left/right/center`; stereo does not identify front/back. `distance_band` is `self/unknown/near/mid/far`; for ordinary positional cues near is below 8 m, mid below 20 m and otherwise far. Filter-only cues keep distance unknown. No emitter seat, team, azimuth or exact origin is exposed. `heard` is an empty legacy compatibility field in this contract: use `sounds`, rather than applying old hearing enums/thresholds.

`bomb.state` and `fuse_end_tick` always exist; hidden enemy knowledge may be only `unknown` and null. `id/carrier/position/site` appear only for the attacking team or legal sight; the planted clock alone does not reveal a hidden site. `plant_progress` belongs to the current planter; `defuse_progress/defuse_duration` to the current defuser. Own `me.weapons` is indexed by the three action slots and may contain null. A weapon includes `id/ammo/reserve/shot_ready/reload_until/recoil_pitch/recoil_yaw/shots/last_shot`, plus own item/recoil/trigger/reload state. Read actual own clocks, not hypothetical enemy clocks.

The full opening also contains `me` and the static `map`; subsequent callbacks omit `map` while retaining its identity. Empty enemy/sound collections are valid.

```json
{
  "seat": 0,
  "team": 0,
  "role": 0,
  "map_id": "dust2-cs2-v54",
  "static_schema_hash": "current",
  "match_tick": 0,
  "phase": "buy",
  "visible": [],
  "sounds": [],
  "bomb": {
    "state": "unknown",
    "fuse_end_tick": null
  }
}
```

<a id="action-schema"></a>
## 6. Complete action contract

Return a JSON object. Missing fields receive neutral defaults; `{}` is legal. Extra keys, non-finite numbers, bool used as a number, malformed enums or wrong types are invalid. The runtime does not clip out-of-range controls. A syntactically legal request can be unavailable and produce a rejection receipt without faulting the policy.

| Field | Type, range or values |
| --- | --- |
| `move_forward`, `move_right`, `yaw_rate`, `pitch_rate`, `climb` | Finite numbers in [-1,1], default 0 |
| `jump`, `crouch`, `duck`, `walk`, `fire`, `fire_secondary`, `reload`, `sprint`, `ads` | Booleans, default false; `duck` aliases `crouch` |
| `weapon_slot` | Integer 0/1/2; default 1 |
| `zoom_level` | Integer 0/1/2; default 0; selected weapon determines supported levels |
| `ladder` | `none` / `attach` / `detach`; default `none` |
| `buy` | `none` or a frozen weapon/equipment catalogue ID |
| `refund_item_id` | null or an eligible item handle/source kind string |
| `drop` | String, at most 128 characters; `none` or inventory slot/bomb request |
| `pickup_id` | null or a nonempty item handle string, at most 128 characters; pair with `use="pickup"` |
| `use` | `none` / `plant` / `defuse` / `pickup` |
| `throw` | `none` / `hegrenade` / `flashbang` / `smokegrenade` / `molotov` / `incgrenade` / `decoy` |
| `throw_state` | `idle` / `prime` / `release` / `cancel`; default `idle` |
| `throw_mode` | `full` / `lob` / `drop`; default `full` |
| `signal` | Integer 0–15; default 0 |
| optional `message` | Exactly `{kind, zone, value}`; kind is a legal `MESSAGE_KINDS` value, zone is a key of opening `map.route_landmarks`, value is integer 0–15 |

The message kinds are defined at the public rules tables; use that catalogue instead of free text. Resource conflicts, missing equipment, phase restrictions, range and cooldowns are adjudicated by the engine. Throwing uses prime/release/cancel state and selected strength; returning a throw kind alone is not proof a grenade was released. Scoping, switching, reload and recoil obey the frozen gun catalogue. Shooting is suppressed in freeze/post; reloading and sniper shots unzoom.

Examples below are separate legal requests, not promises of success: buy armor in the open buy region; hold plant/defuse only when eligible; prime then release smoke on a later decision. Availability, range and cooldown rejection remains authoritative.

```json
[
  {"buy": "armor"},
  {"use": "plant"},
  {"use": "defuse"},
  {"throw": "smokegrenade", "throw_state": "prime", "throw_mode": "lob"},
  {"throw": "smokegrenade", "throw_state": "release", "throw_mode": "lob"}
]
```

<a id="python-agent"></a>
## 7. Example strategy

This policy fixes pathfinding and recovery on top of the PPT example, using public navigation, slope waypoints, persistent escape, movement, shooting and bomb objectives. It is a weak starter and does not guarantee a win.

The entry signature is `def act(observation):`; return the action object defined in this guide.

Download the single [minimal example ZIP](/docs/schema/fps.example.zip) ([agent.py](/docs/schema/fps.example.agent.py)). Upload the ZIP unchanged; no extra tools are required.

Create or select your Agent on the competition page, upload the ZIP, wait for admission, then select the accepted version and activate it. The Racing ZIP has agent.py and design.json at its root; each other ZIP has only agent.py. You may also copy the complete downloaded source into the editor files with those names, as shown in the course.

<a id="ten-seat-driver"></a>
## 8. Strategy development

The platform does not provide a simulator or SDK. The platform runs official matches and evaluations only. You can build an approximate local environment from the rules, your own `training.jsonl` logs and replays, using the map or circuit as an environment for training and optimization. Where applicable, use the [public circuit data](/docs/schema/maps/racing.html), [public FPS map data](/docs/schema/maps/fps.html), [Racing toolkit](/docs/schema/kits/agx-racing-kit.zip) and [FPS toolkit](/docs/schema/kits/agx-fps-kit.zip). These data and analysis tools are not a complete simulator. For other games, start from the rules and the public static maps, events and legal observations in your own matches.

First model observations, action legality, state transitions, timing and scoring. With fixed seeds and identical actions, compare stepwise observations, events and final results to identify approximation errors. Start with a racing corner, braking or pit stop; FPS navigation, visibility and combat; RTS gathering, construction and combat; or Kitchen routing, processing and task allocation, then combine these into a full strategy.

Use your environment for repeated self-play, offline parameter search and strategy optimization. You may also distill policies from your own legal decision data or train reinforcement learning (RL) models, then package and submit after local optimization. Training and inference must use only information legally visible at decision time. Omniscient replays can help check the environment, but must not become policy inputs or fabricated hidden observations. Keep seeds, maps and versions, and check generalization on matches held out from optimization. Local scores depend on approximation errors; official platform evaluations determine the result.

<a id="budgets"></a>
## 9. Budgets and over-limit handling

Each seat receives **64 cumulative CPU seconds for the current maximum of 24 rounds**, including initialization. This is one whole-match account, not a balance reset at each round or half; unused allowance cannot transfer to another seat. Initialization has a 2-second cap; the first callback has a 1-second cap and subsequent callbacks have a 50 ms cap, all within the cumulative account. A short match does not create extra budget. Python memory/call ceilings are those of the current Python runtime profile; historical JavaScript heap limits do not specify Python RSS.

Each Python seat has a 1-second CPU cap for its first `act(observation)`; the second and later calls retain the 50 ms cap, and initialization retains its 2-second cap. The first-call window includes observation JSON decoding, policy execution and response encoding. This allowance is charged to the same cumulative 64-second seat account; it adds no total CPU and does not reset between rounds, halves or policy context replacements. This budget configuration has a distinct profile digest. The platform re-admits existing FPS competition versions using their original code bytes; students do not need to upload again. Passing versions are activated, while failed versions retain their records and an individual failure reason. Matches frozen under the old profile must finish on the old runtime pool before cutover.

The process profile has **3300/3301 seconds soft/hard CPU and 3300 seconds execution wall**, with a separate 300-second validation allowance. The 55-minute execution limit is independent of validation; these ceilings are not additive participant CPU budgets. The longer simulated game clock is separate from host wall time.

Timeout, cumulative exhaustion, exception, malformed output, invalid action, output limit, OOM and worker exit follow the participant-fault path: record the fault, disable that seat's policy and apply neutral controls thereafter. A legal but unavailable purchase/interaction is a receipt rejection, not that fault. When every seat fails, the Python runner emits the defined all-seats-forfeited terminal: faults remain recorded, ratings are unchanged, and each seat is win-rate eligible with zero win credit. Trusted runtime failures propagate as platform failures and cannot be disguised as neutral play. Truncated or host-killed jobs never become draws; only a complete 12:12 match earns a draw. Check match completion and faults in your result and log.

Each Python seat has a 128 MiB memory limit (container cgroup; the Python interpreter and numpy included; no swap) and a 5-second wall-clock limit to answer one `act` (20 seconds for initialization). The 64 cumulative seconds are shared by every decision: at the rule upper bound of about 80,000 decisions that is under 1 ms on average; a 20-minute match has about 24,000 decisions, about 2.7 ms each; 50 ms is a per-call ceiling, not an average allowance. "Execution budget exhausted" covers both a single callback over its CPU limit and exhaustion of the cumulative CPU. After a fault the seat gets the neutral action (no movement, no firing, no purchases) and the team plays a player short; a forfeiting seat's ladder rating cannot rise, and when its team did not win, teammates who did not forfeit keep their ladder rating unchanged. The upload check runs only the first 200 decisions (about 10 seconds of match time). Self-check: call `act` with the `observation` records from your own match logs, accumulate CPU with `time.process_time()` including `import`, `init` and JSON decoding, read peak memory with `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` (KiB on Linux) and leave headroom.

<a id="local-evaluation"></a>
## 10. Upload

The platform does not provide a simulator or SDK. The platform runs official matches and evaluations only. You can build an approximate local environment from the rules, your own `training.jsonl` logs and replays, using the map or circuit as an environment for training and optimization. Where applicable, use the [public circuit data](/docs/schema/maps/racing.html), [public FPS map data](/docs/schema/maps/fps.html), [Racing toolkit](/docs/schema/kits/agx-racing-kit.zip) and [FPS toolkit](/docs/schema/kits/agx-fps-kit.zip). These data and analysis tools are not a complete simulator. For other games, start from the rules and the public static maps, events and legal observations in your own matches.

First model observations, action legality, state transitions, timing and scoring. With fixed seeds and identical actions, compare stepwise observations, events and final results to identify approximation errors. Start with a racing corner, braking or pit stop; FPS navigation, visibility and combat; RTS gathering, construction and combat; or Kitchen routing, processing and task allocation, then combine these into a full strategy.

Use your environment for repeated self-play, offline parameter search and strategy optimization. You may also distill policies from your own legal decision data or train reinforcement learning (RL) models, then package and submit after local optimization. Training and inference must use only information legally visible at decision time. Omniscient replays can help check the environment, but must not become policy inputs or fabricated hidden observations. Keep seeds, maps and versions, and check generalization on matches held out from optimization. Local scores depend on approximation errors; official platform evaluations determine the result.

The ZIP root needs `agent.py`; helper `.py` modules, root `design.json` and numeric `.npz` weights are permitted. For this game omit design or use `{}`. Read weights from `Path(context["weights_dir"]) / "weights/model.npz"` using `numpy.load(..., allow_pickle=False)`. Never submit a venv, requirements, wheel, native library or pickle. ZIP/expanded limits are 64/128 MiB, at most 64 entries; per source/design file 256 KiB, total source/design 1 MiB; NPZ and actual tensor payload each at most 64 MiB. Complete request/response frames are limited to 1 MiB/64 KiB. See the shared Python packaging guide for all admission checks.


Only if the competition exposes this Python contract, upload your ZIP through its Python editor, wait for admission and select the accepted immutable version for future matches. For an already configured API the binary ZIP endpoint is `POST /api/v1/python-submissions/agents/{agent_id}/bundles` with `Idempotency-Key`; history is `GET /api/v1/python-submissions/agents/{agent_id}/bundles`. Keep the same key and bytes for an uncertain retry; web writes require CSRF. Inspect `admission`, `fault_code`, `contract_id`, `rules_version`, bundle hash and accepted version identity. Legacy JavaScript JSON source upload is a different path. Registration, admission and a completed match are separate steps; frozen jobs retain the submitted identity they were assigned. Availability follows the competition page.

<!-- fps54-current-source:start -->
| Value or contract | Current value |
| --- | --- |
| Format | MR12; first 13; max 24; overtime_half=3, overtime_limit=0 |
| Seat CPU | 2.6666666666666665 s/round; 64 s total (init included) |
| Init | 2 s |
| First act | 1 s |
| Later act | 50 ms |
| Parent CPU, wall | 3300/3301 CPU s; 3300 wall s; 300 validation s |
| Clocks | 60 Hz physics; 20 Hz decisions; 24 Hz recording |
| Phases | 6/115/5 s; buy deadline 1860 ticks (31 s, inclusive) |
| Opening cash | 800 |
| Objectives | plant 180; defuse 300/600 ticks; defuse <2.8 m; pickup <2.3 m; drop delay 90 ticks |
| Fuse | 40 s / 2400 ticks |
| Maps | dust2-cs2-v54, mirage-cs2-v54, borgo-r3-v54, molo-r3-v54, nevaio-r3-v54 |
| Catalogue | 24 weapons (knife included); 6 utilities; slots 0/1/2 |
| Economy | win 3250; objective win 3500; plant/defuse 300/300; planted loss +600; losses 1400/1900/2400/2900/3400 |
| Controls | analog [-1,1]; slots and zoom 0..2; signal/value 0..15; drop/pickup_id <=128 chars |
| Bundle & wire limits | 64/128 MiB ZIP/expanded; 64 entries; 256 KiB/file; 1 MiB total source; 64 MiB NPZ/tensors; 1 MiB/64 KiB request/response |
| Scores | win/loss 1/0, rank 0/1; draw 0.5, rank 0 |
<!-- fps54-current-source:end -->

<!-- fps54-catalogue:start -->
## Frozen purchase and weapon tables
All data below is read from the current code. IDs are shared across languages; cosmetic names are omitted. Weapon `slot` is the catalogue slot (1 primary, 2 secondary), while the action uses `weapon_slot` 0 primary, 1 secondary, 2 knife. T/CT mean the current attack/defense side, not permanent team IDs. Prices and base damage do not override purchase receipts, armor, body-part or distance adjudication. The device c4 is referee-issued and cannot be bought. Times are seconds unless suffixed `_ticks`, distances metres, speeds metres/second, spread/recoil radians and zoom FOV degrees.
```json
{
  "weapons": [
    {"id": "ak47", "category": "rifles", "teams": ["T"], "slot": 1, "price": 2700, "damage": 36, "headMultiplier": 4, "armorRatio": 1.55, "fireInterval": 0.1, "magazine": 30, "reserve": 90, "reloadTime": 2.466667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.98, "pellets": 1, "spread": 0.00701, "scopedSpread": 0.00701, "crouchingSpread": 0.00541, "movingSpread": 0.17506, "recoil": 0.021, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.460999999999999, "scopedMaxSpeed": 5.460999999999999, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.55, "fire_interval": 0.1, "reload_time": 2.466667, "reload_style": "magazine", "range_modifier": 0.98, "scoped_spread": 0.00701, "crouching_spread": 0.00541, "moving_spread": 0.17506, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.460999999999999, "scoped_max_speed": 5.460999999999999, "kill_reward": 300},

    {"id": "m4a1", "category": "rifles", "teams": ["CT"], "slot": 1, "price": 2900, "damage": 38, "headMultiplier": 3.475, "armorRatio": 1.4, "fireInterval": 0.1, "magazine": 20, "reserve": 60, "reloadTime": 3.066667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.94, "pellets": 1, "spread": 0.0055, "scopedSpread": 0.0054, "crouchingSpread": 0.0047, "movingSpread": 0.09288, "recoil": 0.017499999999999998, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.715, "scopedMaxSpeed": 5.715, "killReward": 300, "head_multiplier": 3.475, "armor_ratio": 1.4, "fire_interval": 0.1, "reload_time": 3.066667, "reload_style": "magazine", "range_modifier": 0.94, "scoped_spread": 0.0054, "crouching_spread": 0.0047, "moving_spread": 0.09288, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.715, "scoped_max_speed": 5.715, "kill_reward": 300},

    {"id": "awp", "category": "rifles", "teams": ["CT", "T"], "slot": 1, "price": 4750, "damage": 115, "headMultiplier": 4, "armorRatio": 1.95, "fireInterval": 1.455, "magazine": 5, "reserve": 10, "reloadTime": 3.666667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.99, "pellets": 1, "spread": 0.081, "scopedSpread": 0.0022, "crouchingSpread": 0.0608, "movingSpread": 0.17648, "recoil": 0.0546, "automatic": false, "zoomFovs": [90, 40, 10], "zoomStyle": "scope", "unzoomsAfterShot": true, "maxSpeed": 5.08, "scopedMaxSpeed": 2.54, "killReward": 100, "head_multiplier": 4, "armor_ratio": 1.95, "fire_interval": 1.455, "reload_time": 3.666667, "reload_style": "magazine", "range_modifier": 0.99, "scoped_spread": 0.0022, "crouching_spread": 0.0608, "moving_spread": 0.17648, "zoom_fovs": [90, 40, 10], "zoom_style": "scope", "unzooms_after_shot": true, "max_speed": 5.08, "scoped_max_speed": 2.54, "kill_reward": 100},

    {"id": "pistol", "category": "pistols", "teams": ["T"], "slot": 2, "price": 200, "damage": 30, "headMultiplier": 4, "armorRatio": 0.94, "fireInterval": 0.15, "magazine": 20, "reserve": 60, "reloadTime": 2.266667, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.85, "pellets": 1, "spread": 0.0076, "scopedSpread": 0.0206, "crouchingSpread": 0.0062, "movingSpread": 0.01, "recoil": 0.0126, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 0.94, "fire_interval": 0.15, "reload_time": 2.266667, "reload_style": "magazine", "range_modifier": 0.85, "scoped_spread": 0.0206, "crouching_spread": 0.0062, "moving_spread": 0.01, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "usp", "category": "pistols", "teams": ["CT"], "slot": 2, "price": 200, "damage": 35, "headMultiplier": 4, "armorRatio": 1.01, "fireInterval": 0.17, "magazine": 12, "reserve": 24, "reloadTime": 2.2, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.91, "pellets": 1, "spread": 0.0074, "scopedSpread": 0.0063999999999999994, "crouchingSpread": 0.00618, "movingSpread": 0.01387, "recoil": 0.0203, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.01, "fire_interval": 0.17, "reload_time": 2.2, "reload_style": "magazine", "range_modifier": 0.91, "scoped_spread": 0.0063999999999999994, "crouching_spread": 0.00618, "moving_spread": 0.01387, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "elite", "category": "pistols", "teams": ["CT", "T"], "slot": 2, "price": 300, "damage": 38, "headMultiplier": 4, "armorRatio": 1.15, "fireInterval": 0.12, "magazine": 30, "reserve": 60, "reloadTime": 3.766667, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.79, "pellets": 1, "spread": 0.009000000000000001, "scopedSpread": 0.012, "crouchingSpread": 0.00725, "movingSpread": 0.01785, "recoil": 0.0189, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.15, "fire_interval": 0.12, "reload_time": 3.766667, "reload_style": "magazine", "range_modifier": 0.79, "scoped_spread": 0.012, "crouching_spread": 0.00725, "moving_spread": 0.01785, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "p250", "category": "pistols", "teams": ["CT", "T"], "slot": 2, "price": 300, "damage": 38, "headMultiplier": 4, "armorRatio": 1.28, "fireInterval": 0.15, "magazine": 13, "reserve": 39, "reloadTime": 2.266667, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.9, "pellets": 1, "spread": 0.0111, "scopedSpread": 0.0111, "crouchingSpread": 0.008830000000000001, "movingSpread": 0.02, "recoil": 0.0182, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.28, "fire_interval": 0.15, "reload_time": 2.266667, "reload_style": "magazine", "range_modifier": 0.9, "scoped_spread": 0.0111, "crouching_spread": 0.008830000000000001, "moving_spread": 0.02, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "fiveseven", "category": "pistols", "teams": ["CT"], "slot": 2, "price": 500, "damage": 32, "headMultiplier": 4, "armorRatio": 1.823, "fireInterval": 0.15, "magazine": 20, "reserve": 40, "reloadTime": 2.266667, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.81, "pellets": 1, "spread": 0.0111, "scopedSpread": 0.0111, "crouchingSpread": 0.008830000000000001, "movingSpread": 0.04, "recoil": 0.017499999999999998, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.823, "fire_interval": 0.15, "reload_time": 2.266667, "reload_style": "magazine", "range_modifier": 0.81, "scoped_spread": 0.0111, "crouching_spread": 0.008830000000000001, "moving_spread": 0.04, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "deagle", "category": "pistols", "teams": ["CT", "T"], "slot": 2, "price": 700, "damage": 53, "headMultiplier": 3.9, "armorRatio": 1.864, "fireInterval": 0.225, "magazine": 7, "reserve": 21, "reloadTime": 2.2, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.85, "pellets": 1, "spread": 0.0062, "scopedSpread": 0.0062, "crouchingSpread": 0.00418, "movingSpread": 0.0481, "recoil": 0.0337400007, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.842, "scopedMaxSpeed": 5.842, "killReward": 300, "head_multiplier": 3.9, "armor_ratio": 1.864, "fire_interval": 0.225, "reload_time": 2.2, "reload_style": "magazine", "range_modifier": 0.85, "scoped_spread": 0.0062, "crouching_spread": 0.00418, "moving_spread": 0.0481, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.842, "scoped_max_speed": 5.842, "kill_reward": 300},

    {"id": "nova", "category": "mid", "teams": ["CT", "T"], "slot": 1, "price": 1050, "damage": 26, "headMultiplier": 4, "armorRatio": 1, "fireInterval": 0.88, "magazine": 8, "reserve": 32, "reloadTime": 0.466667, "reloadStyle": "shell", "range": 76.2, "rangeModifier": 0.7, "pellets": 9, "spread": 0.047, "scopedSpread": 0.047, "crouchingSpread": 0.04525, "movingSpread": 0.03675, "recoil": 0.07, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.588, "scopedMaxSpeed": 5.588, "killReward": 900, "head_multiplier": 4, "armor_ratio": 1, "fire_interval": 0.88, "reload_time": 0.466667, "reload_style": "shell", "range_modifier": 0.7, "scoped_spread": 0.047, "crouching_spread": 0.04525, "moving_spread": 0.03675, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.588, "scoped_max_speed": 5.588, "kill_reward": 900},

    {"id": "mag7", "category": "mid", "teams": ["CT"], "slot": 1, "price": 1300, "damage": 30, "headMultiplier": 4, "armorRatio": 1.5, "fireInterval": 0.85, "magazine": 5, "reserve": 15, "reloadTime": 2.5, "reloadStyle": "magazine", "range": 35.559999999999995, "rangeModifier": 0.45, "pellets": 8, "spread": 0.047, "scopedSpread": 0.047, "crouchingSpread": 0.04525, "movingSpread": 0.01599, "recoil": 0.07, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.715, "scopedMaxSpeed": 5.715, "killReward": 900, "head_multiplier": 4, "armor_ratio": 1.5, "fire_interval": 0.85, "reload_time": 2.5, "reload_style": "magazine", "range_modifier": 0.45, "scoped_spread": 0.047, "crouching_spread": 0.04525, "moving_spread": 0.01599, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.715, "scoped_max_speed": 5.715, "kill_reward": 900},

    {"id": "mp9", "category": "mid", "teams": ["CT"], "slot": 1, "price": 1250, "damage": 26, "headMultiplier": 4, "armorRatio": 1.2, "fireInterval": 0.07, "magazine": 30, "reserve": 60, "reloadTime": 2.133333, "reloadStyle": "magazine", "range": 91.44, "rangeModifier": 0.87, "pellets": 1, "spread": 0.0096, "scopedSpread": 0.0096, "crouchingSpread": 0.0086, "movingSpread": 0.02904, "recoil": 0.0147, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 600, "head_multiplier": 4, "armor_ratio": 1.2, "fire_interval": 0.07, "reload_time": 2.133333, "reload_style": "magazine", "range_modifier": 0.87, "scoped_spread": 0.0096, "crouching_spread": 0.0086, "moving_spread": 0.02904, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 600},

    {"id": "mp7", "category": "mid", "teams": ["CT", "T"], "slot": 1, "price": 1400, "damage": 30, "headMultiplier": 4, "armorRatio": 1.25, "fireInterval": 0.08, "magazine": 30, "reserve": 90, "reloadTime": 3.166667, "reloadStyle": "magazine", "range": 91.44, "rangeModifier": 0.87, "pellets": 1, "spread": 0.0106, "scopedSpread": 0.0106, "crouchingSpread": 0.0091, "movingSpread": 0.01986, "recoil": 0.0112, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.588, "scopedMaxSpeed": 5.588, "killReward": 600, "head_multiplier": 4, "armor_ratio": 1.25, "fire_interval": 0.08, "reload_time": 3.166667, "reload_style": "magazine", "range_modifier": 0.87, "scoped_spread": 0.0106, "crouching_spread": 0.0091, "moving_spread": 0.01986, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.588, "scoped_max_speed": 5.588, "kill_reward": 600},

    {"id": "bizon", "category": "mid", "teams": ["CT"], "slot": 1, "price": 1300, "damage": 27, "headMultiplier": 4, "armorRatio": 1.26, "fireInterval": 0.08, "magazine": 64, "reserve": 128, "reloadTime": 2.433333, "reloadStyle": "magazine", "range": 91.44, "rangeModifier": 0.8, "pellets": 1, "spread": 0.015, "scopedSpread": 0.015, "crouchingSpread": 0.0115, "movingSpread": 0.02757, "recoil": 0.0126, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 600, "head_multiplier": 4, "armor_ratio": 1.26, "fire_interval": 0.08, "reload_time": 2.433333, "reload_style": "magazine", "range_modifier": 0.8, "scoped_spread": 0.015, "crouching_spread": 0.0115, "moving_spread": 0.02757, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 600},

    {"id": "scar20", "category": "rifles", "teams": ["CT"], "slot": 1, "price": 5000, "damage": 80, "headMultiplier": 4, "armorRatio": 1.65, "fireInterval": 0.25, "magazine": 20, "reserve": 40, "reloadTime": 3.066667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.98, "pellets": 1, "spread": 0.0261, "scopedSpread": 0.0023, "crouchingSpread": 0.01965, "movingSpread": 0.15048, "recoil": 0.0217, "automatic": true, "zoomFovs": [90, 40, 15], "zoomStyle": "scope", "unzoomsAfterShot": false, "maxSpeed": 5.460999999999999, "scopedMaxSpeed": 3.048, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.65, "fire_interval": 0.25, "reload_time": 3.066667, "reload_style": "magazine", "range_modifier": 0.98, "scoped_spread": 0.0023, "crouching_spread": 0.01965, "moving_spread": 0.15048, "zoom_fovs": [90, 40, 15], "zoom_style": "scope", "unzooms_after_shot": false, "max_speed": 5.460999999999999, "scoped_max_speed": 3.048, "kill_reward": 300},

    {"id": "m4a4", "category": "rifles", "teams": ["CT"], "slot": 1, "price": 2900, "damage": 33, "headMultiplier": 4, "armorRatio": 1.4, "fireInterval": 0.09, "magazine": 30, "reserve": 120, "reloadTime": 3.066667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.97, "pellets": 1, "spread": 0.0055, "scopedSpread": 0.00535, "crouchingSpread": 0.0047, "movingSpread": 0.13788, "recoil": 0.0161, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.715, "scopedMaxSpeed": 5.715, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.4, "fire_interval": 0.09, "reload_time": 3.066667, "reload_style": "magazine", "range_modifier": 0.97, "scoped_spread": 0.00535, "crouching_spread": 0.0047, "moving_spread": 0.13788, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.715, "scoped_max_speed": 5.715, "kill_reward": 300},

    {"id": "ssg08", "category": "rifles", "teams": ["CT", "T"], "slot": 1, "price": 1700, "damage": 88, "headMultiplier": 4, "armorRatio": 1.7, "fireInterval": 1.25, "magazine": 10, "reserve": 20, "reloadTime": 3.7, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.98, "pellets": 1, "spread": 0.03198, "scopedSpread": 0.0032300000000000002, "crouchingSpread": 0.024059999999999998, "movingSpread": 0.12345, "recoil": 0.0231, "automatic": false, "zoomFovs": [90, 40, 15], "zoomStyle": "scope", "unzoomsAfterShot": true, "maxSpeed": 5.842, "scopedMaxSpeed": 5.842, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.7, "fire_interval": 1.25, "reload_time": 3.7, "reload_style": "magazine", "range_modifier": 0.98, "scoped_spread": 0.0032300000000000002, "crouching_spread": 0.024059999999999998, "moving_spread": 0.12345, "zoom_fovs": [90, 40, 15], "zoom_style": "scope", "unzooms_after_shot": true, "max_speed": 5.842, "scoped_max_speed": 5.842, "kill_reward": 300},

    {"id": "tec9", "category": "pistols", "teams": ["T"], "slot": 2, "price": 500, "damage": 33, "headMultiplier": 4, "armorRatio": 1.812, "fireInterval": 0.12, "magazine": 18, "reserve": 54, "reloadTime": 2.566667, "reloadStyle": "magazine", "range": 104.0384, "rangeModifier": 0.79, "pellets": 1, "spread": 0.0069, "scopedSpread": 0.01083, "crouchingSpread": 0.00568, "movingSpread": 0.00381, "recoil": 0.0161, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.812, "fire_interval": 0.12, "reload_time": 2.566667, "reload_style": "magazine", "range_modifier": 0.79, "scoped_spread": 0.01083, "crouching_spread": 0.00568, "moving_spread": 0.00381, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 300},

    {"id": "xm1014", "category": "mid", "teams": ["T"], "slot": 1, "price": 2000, "damage": 20, "headMultiplier": 4, "armorRatio": 1.6, "fireInterval": 0.35, "magazine": 7, "reserve": 32, "reloadTime": 0.6, "reloadStyle": "shell", "range": 76.2, "rangeModifier": 0.7, "pellets": 6, "spread": 0.045, "scopedSpread": 0.045, "crouchingSpread": 0.04325, "movingSpread": 0.03603, "recoil": 0.056, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.460999999999999, "scopedMaxSpeed": 5.460999999999999, "killReward": 900, "head_multiplier": 4, "armor_ratio": 1.6, "fire_interval": 0.35, "reload_time": 0.6, "reload_style": "shell", "range_modifier": 0.7, "scoped_spread": 0.045, "crouching_spread": 0.04325, "moving_spread": 0.03603, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.460999999999999, "scoped_max_speed": 5.460999999999999, "kill_reward": 900},

    {"id": "sawedoff", "category": "mid", "teams": ["T"], "slot": 1, "price": 1100, "damage": 32, "headMultiplier": 4, "armorRatio": 1.5, "fireInterval": 0.85, "magazine": 7, "reserve": 32, "reloadTime": 0.466667, "reloadStyle": "shell", "range": 35.559999999999995, "rangeModifier": 0.45, "pellets": 8, "spread": 0.069, "scopedSpread": 0.069, "crouchingSpread": 0.06725, "movingSpread": 0.0168, "recoil": 0.07, "automatic": false, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.334, "scopedMaxSpeed": 5.334, "killReward": 900, "head_multiplier": 4, "armor_ratio": 1.5, "fire_interval": 0.85, "reload_time": 0.466667, "reload_style": "shell", "range_modifier": 0.45, "scoped_spread": 0.069, "crouching_spread": 0.06725, "moving_spread": 0.0168, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.334, "scoped_max_speed": 5.334, "kill_reward": 900},

    {"id": "mac10", "category": "mid", "teams": ["T"], "slot": 1, "price": 1050, "damage": 29, "headMultiplier": 4, "armorRatio": 1.15, "fireInterval": 0.075, "magazine": 30, "reserve": 90, "reloadTime": 2.566667, "reloadStyle": "magazine", "range": 91.44, "rangeModifier": 0.8, "pellets": 1, "spread": 0.0139, "scopedSpread": 0.0139, "crouchingSpread": 0.010579999999999999, "movingSpread": 0.01399, "recoil": 0.0126, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 6.096, "scopedMaxSpeed": 6.096, "killReward": 600, "head_multiplier": 4, "armor_ratio": 1.15, "fire_interval": 0.075, "reload_time": 2.566667, "reload_style": "magazine", "range_modifier": 0.8, "scoped_spread": 0.0139, "crouching_spread": 0.010579999999999999, "moving_spread": 0.01399, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 6.096, "scoped_max_speed": 6.096, "kill_reward": 600},

    {"id": "galilar", "category": "rifles", "teams": ["T"], "slot": 1, "price": 1800, "damage": 30, "headMultiplier": 4, "armorRatio": 1.55, "fireInterval": 0.09, "magazine": 35, "reserve": 140, "reloadTime": 3.033333, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.98, "pellets": 1, "spread": 0.00937, "scopedSpread": 0.00838, "crouchingSpread": 0.00718, "movingSpread": 0.12356, "recoil": 0.0147, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "unzoomsAfterShot": false, "maxSpeed": 5.460999999999999, "scopedMaxSpeed": 5.460999999999999, "killReward": 300, "head_multiplier": 4, "armor_ratio": 1.55, "fire_interval": 0.09, "reload_time": 3.033333, "reload_style": "magazine", "range_modifier": 0.98, "scoped_spread": 0.00838, "crouching_spread": 0.00718, "moving_spread": 0.12356, "zoom_fovs": [90], "zoom_style": null, "unzooms_after_shot": false, "max_speed": 5.460999999999999, "scoped_max_speed": 5.460999999999999, "kill_reward": 300},

    {"id": "sg553", "category": "rifles", "teams": ["T"], "slot": 1, "price": 3000, "damage": 30, "headMultiplier": 4, "armorRatio": 2, "fireInterval": 0.11, "magazine": 30, "reserve": 90, "reloadTime": 2.766667, "reloadStyle": "magazine", "range": 208.0768, "rangeModifier": 0.98, "pellets": 1, "spread": 0.00641, "scopedSpread": 0.00411, "crouchingSpread": 0.00441, "movingSpread": 0.13601, "recoil": 0.0196, "automatic": true, "zoomFovs": [90, 45], "zoomStyle": "optic", "unzoomsAfterShot": false, "maxSpeed": 5.334, "scopedMaxSpeed": 3.81, "killReward": 300, "head_multiplier": 4, "armor_ratio": 2, "fire_interval": 0.11, "reload_time": 2.766667, "reload_style": "magazine", "range_modifier": 0.98, "scoped_spread": 0.00411, "crouching_spread": 0.00441, "moving_spread": 0.13601, "zoom_fovs": [90, 45], "zoom_style": "optic", "unzooms_after_shot": false, "max_speed": 5.334, "scoped_max_speed": 3.81, "kill_reward": 300},

    {"id": "knife", "category": "melee", "teams": ["T", "CT"], "slot": 3, "price": 0, "damage": 40, "headMultiplier": 1, "fireInterval": 0.5, "magazine": 0, "reserve": 0, "reloadTime": 0, "range": 1.2191999999999998, "pellets": 1, "spread": 0, "movingSpread": 0, "recoil": 0, "automatic": true, "zoomFovs": [90], "zoomStyle": null, "secondaryDamage": 65, "secondaryRange": 0.8128, "killReward": 1500, "head_multiplier": 1, "fire_interval": 0.5, "reload_time": 0, "moving_spread": 0, "zoom_fovs": [90], "zoom_style": null, "kill_reward": 1500}

  ],
  "equipment": {"armor": {"id": "armor", "category": "equipment", "teams": ["T", "CT"], "price": 650, "max_count": 1}, "helmet": {"id": "helmet", "category": "equipment", "teams": ["T", "CT"], "price": 1000, "max_count": 1}, "defusekit": {"id": "defusekit", "category": "equipment", "teams": ["CT"], "price": 400, "max_count": 1}, "hegrenade": {"id": "hegrenade", "category": "grenade", "teams": ["T", "CT"], "price": 300, "max_count": 1, "damage": 99, "radius": 8.9, "fuse": 1.5}, "flashbang": {"id": "flashbang", "category": "grenade", "teams": ["T", "CT"], "price": 200, "max_count": 2, "radius": 30.0, "duration": 4.5, "fuse": 1.5}, "smokegrenade": {"id": "smokegrenade", "category": "grenade", "teams": ["T", "CT"], "price": 300, "max_count": 1, "radius": 4.5, "duration": 18.0, "fuse": 2.0}, "molotov": {"id": "molotov", "category": "grenade", "teams": ["T"], "price": 400, "max_count": 1, "radius": 3.4, "duration": 7.0, "damage": 8, "fuse": 3.5}, "incgrenade": {"id": "incgrenade", "category": "grenade", "teams": ["CT"], "price": 500, "max_count": 1, "radius": 2.8, "duration": 5.5, "damage": 8, "fuse": 3.5}, "decoy": {"id": "decoy", "category": "grenade", "teams": ["T", "CT"], "price": 50, "max_count": 1, "radius": 2.0, "duration": 15.0, "damage": 5, "fuse": 2.0}, "c4": {"id": "c4", "category": "objective", "teams": ["T"], "price": 0, "max_count": 1, "purchasable": false}},
  "utilities": {"hegrenade": {"price": 300, "fuse_ticks": 90, "radius": 8.9, "duration_ticks": 0, "damage": 99.0}, "flashbang": {"price": 200, "fuse_ticks": 90, "radius": 30.0, "duration_ticks": 270}, "smokegrenade": {"price": 300, "fuse_ticks": 120, "radius": 4.5, "duration_ticks": 1080, "airborne_clear_ticks": 720}, "molotov": {"price": 400, "fuse_ticks": 210, "radius": 3.4, "duration_ticks": 420, "damage": 8.0, "damage_interval": 12}, "incgrenade": {"price": 500, "fuse_ticks": 210, "radius": 2.8, "duration_ticks": 330, "damage": 8.0, "damage_interval": 12}, "decoy": {"price": 50, "fuse_ticks": 120, "radius": 2.0, "duration_ticks": 900, "damage": 5.0, "sound_interval": 54}},
  "utility_round_limits": {"hegrenade": 1, "flashbang": 2, "smokegrenade": 1, "molotov": 1, "incgrenade": 1, "decoy": 1},
  "max_grenades": 4,
  "knife": {"slash_range": 1.2191999999999998, "stab_range": 0.8128, "hull_radius": 0.4064, "slash_interval": 0.5, "stab_interval": 1.0, "first_slash": 40, "repeat_slash": 25, "stab_damage": 65, "back_slash": 90, "back_stab": 180, "armor_scale": 0.85}
}
```
<!-- fps54-catalogue:end -->

## Five maps

A deterministic hash of seed selects one of five maps for the entire match; attack and defence swap after 12 rounds. A/B are plant sites in world metres. Bounds describe the collision asset, not an entirely walkable rectangle; navigation, ground and collision still govern movement.

| ID | Map | Asset bounds x/y/z m | A centre / radius m | B centre / radius m |
| --- | --- | --- | --- | --- |
| dust2-cs2-v54 | Dust2 | 36.60…217.04; -20.29…191.03; 11.87…44.49 | 166.69, 130.07, 22.54 / 6.1 | 167.37, 60.26, 20.20 / 6.3 |
| mirage-cs2-v54 | Mirage | 1.85…152.02; -4.04…146.33; 8.62…39.59 | 44.67, 88.18, 15.43 / 6.1 | 107.10, 47.87, 15.94 / 6.3 |
| borgo-r3-v54 | Borgo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 110.00, 88.00, 2.40 / 4 | 32.00, 76.00, 0.00 / 4 |
| molo-r3-v54 | Molo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 54.00, 90.00, 1.20 / 4 | 110.00, 44.00, 0.00 / 4 |
| nevaio-r3-v54 | Nevaio | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 112.00, 90.00, 2.40 / 4 | 52.00, 26.00, 0.00 / 4 |


<!-- fps-match-analysis:end -->

The match result `faults` field records each seat’s fault count. Open your match replay and download your own log to compare its observations and actions.

<!-- fps-match-analysis:start -->
## Five maps

A deterministic hash of seed selects one of five maps for the entire match; attack and defence swap after 12 rounds. A/B are plant sites in world metres. Bounds describe the collision asset, not an entirely walkable rectangle; navigation, ground and collision still govern movement.

| ID | Map | Asset bounds x/y/z m | A centre / radius m | B centre / radius m |
| --- | --- | --- | --- | --- |
| dust2-cs2-v54 | Dust2 | 36.60…217.04; -20.29…191.03; 11.87…44.49 | 166.69, 130.07, 22.54 / 6.1 | 167.37, 60.26, 20.20 / 6.3 |
| mirage-cs2-v54 | Mirage | 1.85…152.02; -4.04…146.33; 8.62…39.59 | 44.67, 88.18, 15.43 / 6.1 | 107.10, 47.87, 15.94 / 6.3 |
| borgo-r3-v54 | Borgo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 110.00, 88.00, 2.40 / 4 | 32.00, 76.00, 0.00 / 4 |
| molo-r3-v54 | Molo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 54.00, 90.00, 1.20 / 4 | 110.00, 44.00, 0.00 / 4 |
| nevaio-r3-v54 | Nevaio | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 112.00, 90.00, 2.40 / 4 | 52.00, 26.00, 0.00 / 4 |

## Obtaining data and fitting models from matches

The public materials do not include the complete static descriptor. Read and cache `map` on the first `act` call (`match_tick=0`), or use `observation.map` in your own log, not its metadata header. `nav` contains the full navigation graph, `ladders` the ladder descriptors, and `buy_zone` applies only to Dust2/Mirage. The descriptor also carries compatibility geometry/regions, source/collision asset references and, where present, `overview/labels/bot_waypoints`. Fields may be empty or absent; compatibility geometry and asset references are not the authoritative triangle collision or material files.

Read your weapon state at `observation.me.weapons[]`: `aim_punch/inaccuracy/trigger_state/reload_state`; empty slots may be null. Inspect observations after the relevant actions for trigger/reload details. Read action/economy receipts in subsequent observations at `observation.receipts[]`, which may include prices, refunds and item events; first-call receipts are empty. Complete movement, collision, recoil/accuracy, ballistics and rendering implementations and unpublished internal parameters are not supplied. Use your own match logs and replays to fit approximate responses and build your environment, without using hidden information as policy input.

Identify decision rows by your `seat` and an object-valued `observation`, rather than a fixed line number or only `type="decision"`: current raw rows have six keys, `seat/step/observation/action/applied_action/fault`, and may omit `type`. First verify `export_complete`, then pass the export directly to the toolkit's `calibrate/fit.py` (and racing `calibrate/fit_wet.py`), without adding tags. The fitters accept both untagged and `type="decision"` rows for your seat and skip metadata, outcome and export_complete. Check the output sample counts.

## Match logs and replays

The platform does not provide a simulator or SDK. The platform runs official matches and evaluations only. You can build an approximate local environment from the rules, your own `training.jsonl` logs and replays, using the map or circuit as an environment for training and optimization. Where applicable, use the [public circuit data](/docs/schema/maps/racing.html), [public FPS map data](/docs/schema/maps/fps.html), [Racing toolkit](/docs/schema/kits/agx-racing-kit.zip) and [FPS toolkit](/docs/schema/kits/agx-fps-kit.zip). These data and analysis tools are not a complete simulator. For other games, start from the rules and the public static maps, events and legal observations in your own matches.

First model observations, action legality, state transitions, timing and scoring. With fixed seeds and identical actions, compare stepwise observations, events and final results to identify approximation errors. Start with a racing corner, braking or pit stop; FPS navigation, visibility and combat; RTS gathering, construction and combat; or Kitchen routing, processing and task allocation, then combine these into a full strategy.

Use your environment for repeated self-play, offline parameter search and strategy optimization. You may also distill policies from your own legal decision data or train reinforcement learning (RL) models, then package and submit after local optimization. Training and inference must use only information legally visible at decision time. Omniscient replays can help check the environment, but must not become policy inputs or fabricated hidden observations. Keep seeds, maps and versions, and check generalization on matches held out from optimization. Local scores depend on approximation errors; official platform evaluations determine the result.

Open competition history from [My competitions](#/my-competitions), or visit #/matches/<job_id>. Public downloads provide frames (24 Hz pictures), events and static (map/circuit, roster and metadata); the player uses `/api/v1/python-submissions/recordings/{job_id}/replay/descriptor`, the matching `/replay/index`, and chunked streams. Spectator recordings are not the policy inputs visible at decision time. Signed-in owners also have “Download my log”: training.jsonl includes only frozen seats currently owned by the account. Replay visibility never grants another player’s log.

`GET /api/v1/python-submissions/competitions/{competition_id}/history` lists results, faults and replay_available. Public streams use `/api/v1/python-submissions/recordings/{job_id}/{frames|events|static}`. Query owned seats at `/api/v1/python-submissions/jobs/{job_id}/training-seats`, and download `/api/v1/python-submissions/jobs/{job_id}/training.jsonl`, optionally with `seat=<owned seat>`. Use your login session or account API key; gzip is supported. Guests or unowned seats return 404, missing/corrupt traces 409, and an expired 30-day download window 410. Archive status is separate from the online download window.

Read JSONL one line at a time: metadata binds the match, seed and owned seats; decision rows contain the actual legal observation, action, seat and decision order; outcome records the result and the final export_complete row supplies completion and row-count checks. A missing completion row means an incomplete export. Locate a problem in events and replay, then compare the corresponding decision inputs and actions. For racing inspect the selected circuit, design_rejected, pits, tyres and stalls; for FPS inspect rounds, visibility, movement, purchases, bomb possession and deaths. Keep the seed, map/circuit and frozen version when comparing matches. Never feed omniscient replay data or future events into a policy. See the [API reference](#/docs/common).
<!-- fps-match-analysis:end -->
