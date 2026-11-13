# 独立本地生成冒烟实验 · 2026-11-14 MYT

**已实际跑通本地 CPU 推理，但严格要求 0/3 通过。不是 RAG 集成。**

本目录不连接项目检索器或 HTTP 检索服务。三个问题使用人工固定的同一段公开
Flask 文档证据，分别观察英语回答、中文回答和证据不足时的行为。首次输出原样保留，
没有为了提高结果改提示词、问题或重跑选择答案。

## 首次真实输出

| 用例 | 原样回答 | 按运行前写好的期望判定 |
|---|---|---|
| 英语可答 | `S1.` | 失败：没有回答问题，也没有 `[S1]` 引用 |
| 中文可答 | `否。根据文档，测试客户端仅用于发起请求，不运行服务器。` | 失败：中文语义基本支持，但漏掉必需的 `[S1]` |
| 证据不足 | `INSUFFICIENT_EVIDENCE.` | 失败：拒答语义合理，但多一个句点，不符合精确标记协议 |

三个 HTTP 请求均返回 200，`finish_reason=stop`。这只证明推理请求完成，
不证明回答正确。严格 0/3 不是一般质量分数；三个作者编写的小样本没有统计代表性。
详见[报告](REPORT.md)、[固定输入](cases.json)、[结果汇总](recorded/summary.json)
和 `recorded/*-response.raw.json` 中未经改写的原始 HTTP 响应体。

## 不下载模型的验收

Python 3.10+，标准库；检查输入/原始输出哈希、格式失败和汇总一致性：

```bash
# 从仓库根目录运行
python experiments/local-generation-smoke/verify_recorded.py
PYTHONPATH=src python -m unittest discover -s tests -p test_generation_record.py -v
```

CLI 退出 0 表示**记录一致**，并显示 `strict_pass_count: 0`，不表示模型质量过关。
单元测试不下载或执行模型，现有 CI 不增加模型下载。

## 自愿复现推理

仅测试过 **Linux x86_64、Python 3.12、CPU**。下载约 586 MB，需预留约 2 GB
磁盘及至少约 2 GB 可用内存；这些是本次规模的实用余量，不是跨机器兼容性保证。
没有 API Key、收费模型接口或安装操作。下载只来自固定的公开 Hugging Face 模型
和官方 llama.cpp GitHub release；如网络或安装政策不允许，请停止，不尝试绕过。

```bash
cd experiments/local-generation-smoke
python3 prepare.py                 # 显式下载并校验 SHA-256，不执行下载的程序
python3 run_smoke.py --output runs/my-first-run
```

每次复现都先运行 `prepare.py`，因为原始 runner 只记录运行时二进制哈希，
没有自行核对预期运行时哈希。输出名称请始终放在 `runs/` 下；原始 runner
允许实验目录内其他新目录，但那些目录不会自动被 Git 忽略，完整清单含本机绝对路径，
不得不检查就发布。本目录的已发布汇总已去掉这些路径。

`prepare.py` 校验已有文件；校验失败即终止，不自动替换。模型文件、二进制、压缩包、
缓存和新运行均被 `.gitignore` 排除。模型不在 Git 仓库里。输出目录必须未存在；
后续运行选新名称以保留失败。`run_smoke.py` 与首次执行版本逐字节相同，
运行哈希保存在结果汇总。下载辅助脚本后来整理，另有轻量校验测试；
本次实际下载采用了等价的标准库下载与校验流程，不把整理后的命令冒充额外模型运行。

推理只连接绑定 `127.0.0.1` 的本地 `llama-server`，关闭 agent、Web UI、MCP proxy
和 thinking。不接入工具，不传私有资料。程序结束时关闭子进程；成功退出只表示
请求成功，不自动把模型答案判为通过。每次完整请求、原始响应和运行清单写入 `runs/`。

## 固定来源与许可

- 模型：[`ggml-org/Qwen3.5-0.8B-GGUF`](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/tree/004fd086eccea9f7cf867aa07ba328773beef81d)，
  `Q4_0`，563,036,064 bytes。它是 ggml-org 发布的量化文件，不是 Qwen 官方账号下的 GGUF。
  基础权重来自 [Qwen 固定修订](https://huggingface.co/Qwen/Qwen3.5-0.8B/tree/2fc06364715b967f1860aea9cf38778875588b17)，
  Apache-2.0，许可全文见 [licenses/Qwen-Apache-2.0.txt](licenses/Qwen-Apache-2.0.txt)。
- 运行时：官方 [`ggml-org/llama.cpp b12359`](https://github.com/ggml-org/llama.cpp/releases/tag/b12359)，
  固定 commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`，Ubuntu x64 CPU 包；
  MIT，见 [licenses/llama.cpp-MIT.txt](licenses/llama.cpp-MIT.txt)。不在这里分发第三方程序或代码。
- 证据：Flask 3.1.0 固定[文档](https://github.com/pallets/flask/blob/ab8149664182b662453a563161aa89013c806dc9/docs/testing.rst)，
  BSD-3-Clause，见仓库 [NOTICE](../../NOTICE.md) 与[全文许可](../../data/licenses/Flask-BSD-3-Clause.txt)。
- 本目录脚本为原创 AI 辅助实现，使用仓库 MIT 许可。全部固定 URL、字节数和
  SHA-256 在 [sources.json](sources.json)。只做文本推理，没有下载或测试视觉组件。

下一步应先设计可靠的结构化输出/引用校验和失败处理，再单独研究与检索器的连接。
本实验没有完成端到端 RAG、证据充分性判定、一般双语评测、生产部署或安全评测。
