# FPS 对局01：赛前测试（V0）

| 项目 | 记录 |
| --- | --- |
| 比赛 ID | `633b4a9d-c271-444b-9155-14f67e96aae0` |
| 对局日期（用户说明） | 2026-11-14，课程比赛开始前 |
| 分类 | 赛前测试；不纳入第2～11局的正式十场基线主表 |
| 归档日期 | 2026-11-15，Asia/Shanghai |
| 实际参赛策略 | V0 工具包原版 |
| 平台版本 ID | `7d30f64b-e6f0-4298-92ab-63e8910192a6` |
| 地图与合同 | Nevaio，`nevaio-r3-v54`，`rsi-fps-5.5` |
| 本人身份 | PyZ，界面队伍1、#5；日志 `team=0`、`seat=4` |
| 比分与个人表现 | 本队 10:13；17 击杀、13 死亡、1 助攻，伤害约 1948 |
| 用途 | 赛前测试、问题发现及 V1 修改依据；平台仍将其计入累计11场 |

## 文件

- `training-633b4a9d-c271-444b-9155-14f67e96aae0.jsonl.gz`：原始本人训练日志的无损压缩文件。压缩前约 126 MiB，压缩后约 3.77 MiB；解压后的 SHA-256 已与原文件核对一致。
- `public-events.jsonl`：原始公开事件，未改写。
- `比赛结果.png`：用户提供的比赛结果截图。
- `对局分析.md`：完整逐回合分析。
- `核查数据.json`：完整性、个人表现和逐回合统计。
- `归档清单.json`：原始与压缩文件大小、SHA-256 等归档信息。

训练日志的 40,129 条决策，其原始字节数和决策区 SHA-256 与 `export_complete` 声明一致。文件整体 SHA-256 和决策区 SHA-256 是两个不同校验值，分别记录在归档清单与核查数据中。

日志中的观察、动作和结果保持原样。公开事件只辅助解释，实时策略不会读取这些历史文件。

## 读取训练日志

Python 标准库可直接逐行读取，无需解压，也无需额外依赖。在仓库根目录执行：

```python
import gzip
import json
from pathlib import Path

path = Path("比赛日志/对局01/training-633b4a9d-c271-444b-9155-14f67e96aae0.jsonl.gz")
with gzip.open(path, "rt", encoding="utf-8") as stream:
    for line in stream:
        row = json.loads(line)
        if "observation" in row:
            observation = row["observation"]
            action = row["action"]
```

若手动解压为大型 `training-*.jsonl`，根 `.gitignore` 会忽略本目录中的该原始副本；压缩归档仍可正常跟踪。

该场数据支持的首次更新见：[V1 修改说明](../../策略更新/V1-炸弹目标记忆/修改说明.md)。V1 的真实表现需另存新的对局文件夹。

分类说明及正式十场统计见：[V0联合分析](../V0联合分析/联合分析报告.md)。
