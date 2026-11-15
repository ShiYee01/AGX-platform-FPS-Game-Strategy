# AGX FPS local optimisation kit / 本地优化工具包

## 本仓库的比赛归档与当前版本

- 当前开发策略：**V1-炸弹目标记忆**，入口 `agent/agent.py`；用户计划下一轮提交AGX参赛。
- [比赛日志索引](比赛日志/README.md)：对局01为11月14日赛前测试，对局02～11为正式十场V0基线。
- [正式十场联合分析](比赛日志/V0联合分析/联合分析报告.md)：原版重复问题、评分口径和V1实验建议。
- [策略更新记录](策略更新/README.md)：版本依据、修改说明与验证情况。

以上11场实际参赛代码均为V0；现有V1尚无真实比赛结果。下方保留原工具包说明。


FPS 策略在 PPT 示例基础上修了寻路和脱困；与网站和编辑器模板使用相同文件。赛车策略保留 PPT 原版。
The FPS policy fixes pathfinding and recovery on top of the PPT example and uses the same files as the website and editor.

这是地图、最小策略和自建近似环境的示例。模型结果与正式对局有偏差。所有动力学/判定参数都要用本人的日志标定。
These are map parts, a minimal policy and examples for YOUR approximate environment. Model results differ from matches. Fit all dynamics/adjudication parameters using your own logs.

1. 下载 `agx-fps-kit.zip`，解压到新目录并进入该目录。Install Python 3.10+ and unzip into a new folder, then enter it.
2. 创建 Python 环境并安装 NumPy / create an environment and install NumPy:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install numpy
```

可选：`python tools/read_map.py data/fps-borgo.mapdata.npz` 查看字段，`--output restored.json` 还原完整 JSON。Optional: inspect all fields or restore JSON using the reader.

3. 在 AGX 的本人已结束对局页下载本人席位的 `training.jsonl`，放到此目录；不把日志、账号信息或下载凭据装进提交 ZIP。In your completed match, download YOUR seat's training data to this directory. Keep logs and credentials out of the submission.
4. 标定 / calibrate:

```sh
python calibrate/fit.py training.jsonl --game fps --output fitted.json
```

输出是有效观测包络，不是确定的物理规律。按地图与移动方式分别采样；留出后续对局验证。空值表示缺对应动作/运动样本，需补采样或填入自己估计的正数。手动在 `fitted.json` 的 `parameters` 里补入 `reaction_seconds`（反应时间，秒 / reaction time in seconds），并记录你的依据。FPS 的反应时间和赛车的安全边距不由这个简单拟合器识别。
Fits are effective observed envelopes, not identified physics. Separate maps and movement modes and keep held-out matches. Null means missing samples: collect suitable actions or add your own positive estimate. Add `reaction_seconds`（反应时间，秒 / reaction time in seconds） to `parameters` in `fitted.json`, documenting your choice. This fitter does not identify reaction time or safety margins.

5. 运行本地近似环境 / run your local approximation:

```sh
python sim/optimize.py data/fps-borgo.mapdata.json --params fitted.json --site A
```

FPS：搜索双方路线/站位，可改成简化自博弈。赛车：搜索行车线/速度表，输出近似时间和能耗。优化完把选中的行为写回 `agent/agent.py`；赛车可将 `profile.npz` 放到 `data/`，从 `weights/profile.npz` 加载速度表。`sim/` 输出不会自动改变策略或平台分数。
FPS searches both sides' routes/positions and can be extended for simplified self-play. Racing searches lines/speeds and estimates time/energy. Transfer chosen behaviour into `agent/agent.py`; racing can copy `profile.npz` to `data/` and load the table from `weights/profile.npz`. Simulator output does not automatically modify the policy or a match score.

6. 打包最小策略和所有地图 / pack the agent and maps:

```sh
python tools/pack.py --output submission.zip
```

`tools/pack.py` 只收集 `agent/*.py`、根设计书 `agent/design.json` 和 `data/*.npz`；写入 ZIP 根目录 `agent.py`、赛车 `design.json`、`weights/*.mapdata.npz`。不会放入 JSON 地图、日志、文档、环境代码或目录条目。ZIP ≤64 MiB、≤64 条目，每份源文件 ≤256 KiB、源文件合计 ≤1 MiB、NPZ 和展开张量各合计 ≤64 MiB。打包器检查常用约束，最终仍以平台准入为准。
The packer collects only `agent/*.py`, `agent/design.json` and `data/*.npz`. It writes root `agent.py`, racing `design.json`, and `weights/*.mapdata.npz`, with no explicit directories. ZIP ≤64 MiB/64 entries; each source ≤256 KiB, combined source ≤1 MiB; NPZ and tensor bytes each ≤64 MiB. It checks common limits; platform admission remains authoritative.

7. 在对应比赛的 Agent 提交页上传 `submission.zip`、发布版本并更新报名版本。看后续本人对局日志，重新标定/优化。
Upload `submission.zip` on the contest Agent submission page, publish the version and update the enrolled version. Repeat calibration using your later match logs.

`init(context)` 从 `context['weights_dir']` 给出的提交根目录定位 `weights/`，用 `np.load(..., allow_pickle=False)`；`act(observation)` 使用已加载数据。所附策略保持上述母版；地图加载与优化结果由学生自行接入。不要在策略里导入 `sim` 或 `calibrate`。
`init(context)` locates `weights/` under the submitted root given by `context['weights_dir']` and uses `allow_pickle=False`; `act(observation)` uses the loaded data. The supplied policy preserves the template above; connect map loading and optimisation results yourself. Do not import `sim` or `calibrate` from the submitted policy.

## 地图数据能做什么：FPS

用 `walkable_surface_candidates.cells` 的 XY 可走候选网格做 A*：先把出生点和 A/B 包点投到最近候选格，再找四邻接最短路。`sim/optimize.py` 演示双边出生点到包点的路线搜索。格子坐标需乘 `cell_size_m`、加 `origin_xy` 和半格偏移；同一 XY 可能有多层高度，空格表示未知。示例压成 2D，会丢掉楼层、梯子和跳跃信息，不能据此断言真实对局不可达。

`wall_cover_contours` 是墙体和掩体多边形，可用线段与多边形相交测试估算视线：在哪能看到包点、在哪有遮挡。高度区间可以帮助你扩展到分层模型；示例 2D 判定忽略了高度。`landmarks`、`passages` 和出生点可用于分工、通道选择、回防与设伏。不要把视觉标签当作精确可行走的路点。

这些零件能拼成自己的简化 2D 对抗环境：双方沿网格移动，用轮廓近似遮挡，搜索站位和路线，或轮流选最佳回应做简化自博弈。示例使用一个小型 minimax 站位目标，结果不是正式胜率。移动速度、反应时间及你添加的射击/判定参数都需要用自己的 `training.jsonl` 标定；不要把示例策略的数值当成环境规则。校准后可批量搜索，再将优化结果写回 `agent.py`，打包提交。

NPZ 与 JSON 一一对应；NPZ 额外提供 `floor_cells`、`floor_origin_xy`、`floor_cell_size_m`、`bombsite_centers` 和 `spawn_attack/defend` 数值数组。完整文字/结构编码在 `structure_utf8` 的 UTF-8 字节中；整数、浮点、布尔值分别位于 `i/f/b` 池。全部能用 `np.load(path, allow_pickle=False)` 读取。可在自己的策略的 `init(context)` 中从 `Path(context['weights_dir'])/'weights'` 加载地图，在 `act(observation)` 根据当前观察调用 A*；附带母版使用观察给出的导航图。

这是近似环境，会与真实对局有偏差。用本人日志检查路线、分层、移动和视线假设，在本地优化完成后提交；平台比赛结果才是实际表现。

## What map data can do: FPS

Run A* on the XY candidate grid in `walkable_surface_candidates.cells`: snap a spawn and an A/B site to their nearest candidate cells and search four-neighbour routes. `sim/optimize.py` searches both sides' routes to a site. Convert cell indices using `cell_size_m`, `origin_xy` and a half-cell offset. Several heights can share an XY cell; missing cells are unknown. The example collapses floors to 2D and omits ladders and jumps, so a failed search does not prove the real site is unreachable.

Intersect sight segments with `wall_cover_contours` polygons to estimate where a site is visible or covered. Height ranges can support your own layered model; the 2D example ignores height. Use `landmarks`, `passages` and spawn pads to plan roles, lanes, rotations and ambushes. Visual labels are not precise navigation waypoints.

Combine these parts into your own simplified local 2D adversarial environment: move on the grid, approximate occlusion with contours, and search positions/routes or alternate best responses for simplified self-play. The example uses a small minimax positioning objective; it does not estimate a platform win rate. Fit movement speed, reaction time and any added shooting/adjudication parameters using YOUR `training.jsonl`. Example policy numbers are student heuristic guesses, not environmental rules. Search many local candidates, then transfer the selected behaviour to `agent.py` and submit.

NPZ represents the same complete JSON, plus convenient numeric arrays: `floor_cells`, `floor_origin_xy`, `floor_cell_size_m`, `bombsite_centers`, `spawn_attack/defend`. Complete names and structure are UTF-8 bytes in `structure_utf8`, with integer/float/bool pools `i/f/b`. Load every array with `np.load(path, allow_pickle=False)`. Your adapted policy can load `Path(context['weights_dir'])/'weights'` in `init(context)` and call A* from `act(observation)`; the supplied canonical policy uses the public navigation graph in the observation.

Your approximate environment will differ from real matches. Check route, floor, movement and visibility assumptions against your own logs, optimise locally, then submit. Match results measure actual performance.

