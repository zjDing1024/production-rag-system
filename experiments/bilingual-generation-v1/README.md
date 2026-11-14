# 12 题英中生成实验 · 2026-11-15 MYT

**已实际运行首次检索→本地生成链路，但结果不可靠。JSON 合法、引用 ID 存在，不等于答案有依据。**

6 个新英中配对，共 12 题：可答、相关但证据不足、主题缺失各 4 题。
用例、期望事实与固定上下文在首个模型请求前提交冻结。作者知道语料和既有失败，
因此这是新编开发挑战，不是独立盲测。昨天的三条 0/3 诊断没有混入本轮。

## 结果概览

| 本轮策略 | 模型输出合同有效 | 可答题事实正确且有支持 | 8 个负例的合法模型拒答 | 检索门直接拒绝 |
|---|---:|---:|---:|---:|
| 固定上下文、文本 baseline | 10/12 | 1/4 | 8/8 | 0 |
| 固定上下文、JSON schema 策略 | 11/12 | 4/4 | 0/8 | 0 |
| 真实检索→JSON adapter | 5/8 次模型调用 | 1/4 | 0/4 个进入模型的负例 | 4/8 负例 |

第一行唯一语义正确的可答输出仍写成 `S1:`，不符合要求的 `[S1]` 引用。
schema 策略在负例上生成 7 个无依据答案，另一个输出 `abstain=true` 却携带
`answer="None"` 和引用。它们的 JSON 字段类型均合法，但拒答合同或语义不成立。

真实链路返回的 5 个合同有效答案中，只有 1 个正确且有支持；2 个答错属性，
2 个无依据声称上限为 1。另有 3 个输出被 adapter 拦下，包括编造巨大上限后截断。
4 个主题缺失题在检索门退出，**未调用模型，不是模型拒答成功**。

提示词的输出说明和 `response_format` 同时改变，不能把差异单独归因于 grammar。
完整[报告](REPORT.md)、[逐题人工复核](manual-review.json)、[机器可复算汇总](summary.json)、
[全部原始记录](recorded/)均保留失败。

## 不下载模型的复核

从仓库根目录运行，Python 3.10+，仅标准库：

```bash
python experiments/bilingual-generation-v1/audit_record.py
PYTHONPATH=src python -m unittest discover -s tests -p test_bilingual_generation_record.py -v
```

退出 0 仅表示记录/格式核验一致，不代表模型通过。语义判断来自明确记录的人工审阅，
不是字符串匹配冒充的自动忠实度评判。通常测试和 CI 不启动或下载模型。

## 可选完整复现

Linux x86_64、Python 3.12，约 586 MB 公开下载；建议预留约 4 GB 可用 RAM、
2 GB 磁盘。固定模型/运行时沿用[公开来源与许可](../local-generation-smoke/sources.json)：
Qwen3.5-0.8B Q4_0（Apache-2.0），官方 llama.cpp b12359（MIT）。没有收费 API。

```bash
# 从合并了 generation.py 的仓库根目录运行
python3 experiments/local-generation-smoke/prepare.py
python3 experiments/bilingual-generation-v1/run_experiment.py \
  --output build/bilingual-generation-v1-my-run
```

脚本校验模型/二进制哈希，在同一环境内启动 loopback 服务器，依次完成 24 次固定上下文
请求及 12 次 pipeline 调用，最后关闭子进程。默认从本仓库 `src` 导入适配器，
不依赖作者目录。`--mode fixed` 或 `--mode pipeline` 可分别复现两部分。
新输出目录必须不存在，不覆盖失败记录，不自动重试或修正模型回答。

本次准备阶段发现不同命令的回环网络相互隔离。独立启动的首次监听进程没有收到
模型请求，随后被正常停止；正式 runner 将服务和请求置于同一子进程环境，没有
绕过网络或安装限制。`build/` 中的日志可能有机器路径，不应直接提交。

## 材料与边界

- [cases.json](cases.json) 与 [lock](cases.lock.json)：冻结问题、来源行号、期望及提示词。
- [run_experiment.py](run_experiment.py)：实际执行版本，哈希写入 manifest。
- `recorded/`：24 个完整请求、24 个未经改写的原始响应体、12 个 pipeline 返回及运行 manifest。
- [recorded-files.sha256.json](recorded-files.sha256.json)：原始记录逐文件哈希。
- [audit_record.py](audit_record.py)：离线完整性/字面合同核验；不会运行模型。

所有供给文档来自仓库中固定的 Flask 3.1.0 快照，BSD-3-Clause，
参见 [NOTICE](../../NOTICE.md) 与[完整许可](../../data/licenses/Flask-BSD-3-Clause.txt)。
公开文档自带的演示密钥只是文档示例，不是用户凭据。没有私有文档、模型权重、
第三方运行时包/源码或机器日志入库。

这是免费本地端到端原型和失败分析，不是生产 RAG、通用双语质量或低幻觉率证明。
AI 辅助工程验证也不代表学习者已经独立掌握这些机制。
