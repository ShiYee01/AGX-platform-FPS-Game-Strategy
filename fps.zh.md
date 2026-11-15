# 多人爆破 · AI 助手开发指南

<!-- generated:local-development-resources begin -->
## 本地开发资源

> 数据和分析工具，不是完整模拟器。

- [下载 FPS 工具包](/docs/schema/kits/agx-fps-kit.zip) — 包含地图读取、日志标定与近似优化示例。
- [公开 FPS 地图数据](/docs/schema/maps/fps.html) — 查看和下载公开地图几何、导航与目标点数据。
<!-- generated:local-development-resources end -->

本文说明当前 FPS 赛事使用的 `rsi-fps-5.5` 合同。参赛入口和开放状态以赛事页面为准；历史对局保留自己的合同。[中文 Markdown](/docs/agent/fps.zh.md) · [English Markdown](/docs/agent/fps.en.md) · [Python 打包说明](#/docs/python-submissions)。

<a id="contract-status"></a>
## 1. 参赛说明

平台不提供模拟器或 SDK，仅运行正式对局或评测。你可以根据规则文档、自己对局的 `training.jsonl` 和回放，在本地自建近似环境，把地图或赛道作为环境进行训练与优化。结合适用的[公开赛道数据](/docs/schema/maps/racing.html)、[公开 FPS 地图数据](/docs/schema/maps/fps.html)以及[赛车工具包](/docs/schema/kits/agx-racing-kit.zip)、[FPS 工具包](/docs/schema/kits/agx-fps-kit.zip)；这些数据与分析工具不等于完整模拟器。其他项目可从规则和自己对局的公开静态地图、事件与合法观察逐步建模。

先复刻观察、动作合法性、状态转移、计时和计分，再用固定种子与相同动作比较逐步观察、事件和最终结果，定位近似模型的偏差。赛车可先优化某个弯道、制动或进站；FPS 可先做导航、视野和交战；RTS 可先做采集、建造与战斗；厨房可先做寻路、工序和分工，再逐步组合完整策略。

在自建环境中反复做自博弈、离线参数搜索与策略优化，也可以用本人合法决策数据蒸馏策略或训练强化学习（RL）模型，优化充分后再打包提交。训练与推理只使用决策当时合法可见的信息；全知回放可用于核对环境，不能作为策略输入，也不能据此逆造隐藏观察。保留种子、地图和版本，用未参与优化的对局检查泛化；本地成绩受近似误差影响，最终以平台正式评测为准。

从本页的最小示例开始，按 Python 提交指南上传 ZIP；开放状态以比赛页为准。

<a id="rules"></a>
## 2. 规则、回合与结算

十个固定席位组成队伍 0（0–4）和队伍 1（5–9），各席 role 都是 0。攻守交换不改变队伍、席位或策略进程。MR12 即每半场 12 回合，先得 13 胜者获胜，最多 24 回合。第 12 回合结束后换边，清空装备，每席现金重置为 800。默认 `overtime_limit=0`，12:12 立即平局。MR3 加时已实现（`overtime_half=3`）但默认关闭；只有可信合同变更可以启用，策略不能启用。`round_index` 从 0 开始，下半场始于索引 12。

胜队各席 score=1、败队各席为 0，rank 分别为 0/1。平局十席 score=0.5、rank=0，按既有团队平局把 ranks=[0,0] 交给 OpenSkill；个人 mu、sigma、展示分仍可能变化。现金、击杀与回合差不另加排名分。

物理 60 Hz，策略决策 20 Hz（每三 tick 一次），公开录像 24 Hz。决策边界先冻结十席合法观察，收齐并校验动作后才推进世界；非决策 tick 沿用上次动作。每物理 tick 调用一次 `Arena.step`，由它安排策略调用，不要在循环里自行再次逐席调用策略。

| 阶段或目标 | 规则 |
| --- | --- |
| `buy` 冻结 | 6 秒 / 360 tick；禁用战斗与目标操作 |
| `live` | 未安放情况下最多 115 秒 / 6900 tick 后超时 |
| `post` | 回合间 5 秒 / 300 tick |
| 购买 / 退款窗口 | 回合起点后 31 秒 / 1860 tick，含截止点；即冻结加 live 前 25 秒 |
| 安放 | 携带者在合法点连续 `use="plant"` 180 tick / 3 秒 |
| 拆除 | 连续 `use="defuse"`；有钳 300 tick，无钳 600；距离严格小于 2.8 米 |
| 引信 | 安放后 40 秒 / 2400 tick；同 tick 拆除与引信到期时，到期优先 |
| 掉落炸弹 | 距离小于 2.3 米且可见时自动拾取；主动丢弃者需等 90 tick |

安放前可因歼灭或未安放超时结束回合；安放后即使进攻方全部死亡，目标时钟仍继续。成功拆除或爆炸结算；爆炸直接结束回合，不另加 HP 伤害。目标交互期间锁定移动与开火，完成或解除后释放。距离、视线与交互均由裁判判定，请求合法不代表一定成功。

目标裁定时，执行者必须存活、着地且速度不超过 0.1 米／秒，持续对应 use 并满足包点／职责／距离条件；忙于开火、装填、投掷或切枪的动作不能推进。Arena 会先选择并锁定合格执行者、抑制冲突控制，条件失效则中断进度；多个新的拆除者按席位顺序选择，不按最近距离（公开规则表、`:156`、`:175`、公开规则表）。

<a id="economy"></a>
## 3. 经济与库存

服务端选择 `ECONOMY_RULES=BALANCED`，参赛者不能通过 config、design 或动作修改。现金上限 16000，开局与下半场现金均为 800。普通回合保留现金；存活者保留允许装备，死亡者失去装备。当前规则在新回合为保留枪械补满弹药并重置武器就绪与后坐时钟。半场重置对存活者同样清空库存，再发默认手枪 / 刀，并重置败补档位。每次转换后以实际 `me.slots`、`me.weapons` 与回执为准。

| 交易 | 金额或条件 |
| --- | --- |
| 普通回合胜利 | 胜队每席 3250 |
| 爆炸 / 拆除获胜 | 胜队每席 3500 |
| 败补档 | 1400 / 1900 / 2400 / 2900 / 3400；初始索引 1，首败发 1900 |
| 档位更新 | 结算后败队升一档、胜队降一档，限于索引 0–4 |
| 个人安放 / 拆除 | 300 / 300 |
| 安放后被拆，进攻方失败 | 进攻方每席额外 600 |
| 未安放超时且存活的进攻者 | 无普通败款 |
| 击杀 | 按武器，冻结目录及权威现金账本为准 |

购买 / 退款要求玩家存活、处于己方出生购买区、窗口未关且目录物品符合阵营限制。退款还需对应的合资格购买记录，重复请求不会重复发钱。三武器槽为主武器 / 副武器 / 刀（0/1/2）；有 23 把枪及六类道具。价格、阵营限制、道具限额与武器时钟见 公开规则表 及当前经济规则。使用 `ak47`、`m4a1`、`defusekit`、`hegrenade` 等具体 ID，不沿用旧的泛称武器名。库存物品句柄是不透明标识，不能从中解析种子或未来信息；拾取 / 退款回执里的唯一 `item_id` 与武器种类不同。

<a id="maps"></a>
## 4. 五图与选择

| 显示名 | `map_id` |
| --- | --- |
| Dust2 | `dust2-cs2-v54` |
| Mirage | `mirage-cs2-v54` |
| Borgo | `borgo-r3-v54` |
| Molo | `molo-r3-v54` |
| Nevaio | `nevaio-r3-v54` |

可信整数对局种子为整局选择一图：对 `rsi-fps-5.4:map:{seed}` 做 SHA-256，按大端整数对五取模，对应上表顺序。这是五个等权轮换条目，不保证每五局严格轮一遍。策略拿不到对局种子；`init.context.seed` 是独立公开的策略随机域，不能用来重建隐藏抽样。

坐标单位米，x/y 水平、z 向上，yaw/pitch 为弧度。正 yaw 面向 `(cos(yaw), -sin(yaw))`，正 pitch 向上。静态描述把三角几何 / 材质引用、圆形区域、出生点、目标点与导航来源绑定到哈希。按 `map_id` 与 `static_schema_hash` 缓存首次 `map`，后续观察不再包含它。`source-adjacency` 仅为导航来源，不证明路线可通行；Mirage 材质 / 穿透重建不冒充原始源数据。

正式环境要求通过源码 / 二进制 / ABI 校验的 `NativeCollisionWorld`，缺失或陈旧产物会拒绝启动。显式 reference 碰撞仅用于离线 probe；本地后备实现与渲染网格都不能更改权威空间规则。

<a id="observation-schema"></a>
## 5. 合法观察合同

`act(observation)` 接收该席独立 JSON 对象，不接收 `arena.frame()` 或全知录像。下表覆盖顶层字段；集合可能为空，依状态存在的子字段须先检查再用。

| 字段 | 含义 |
| --- | --- |
| `rules_version`, `seat`, `team`, `side`, `role` | 合同身份；side 为 `attack`/`defend`，role 为 0 |
| `match_tick`, `round_index`, `round_tick`, `phase`, `phase_remaining_ticks` | 整数时钟；phase 为 `buy`、`live`、`post` 或终局 `finished` |
| `round_wins`, `alive_by_team`, `attack_team` | 固定队伍公开比分、存活数、进攻队伍 |
| `period`, `overtime_number`, `win_target` | 默认赛制为 `regulation`、0、13；只有可信合同可以启用已实现的加时 |
| `buy_deadline_tick`, `loss_level` | 绝对购买截止 tick 与己队败补档位 |
| `me` | 自己的位置、朝向、生命、现金、库存、姿态、武器时钟 |
| `teammates` | 其余队友的 `seat`、`alive`、`cash`、`zone` 与允许的 `equipment` |
| `visible` | 当前可见敌人的合法姿态，不含敌方私有生命 / 经济 / 库存 |
| `sounds` | 仅听到的 `{type, direction, distance_band}`，不暴露精确声源坐标或身份 |
| `heard` | 空的历史兼容集合；使用 `sounds` |
| `bomb` | 仅允许知道的炸弹状态，隐藏位置不能作为目标坐标 |
| `world_items` | 可见掉落物 `{id, kind, position}` |
| `messages`, `receipts` | 允许的队友通信与自己的动作 / 经济回执 |
| `map_id`, `static_schema_hash`, 首次 `map` | 静态身份与仅首次下发的描述 |

`me` 包含 `x/y/z`、`yaw/pitch`、`vx/vy/vz`、`hp`、`armor`、`helmet`、`cash`、`alive`、`crouch`、`ammo`、`reload`、`recoil`、`stamina`、`lean_offset`、`active_slot`、`ads_progress`、`sprinting`、`grounded`、`slots`、`throwables`、`weapons`、`pickup_ready_tick`、`switch_until`、`throw_ready`、`throwable_kinds`、`blind_ticks`、`weapon_status`、`carrying_bomb`、`has_kit`。当前观察包含 `walk`、`quiet`、`duck`、`zoom_level`、`ladder_id`、`movement_mode`、`shot_ready`。空槽可能为 null，读取弹药前先检查当前武器。渲染用 `zoom_fov` 不是额外策略输入。

合同不包含 `scenario_seed`、`map.render`、敌人 HP / 现金 / 库存以及全知 `audio_events/audio_ambient`。观众音频、全知帧与训练 / 录像导出均不授权扩大策略输入。不能从全知录像重建并冒充合法观察；评估时应保留真正的私有决策轨迹。

敌人条目仅提供 `seat/team/x/y/z/yaw/pitch/crouch/lean/parts/weapon`：当前持枪的外观 ID（或 null）是合法信息，但敌人弹药、生命、现金及其余库存不提供。可见部位提示为 `head/chest/abdomen`，不保证未来命中（公开规则表、公开规则表）。

`sounds.direction` 为 `self/unknown/left/right/center`，立体声不能区分前后；`distance_band` 为 `self/unknown/near/mid/far`。普通有位置的声音 near 为小于 8 米、mid 为小于 20 米，否则 far；仅滤波的提示保留 unknown 距离。不提供发声席位、队伍、方位角或精确声源。此合同的 `heard` 是空的历史兼容字段；应读 `sounds`，不能套用旧声音枚举／距离阈值（公开规则表、公开规则表）。

`bomb.state` 与 `fuse_end_tick` 始终存在；敌方隐藏信息可能只有 `unknown` 与 null。`id/carrier/position/site` 只在本队进攻或合法可见时提供，公开安装时钟不披露隐藏包点。`plant_progress` 仅属当前安放者，`defuse_progress/defuse_duration` 仅属当前拆除者（公开规则表）。本人 `me.weapons` 按三个动作槽索引，可有 null；单枪含 `id/ammo/reserve/shot_ready/reload_until/recoil_pitch/recoil_yaw/shots/last_shot` 及本人账本、后坐、扳机和装填状态。应读取本人实际时钟，不能猜测敌方时钟（公开规则表、公开规则表）。

完整首拍另有 `me` 与静态 `map`；后续回调省略 `map` 但保留其身份。敌情／声音集合为空是合法情况。

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
## 6. 完整动作合同

返回 JSON 对象；缺字段补中性默认值，`{}` 合法。额外键、非有限数、用 bool 充数、错误枚举或类型均非法，运行时不会替你裁剪越界值。语法合法但当前不可用的请求可产生拒绝回执，不一定记策略故障。

| 字段 | 类型、范围或取值 |
| --- | --- |
| `move_forward`, `move_right`, `yaw_rate`, `pitch_rate`, `climb` | [-1,1] 有限数，默认 0 |
| `jump`, `crouch`, `duck`, `walk`, `fire`, `fire_secondary`, `reload`, `sprint`, `ads` | bool，默认 false；`duck` 是 `crouch` 别名 |
| `weapon_slot` | 整数 0/1/2，默认 1 |
| `zoom_level` | 整数 0/1/2，默认 0；具体武器决定支持的倍率层 |
| `ladder` | `none` / `attach` / `detach`，默认 `none` |
| `buy` | `none` 或冻结武器 / 装备目录 ID |
| `refund_item_id` | null 或合资格物品句柄 / 来源种类字符串 |
| `drop` | 至多 128 字符的字符串；`none` 或库存槽 / 炸弹请求 |
| `pickup_id` | null 或非空物品句柄，至多 128 字符；配合 `use="pickup"` |
| `use` | `none` / `plant` / `defuse` / `pickup` |
| `throw` | `none` / `hegrenade` / `flashbang` / `smokegrenade` / `molotov` / `incgrenade` / `decoy` |
| `throw_state` | `idle` / `prime` / `release` / `cancel`，默认 `idle` |
| `throw_mode` | `full` / `lob` / `drop`，默认 `full` |
| `signal` | 整数 0–15，默认 0 |
| 可选 `message` | 严格 `{kind, zone, value}`；kind 属于 `MESSAGE_KINDS`，zone 是首次 `map.route_landmarks` 的键，value 是整数 0–15 |

消息类型见 公开规则表，不是自由文本。资源冲突、缺装备、阶段限制、距离与冷却由引擎裁决。投掷需遵守预备 / 释放 / 取消状态和力度；仅返回道具种类不证明成功投出。瞄准镜、切枪、装填和后坐按冻结枪械目录执行；冻结与 post 禁用开火，装填和狙击枪射击会退镜。

以下是彼此独立的合法请求示例，不保证成功：在开放购买区域买护甲；满足条件时持续安放／拆除；先拉烟雾弹，再在后续决策释放。库存、距离与冷却等拒绝仍以裁判回执为准。

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
## 7. 示例策略

在 PPT 示例基础上修了寻路和脱困：公开导航、坡面路点、持续脱困、移动射击和爆破目标；弱策略，不保证获胜。

入口签名为 `def act(observation):`，返回本文动作对象。

下载唯一的[最小示例 ZIP](/docs/schema/fps.example.zip)（[agent.py](/docs/schema/fps.example.agent.py)）。ZIP 可原样上传，无需安装额外工具。

在赛事页面创建或选择自己的 Agent，上传 ZIP，等待准入通过，然后选择接受的版本并激活参赛。赛车 ZIP 根目录为 agent.py 和 design.json；其他三赛仅为 agent.py。也可按课程说明把下载源码完整复制到同名编辑器文件。

<a id="ten-seat-driver"></a>
## 8. 策略开发

平台不提供模拟器或 SDK，仅运行正式对局或评测。你可以根据规则文档、自己对局的 `training.jsonl` 和回放，在本地自建近似环境，把地图或赛道作为环境进行训练与优化。结合适用的[公开赛道数据](/docs/schema/maps/racing.html)、[公开 FPS 地图数据](/docs/schema/maps/fps.html)以及[赛车工具包](/docs/schema/kits/agx-racing-kit.zip)、[FPS 工具包](/docs/schema/kits/agx-fps-kit.zip)；这些数据与分析工具不等于完整模拟器。其他项目可从规则和自己对局的公开静态地图、事件与合法观察逐步建模。

先复刻观察、动作合法性、状态转移、计时和计分，再用固定种子与相同动作比较逐步观察、事件和最终结果，定位近似模型的偏差。赛车可先优化某个弯道、制动或进站；FPS 可先做导航、视野和交战；RTS 可先做采集、建造与战斗；厨房可先做寻路、工序和分工，再逐步组合完整策略。

在自建环境中反复做自博弈、离线参数搜索与策略优化，也可以用本人合法决策数据蒸馏策略或训练强化学习（RL）模型，优化充分后再打包提交。训练与推理只使用决策当时合法可见的信息；全知回放可用于核对环境，不能作为策略输入，也不能据此逆造隐藏观察。保留种子、地图和版本，用未参与优化的对局检查泛化；本地成绩受近似误差影响，最终以平台正式评测为准。

<a id="budgets"></a>
## 9. 预算与超限处理

每席 **当前最多 24 回合共 64 累计 CPU 秒**，含初始化。这是整局总账，不在每回合或半场重新发放，也不能向别席转账。初始化上限 2 秒，普通回调上限 50 ms，仍受累计账本限制；较短对局不产生额外额度。Python 内存与调用次数按当前 Python 运行时配置 执行，旧 JavaScript heap 上限不代表 Python RSS。

当前进程 profile 为**软 / 硬 CPU 3300/3301 秒、执行 wall 3300 秒**，另有独立验证预算 300 秒。55 分钟执行上限与验证预算分开，不能把这些上限相加作为策略 CPU 额度；更严格的端到端验收门仍需单独正式检查。模拟游戏时钟与宿主 wall 不同。这些是正式运行上限，实际资源故障会随对局结果报告。

超时、累计耗尽、异常、畸形输出、非法动作、输出超限、OOM、worker 退出走参赛者故障路径：记录故障，禁用该席策略，后续使用中性控制。合法但不可用的购买 / 交互是回执拒绝，不等同故障。全席失败时，Python runner 产出明确的全席弃权终局：故障照记、不改 rating；各席计入胜率样本，胜场信用为零。可信运行时错误作为平台失败向上传播，不能伪装为中性动作。截断或宿主杀掉的任务不能算平局；只有完整打成 12:12 才能平局。把运行当验收证据前，须检查完成状态、故障、父进程用量回执与冻结身份。

<a id="local-evaluation"></a>
## 10. 上传

平台不提供模拟器或 SDK，仅运行正式对局或评测。你可以根据规则文档、自己对局的 `training.jsonl` 和回放，在本地自建近似环境，把地图或赛道作为环境进行训练与优化。结合适用的[公开赛道数据](/docs/schema/maps/racing.html)、[公开 FPS 地图数据](/docs/schema/maps/fps.html)以及[赛车工具包](/docs/schema/kits/agx-racing-kit.zip)、[FPS 工具包](/docs/schema/kits/agx-fps-kit.zip)；这些数据与分析工具不等于完整模拟器。其他项目可从规则和自己对局的公开静态地图、事件与合法观察逐步建模。

先复刻观察、动作合法性、状态转移、计时和计分，再用固定种子与相同动作比较逐步观察、事件和最终结果，定位近似模型的偏差。赛车可先优化某个弯道、制动或进站；FPS 可先做导航、视野和交战；RTS 可先做采集、建造与战斗；厨房可先做寻路、工序和分工，再逐步组合完整策略。

在自建环境中反复做自博弈、离线参数搜索与策略优化，也可以用本人合法决策数据蒸馏策略或训练强化学习（RL）模型，优化充分后再打包提交。训练与推理只使用决策当时合法可见的信息；全知回放可用于核对环境，不能作为策略输入，也不能据此逆造隐藏观察。保留种子、地图和版本，用未参与优化的对局检查泛化；本地成绩受近似误差影响，最终以平台正式评测为准。


ZIP 根必须有 `agent.py`；允许辅助 `.py` 模块、根 `design.json` 与数值 `.npz` 权重。本赛省略 design 或使用 `{}`。从 `Path(context["weights_dir"]) / "weights/model.npz"` 以 `numpy.load(..., allow_pickle=False)` 读取权重；不能提交 venv、requirements、wheel、原生库或 pickle。ZIP / 解包上限 64/128 MiB，至多 64 项；单源码 / design 文件 256 KiB，源码 / design 合计 1 MiB；NPZ 文件与实际张量各至多 64 MiB；完整请求 / 响应帧为 1 MiB/64 KiB。其余准入校验见共享 Python 打包说明。


仅当赛事显示此 Python 合同时，才通过 Python 编辑器上传 ZIP，等待准入，选择已接受的不可变版本参与未来对局。已配置 API 的二进制 ZIP 入口是 `POST /api/v1/python-submissions/agents/{agent_id}/bundles`，带 `Idempotency-Key`；历史查询为 `GET /api/v1/python-submissions/agents/{agent_id}/bundles`。不确定结果的重试保持同一个 key 与字节，网页写操作需 CSRF。核对 `admission`、`fault_code`、`contract_id`、`rules_version`、bundle hash 与接受版本身份。旧 JavaScript JSON 源码上传是另一条路径；报名、准入、完整对局彼此独立，冻结任务保留指派时的投稿身份。开放状态以赛事页面为准。

<!-- fps54-current-source:start -->
| 数值或合同 | 当前值 |
| --- | --- |
| 赛制 / Format | MR12; first 13; max 24; overtime_half=3, overtime_limit=0 |
| 每席 CPU / Seat CPU | 2.6666666666666665 s/round; 64 s total (init included) |
| 初始化 / Init | 2 s |
| 回调 / Callback | 50 ms |
| 父进程 / Parent CPU, wall | 3300/3301 CPU s; 3300 wall s; 300 validation s |
| 时钟 / Clocks | 60 Hz physics; 20 Hz decisions; 24 Hz recording |
| 阶段 / Phases | 6/115/5 s; buy deadline 1860 ticks (31 s, inclusive) |
| 初始资金 / Opening cash | 800 |
| 目标 / Objectives | plant 180; defuse 300/600 ticks; defuse <2.8 m; pickup <2.3 m; drop delay 90 ticks |
| 引信 / Fuse | 40 s / 2400 ticks |
| 地图 / Maps | dust2-cs2-v54, mirage-cs2-v54, borgo-r3-v54, molo-r3-v54, nevaio-r3-v54 |
| 武器 / Catalogue | 24 weapons (knife included); 6 utilities; slots 0/1/2 |
| 经济 / Economy | win 3250; objective win 3500; plant/defuse 300/300; planted loss +600; losses 1400/1900/2400/2900/3400 |
| 动作 / Controls | analog [-1,1]; slots and zoom 0..2; signal/value 0..15; drop/pickup_id <=128 chars |
| 打包 / Bundle & wire limits | 64/128 MiB ZIP/expanded; 64 entries; 256 KiB/file; 1 MiB total source; 64 MiB NPZ/tensors; 1 MiB/64 KiB request/response |
| 比分 / Scores | win/loss 1/0, rank 0/1; draw 0.5, rank 0 |
<!-- fps54-current-source:end -->

<!-- fps54-catalogue:start -->
## 冻结购买与武器表
以下数据直接读取当前代码，标识在中英文中相同，省略外观名称。武器目录 `slot` 为 1 主武器、2 副武器，动作 `weapon_slot` 则为 0 主武器、1 副武器、2 刀。T／CT 指当前进攻／防守职责，不是永久队号。标价与基础伤害不能覆盖实际购买回执、护甲、部位和距离裁判。c4 由裁判发放，不可购买。时间为秒（`_ticks` 后缀为拍），距离为米，速度为米／秒，散布／后坐为弧度，缩放视场为度。
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



整局结果中的 `faults` 记录每个席位的故障次数。打开本人对局页的回放，并下载本人日志，核对当时的观察和动作。

<!-- fps-match-analysis:start -->
## 五张地图

服务器按 seed 的固定哈希选择五图之一，整局共用同图；12 回合后交换攻守。A/B 是放置区域，坐标为世界米制；范围是碰撞资产包围盒，不能据此假设整块区域可行走。合法移动仍以导航、地面与碰撞为准。

| ID | 地图 | 资产范围 x/y/z m | A 中心 / 半径 m | B 中心 / 半径 m |
| --- | --- | --- | --- | --- |
| dust2-cs2-v54 | Dust2 | 36.60…217.04; -20.29…191.03; 11.87…44.49 | 166.69, 130.07, 22.54 / 6.1 | 167.37, 60.26, 20.20 / 6.3 |
| mirage-cs2-v54 | Mirage | 1.85…152.02; -4.04…146.33; 8.62…39.59 | 44.67, 88.18, 15.43 / 6.1 | 107.10, 47.87, 15.94 / 6.3 |
| borgo-r3-v54 | Borgo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 110.00, 88.00, 2.40 / 4 | 32.00, 76.00, 0.00 / 4 |
| molo-r3-v54 | Molo | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 54.00, 90.00, 1.20 / 4 | 110.00, 44.00, 0.00 / 4 |
| nevaio-r3-v54 | Nevaio | -90.00…234.00; -90.00…218.00; -0.25…8.90 | 112.00, 90.00, 2.40 / 4 | 52.00, 26.00, 0.00 / 4 |

## 对局日志与回放

平台不提供模拟器或 SDK，仅运行正式对局或评测。你可以根据规则文档、自己对局的 `training.jsonl` 和回放，在本地自建近似环境，把地图或赛道作为环境进行训练与优化。结合适用的[公开赛道数据](/docs/schema/maps/racing.html)、[公开 FPS 地图数据](/docs/schema/maps/fps.html)以及[赛车工具包](/docs/schema/kits/agx-racing-kit.zip)、[FPS 工具包](/docs/schema/kits/agx-fps-kit.zip)；这些数据与分析工具不等于完整模拟器。其他项目可从规则和自己对局的公开静态地图、事件与合法观察逐步建模。

先复刻观察、动作合法性、状态转移、计时和计分，再用固定种子与相同动作比较逐步观察、事件和最终结果，定位近似模型的偏差。赛车可先优化某个弯道、制动或进站；FPS 可先做导航、视野和交战；RTS 可先做采集、建造与战斗；厨房可先做寻路、工序和分工，再逐步组合完整策略。

在自建环境中反复做自博弈、离线参数搜索与策略优化，也可以用本人合法决策数据蒸馏策略或训练强化学习（RL）模型，优化充分后再打包提交。训练与推理只使用决策当时合法可见的信息；全知回放可用于核对环境，不能作为策略输入，也不能据此逆造隐藏观察。保留种子、地图和版本，用未参与优化的对局检查泛化；本地成绩受近似误差影响，最终以平台正式评测为准。

从[我的比赛](#/my-competitions)进入赛事历史，或打开该局 #/matches/<job_id>。公开下载提供 frames（24 Hz 画面）、events（事件）和 static（地图/赛道、阵容与元数据）；播放器使用 `/api/v1/python-submissions/recordings/{job_id}/replay/descriptor`、同前缀 `/replay/index` 和分块流。公开录像是观赛信息，不是策略当时可见的输入。登录后，本人对局另有「下载我的日志」：training.jsonl 仅包含当前账号实际拥有的冻结席位，公开观赛权限不能获得他人日志。

`GET /api/v1/python-submissions/competitions/{competition_id}/history` 查询赛果、故障与 replay_available；公开流使用 `/api/v1/python-submissions/recordings/{job_id}/{frames|events|static}`。本人席位用 `/api/v1/python-submissions/jobs/{job_id}/training-seats` 查询，日志用同前缀 `/jobs/{job_id}/training.jsonl` 下载；可带 `seat=<本人席号>`。沿用登录会话或账户 API key，支持 gzip；游客或他人席位 404、轨迹缺失/损坏 409、30 天下载窗口到期 410。归档状态与在线下载窗口不同。

按 JSONL 逐行读取：首行 metadata 绑定赛局、种子和本人席位，decision 行给出当时合法 observation、action、席位与决策顺序，outcome 行给出结果，末行 export_complete 提供完整性与行数校验；缺少末行不能当作完整导出。先把事件和录像定位到出错时刻，再比较对应决策的观测与动作；赛车检查所选赛道、design_rejected、进站、轮胎与停滞，FPS 检查回合、视野、移动、购买、携包与死亡事件。跨局比较时保留种子、赛道/地图和冻结版本，不把全知录像或未来事件作为策略输入。通用接口见[公共 API](#/docs/common)。
<!-- fps-match-analysis:end -->
