# AGX FPS 爆破模式策略

当前开发版本：**V2-稳定目标与分级脱困**，参赛入口为 [`agent/agent.py`](agent/agent.py)。保留V1炸弹记忆，取消未到点就定时换点，并在连续脱困失败后暂时避开失败导航连接。V2尚无真实比赛结果。

| 内容 | 位置 |
| --- | --- |
| V2修改依据、参数和验证 | [策略更新/V2-稳定目标与分级脱困](策略更新/V2-稳定目标与分级脱困/修改说明.md) |
| 原V1完整源码 | [agent-v1.py](策略更新/V2-稳定目标与分级脱困/agent-v1.py) |
| 对局12～18及评分截图 | [比赛日志索引](比赛日志/README.md)，实际使用V1，4胜3负 |
| V1七场联合分析 | [联合分析报告](比赛日志/V1联合分析/联合分析报告.md) |
| 正式原版十场 | [V0联合分析](比赛日志/V0联合分析/联合分析报告.md)，对局02～11，5胜5负 |
| 第1局 | [赛前测试](比赛日志/对局01/README.md)，不混入正式十场基线 |

## 参赛与验证

可在支持Python源码的AGX提交页使用 `agent/agent.py`。需要ZIP时运行工具包打包器；提交后还需在AGX选择新参赛版本，GitHub更新不会自动替换参赛代码。

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_fps_v2.py
python3 tools/pack.py --output submission.zip
```

策略本身只使用Python标准库和当时合法观察，不读取历史比赛日志，也不依赖本地分析环境。工具包打包器及地图标定工具需要Python 3.10+和NumPy。打包器仅收集 `agent/*.py` 及 `data/*.npz`，比赛日志、报告、旧版本源码和测试不会进入提交包。不要把V1快照放入 `agent/`。

## 日志归档

原始训练导出无损保存为 `.jsonl.gz`，逐场包含公开事件、原始评分PNG、摘要及SHA-256校验清单。归档已核对解压后原文件哈希和export_complete决策区校验。第12～18局是V2设计依据，固定观察验证不是新比赛成绩。

## 工具包地图和近似环境

`tools/read_map.py` 可查看或还原 `data/*.mapdata.npz`。地图提供候选地面、导航节点、墙体轮廓、出生点和包点等信息。`calibrate/fit.py` 可用本人训练日志标定有效观测包络；`sim/optimize.py` 演示本地近似路线搜索。示例会丢失部分楼层、跳跃及碰撞细节，本地搜索结果不代表正式环境判定，也不会自动改变当前策略。

```sh
python3 tools/read_map.py data/fps-borgo.mapdata.npz
python3 calibrate/fit.py training.jsonl --game fps --output fitted.json
python3 sim/optimize.py data/fps-borgo.mapdata.json --params fitted.json --site A
```

先用后续真实对局检验目标到达、反复停滞、交战和拆除，再决定下一次策略调整。
