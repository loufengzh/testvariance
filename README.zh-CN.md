# testvariance

**按相同条件比较 CI 测试结果，让证据可以核查。**

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

这是一个离线 Python 库和命令行工具，读取规范 JSONL 测试历史，按测试、代码版本和环境分别汇总，报告混合结果、恢复成功的运行及已观测到的重试耗时。运行时仅依赖 Python 3.10+ 标准库。

## 用途与边界

先失败后成功并不能单独证明测试不稳定：代码或环境可能已经变化。testvariance 不会混合不同版本或环境的数据，也不会执行重试、连接 CI、诊断根因或自动隔离测试。[pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) 用于执行 pytest 重试；[test-summary/action](https://github.com/test-summary/action) 用于展示 GitHub Actions 报告。本项目专注于离线历史证据和缺失耗时的明确记录，是独立实现。

## 安装与示例

目前不假设已发布到包索引。请在仓库目录执行：

```sh
python -m pip install .
testvariance analyze examples/outcomes.jsonl --format text
testvariance analyze examples/outcomes.jsonl --format json
cat examples/outcomes.jsonl | testvariance analyze - --fail-on-mixed
```

示例含 7 条观测、4 个可比组、1 个混合结果组。最后一个命令会有意返回退出码 1。混合组失败频率为 1/3，含 1 次恢复运行、2.5 秒已观测重试耗时，以及 1 条缺失耗时的重试。另一个代码版本的失败单独计算。无需安装即可在 POSIX shell 使用 `PYTHONPATH=src python -m testvariance analyze examples/outcomes.jsonl`。

## 输入约定

每个非空行是一个 UTF-8 JSON 对象：

```json
{"test_id":"suite/test","revision":"a1b2c3","environment":"linux-py312","run_id":"build-101","attempt":1,"outcome":"fail","duration_seconds":12.5}
```

- 必需字段：`test_id`、`revision`、`environment`、`run_id`、`attempt`、`outcome`。
- 四个标识符必须是非空白字符串，每个最多 4096 字符；不做大小写转换、去空格或规范化。建议使用完整提交标识，并将平台、依赖和配置等可比性维度纳入环境标识。
- `attempt` 是正整数，不能是布尔值；表示此测试、版本、环境和运行中的原始尝试序号，而非文件行号。
- `outcome` 只能为 `pass`、`fail`、`error`、`skip`。
- 可选 `duration_seconds` 是有限非负数或 `null`。省略或 null 表示未知；0 是已知的零。
- 未知字段、重复 JSON 字段、非法 UTF-8、NaN/Infinity 和重复观测键均拒绝。键为 `(test_id, revision, environment, run_id, attempt)`；完全相同的重复行也无效。
- 总量上限 32 MiB；每个物理行（含换行符）上限 64 KiB；最多 100000 条观测。空白行也计入字节限制；空输入有效；不接受 UTF-8 BOM。汇总耗时也必须有限。

当前不支持 JUnit/XML 导入。请在上游转换为此格式，并保留准确的元数据；不要从文件名猜测版本或环境。

## 报告语义

所有平台（包括 Windows）的命令行报告、诊断和帮助/版本消息均使用 LF 换行。默认输出 JSON，`schema_version` 为 1。组按三个标识符排序，运行按 `run_id` 排序，尝试仅在各自运行内按序号排序。输入行顺序不重要，运行 ID 不被解释为时间顺序。

- `counts` 是各结果的观测条数；`executed_attempts` 不含 skip。
- `failure_frequency = (fail + error) / (pass + fail + error)`，是按尝试加权的观测频率，不是构建失败概率。全部跳过时为 null。
- `failure_frequency_wilson_95` 是名义 95% Wilson 区间，无执行观测时为 null。重试常有相关性、选择偏差和依赖关系，因此真实覆盖率可能不是 95%；它不是不稳定性置信度或保证。
- `mixed_outcomes` 表示同一个可比组至少包含一次 pass 和一次 fail/error，可以来自不同运行。这是变化证据，不是非确定性或根因的证明。
- `recovered_runs` 要求某次运行最后一个已观测尝试为 pass，且之前有 fail/error。pass→fail 或 fail→pass→skip 不算。最后指已提供的最大序号，并不表示 CI 已结束。
- `observed_retry_seconds` 只累加序号大于 1 的已提供尝试的已知耗时（包括记录了耗时的 skip）。`retry_missing_duration_count` 统计这些重试中耗时未知的条数。
- 每次运行的 `missing_attempt_count` 统计从 1 到最大序号之间未提供的尝试。缺失尝试不估算成本。耗时总和不是墙钟延迟，也不是费用。
- `observed_duration_seconds` 和 `missing_duration_count` 针对全部已提供尝试。存在未知耗时的时候，总和为零并不能证明成本为零。

报告包含原始标识符，请按其保密要求处理。工具无网络访问，不收集 stdout、错误消息、堆栈或环境变量；文本输出转义控制字符，校验错误不回显原始内容。但报告不会自动匿名化。

## 退出码和库接口

0 表示有效报告；只有指定 `--fail-on-mixed` 且存在混合组时才返回 1，仍输出完整报告。2 表示非法输入、用法或 I/O 错误；非法输入不会输出部分报告。是否启用此门禁取决于工作流，不应将其当作自动不稳定测试判定。

```python
from testvariance import analyze, load_jsonl
with open("examples/outcomes.jsonl", "rb") as source:
    report = analyze(load_jsonl(source))
print(report["mixed_group_count"])
```

`Observation` 在构造时校验，`analyze` 也拒绝重复键。`InputError` 继承 `ValueError`。数据在上述限制内保存在内存中，不写文件或修改原始观测。

## 开发与计划

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

测试仅需 Python；构建需要已有 setuptools 和 wheel。CI 覆盖 Linux Python 3.10–3.13、Windows Python 3.12 和安装后 CLI。另见 [贡献指南](CONTRIBUTING.md)、[安全说明](SECURITY.md)、[格式说明](docs/FORMAT.md)。计划包括有界 JUnit/Jest 转换器、明确冲突策略的历史合并和透明成本排序；0.1.0 尚未实现这些功能，也不包含历史存储、自动隔离或根因诊断。MIT 许可。
