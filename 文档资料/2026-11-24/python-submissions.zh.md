# 提交 Python 策略

Python 比赛：厨房、RTS、枪战、赛车和五场工程仿真只接收 Python；坦克和德州只接收 JavaScript。是否开放以比赛页面为准。

## 打包自己的文件

把自己的 `agent.py` 和辅助模块放进 `my-submission/`，然后运行：

```sh
mkdir -p output
python3 - <<'PYTHON'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
source = Path("my-submission")
assert (source / "agent.py").is_file(), "Missing agent.py"
with ZipFile("output/agent.zip", "w", ZIP_DEFLATED) as bundle:
    for file in sorted(source.rglob("*")):
        if file.is_file() and "__pycache__" not in file.parts:
            bundle.write(file, file.relative_to(source))
PYTHON
```

这条命令只打包，不验证格式或运行表现。上传时平台会检查文件类型、大小和入口；运行表现请结合本人对局的日志和回放检查。

ZIP 根目录必须有定义 `act(observation)` 的 `agent.py`；`init(context)` 可选。正式初始化固定提供 `seed`、`weights_dir`、`contract_id`、`seat`、`role` 五键。使用普通 JSON，不含 NaN 或无穷值。辅助模块随 ZIP 提交；正式席位只提供文档约定的投稿依赖。

正式提交包接受 `.py` 模块、根目录 `design.json` 与数值 `.npz` 权重；其他 JSON 文件不属于正式运行时合同。数值权重放在 `weights/*.npz`。context 的 `weights_dir` 指向提交根目录：用 `Path(context["weights_dir"]) / "weights" / "model.npz"` 定位，再以 `numpy.load(..., allow_pickle=False)` 读取。不接受对象数组、pickle 或原生库。

| 准入边界 | 上限 |
|---|---:|
| 压缩 ZIP | 64 MiB |
| 展开文件 | 128 MiB |
| ZIP 条目 | 64 |
| 单个 `.py` 文件或 `design.json` | 256 KiB |
| `.py` 文件与 `design.json` 合计 | 1 MiB |
| NPZ 文件合计 / 实际数值张量数据 | 各 64 MiB |
| 完整初始化 / 观察请求（含信封与换行） | 1 MiB |
| 完整响应（含信封与换行） | 64 KiB |

这些指标与席位内存、累计 CPU、单次动作 CPU、调用次数分别计量；后者请读各赛教程。历史 JavaScript 的源码、堆和栈限制不代表 Python 准入边界。

## 上传额度

- 每个账号在每项 Python 游戏赛每天可提交 **5 次**，北京时间每天 **08:00**（UTC 00:00）重置。校验中的提交暂占一次，通过后计入，失败后自动返还当天次数。用原幂等键重试同一次已记录的上传不额外占用次数。工程五赛的正式评测另有每日上限，上传参赛包不占这 5 次。
- 同一账号的所有 Python 比赛共用 **2 GiB** 存储额度，最多保留 **1000 条提交记录**。内容完全相同的 ZIP 只占一份存储空间。账号存储额度和记录数不会按日重置。
- 遇到 **413**，先看错误码。`python_bundle_too_large` 表示单个 ZIP 超过 **64 MiB**，需减小文件。`python_owner_quota` 表示本次上传会超过账号存储额度或记录数上限，可清理未被草稿、已发布版本或对局引用且未在校验中的旧提交。没有可清理的提交时，请联系管理员。
- 遇到 **429**，`python_daily_quota` 表示本赛当前没有可用提交次数。现有提交校验失败后可提前重试。上传页显示每日重置的本地时间，API 返回重置时间 `reset_at` 和距重置的秒数 `Retry-After`。短时间内请求过于频繁也会收到 429，按 `Retry-After` 等待即可。

## 上传、验证和参赛

打开有权访问的赛事及其 Python 编辑器。游戏赛先报名，再上传 ZIP，等待准入状态为 `passed`，随后选择已接收版本用于未来对局；已冻结的对局保留原 bundle。工程赛上传并通过准入后，再用该版本发起正式评测。本地检查和上传准入都不产出正式成绩。

API 路径均相对于 `/api/v1/python-submissions`：

|操作|路径与请求体|
|---|---|
|读取当前模板|`GET /templates/{game_id}`|
|创建本人投稿身份|`POST /agents`，`{"game_id": "<game_id>"}`|
|游戏报名|`POST /competitions/{competition_id}/registration`，`{"agent_id": "<agent_id>"}`|
|上传 ZIP|`POST /agents/{agent_id}/bundles`，二进制 `application/zip`，带 `Idempotency-Key`|
|查询准入|`GET /bundles/{submission_id}`；检查 `admission` 与 `fault_code`|
|选择游戏版本|`POST /competitions/{competition_id}/versions`，`{"submission_id": "<id>", "auto_match": true}`|
|发布工程版本|`POST /bundles/{submission_id}/publish`|
|发起工程正式评测|`POST /agents/{agent_id}/engineering/formal`，`{"version_id": "<version_id>"}`，带 `Idempotency-Key`|

上传结果不确定时，用原幂等键和完全相同的 ZIP 重试。准入为 `queued` 或 `running` 时尚未完成，应轮询到 `passed` 或 `failed`。Python 不能发送到 JavaScript 的 `source` 端点。只能使用本人获授权的身份；浏览器写操作要求 CSRF。运行时与 profile 身份来自当前模板，文档不授予隐藏赛事的访问权限。

## 策略开发

平台不提供模拟器或 SDK，仅运行正式对局或评测。请根据规则文档和自己对局的日志、回放来设计和改进策略。
