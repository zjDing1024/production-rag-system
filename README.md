# production-rag-system

## 2026-11-14：独立本地生成实验，不是 RAG 集成

公开 Apache-2.0 的 Qwen3.5-0.8B Q4_0 配合官方 llama.cpp，已实际完成三条 CPU 生成请求。人工固定上下文，没有连接检索器。英文返回 `S1.`、中文答案漏引用、无依据题拒答标记多句点，按运行前要求严格 **0/3 通过**。完整保留失败，不把请求成功当回答正确。

[复现脚本、来源和原始输出](experiments/local-generation-smoke/README.md) · [实验报告](experiments/local-generation-smoke/REPORT.md)。模型/第三方二进制不入库，普通测试与 CI 不下载模型。主检索管线仍为 retrieval-only。

## 2026-11-14：冻结双语挑战揭示证据不足问题

新增24题、12英中配对的冻结挑战，区分可答、相关但证据不足、完全缺失。没有改词典或门槛。当前配置可答Hit@5=8/8、缺失题无返回8/8，但**相关不足8/8仍返回候选**。这是候选误放，不是模型错误回答；该评测未连接生成模型。小样本为作者已知语料/策略的挑战，不是独立泛化证明。a02重复证据句的事后锚点审计完整保留。

[协议、逐类结果与限制](docs/bilingual-challenge-report.md) · [原始结果](results/bilingual-challenge-v1.json) · [证据锚点审计](results/bilingual-challenge-v1-audit.json)

```bash
PYTHONPATH=src python -m rag_foundation.challenge > build/bilingual-challenge-v1.json
PYTHONPATH=src python -m rag_foundation.challenge_audit > build/bilingual-challenge-v1-audit.json
```


**Day 1: evidence-first retrieval foundation.** 目前完成离线文档导入、可追溯切分、原创 BM25 关键词检索与首批评测。仓库名表示长期目标，主检索管线没有集成生成模型、向量检索或生产部署，不是完整 RAG。

## 为什么先做检索

先把“文档从哪里来、哪一段支持结果、检索失败如何测量”做成可运行工程，再添加模型。当前以 Flask 官方文档为真实语料，服务于技术文档检索，而非无来源的聊天演示。

实现和验证由 AI 助理协助完成。工程产物可供学习、复查与扩展，不代表学习者已经独立掌握。

## 快速运行

Python 3.10+，运行与测试仅使用标准库，无模型下载、API Key、付费服务或网络请求。从仓库根目录运行：

```bash
export PYTHONPATH=src
python -m unittest discover -s tests -v
python -m rag_foundation ingest
python -m rag_foundation query 'test client live server' -k 3
python -m rag_foundation evaluate --output build/evaluation.json
```

Windows PowerShell 用 `$env:PYTHONPATH="src"` 替代 `export`。命令输出 JSON，检索结果的 `answer` 固定为 `null`，仅返回来源片段、分数和固定提交的原文行号。示例见 [`examples/query-output.json`](examples/query-output.json)。

也可安装源码包：`python -m pip install .`，然后用 `rag-foundation` 命令。数据集保留在仓库中，不随 wheel 分发；离开仓库时须传入 `--root /path/to/repo`，query 则传 `--chunks /path/to/chunks.jsonl`。构建 wheel 可能需要从标准包源安装 setuptools，检索本身不需要第三方依赖。

## 已实现架构

1. **导入**：只读取清单内的 6 个公开 RST 文件，校验 SHA-256、字节数及许可证，拒绝路径越界和越界符号链接。
2. **切分**：180 个空白分隔词、40 词重叠，共 91 块；每块保留原文字符区间、行号、源哈希、许可证和固定 URL。原始 RST 不被渲染或执行。
3. **检索**：Unicode 单词、casefold、倒排索引，独立实现 BM25，固定 k1=1.5、b=0.75，同分按稳定 chunk ID 排序。
4. **评测**：先冻结 22 个问题及原文证据，再运行检索。可答题要求命中指定文档中完整证据片段，不只是命中文档名。

```text
data/manifest.json → verified documents → source-span chunks → BM25 → cited excerpts
                                                         ↘ authored evaluation
```

## 真实语料与许可

- Pallets Flask 3.1.0：Quickstart、Config、Error Handling、Logging、Testing、Deploying。
- 固定提交：`ab8149664182b662453a563161aa89013c806dc9`。
- 6 篇、99,096 字节；这是明确的小型快照，并不声称是最新 Flask 文档或全站文档。
- 上游 BSD-3-Clause 全文和归属已保留，详见 [NOTICE](NOTICE.md) 与 [manifest](data/manifest.json)。项目原创代码使用 MIT。
- 不抓取私有文档、不执行源文档中的代码、不递归访问链接。

## 第一轮结果 · 2026-11-12

34 项单元/集成测试通过。18 个可答题包含 17 个英语题及 1 个中文跨语言压力题，另有 4 个不可答题。

| 检索指标 | 结果 | 分母 |
|---|---:|---|
| Evidence Hit@1 | 66.67% | 12 / 18 可答题 |
| Evidence Hit@3 | 88.89% | 16 / 18 可答题 |
| Evidence Hit@5 | 94.44% | 17 / 18 可答题 |
| MRR@5 | 0.7917 | 18 可答题 |
| 不可答题仍返回片段 | 75% | 3 / 4 不可答题 |

中文跨语言题未在前 5 命中证据；英文词面匹配会对不存在答案的题目返回相关词片段。**检索分数不是答案置信度，也不是拒答能力。** 没有生成步骤，因此不报告回答准确率、忠实度或幻觉率。

这是人工编写、查看语料后形成的开发集，不是独立盲测或行业 benchmark。第一次运行后未为提高数字修改问题、切分参数或 BM25 参数。逐题结果、失败案例和复现协议见 [实验报告](docs/day1-report.md) 与 [原始 JSON](results/day1-evaluation.json)。

## 工程结构

```text
src/rag_foundation/  导入、切分、BM25、评测、CLI
data/corpus/        原始许可语料
data/evaluation/    固定问题、证据和不可答说明
data/licenses/      上游许可全文
tests/              34 项机制与端到端检查
examples/           检索输出与计时脚本
results/            实际运行的评测与计时结果
docs/               设计、来源阅读与实验边界
```

## 性能与下一步

倒排索引构建线性扫描 token，单次检索访问匹配 posting 后对候选块排序。当前数据太小，不能外推规模或生产延迟；本机暖查询计量与方法见[报告](docs/day1-report.md)。

下一步：增加独立审阅的难例与同义改写，比较词法/向量/混合检索，加入段落感知切分与去重，再研究带引用的生成、证据不足时拒答、文档更新及服务边界。当前未实现 embedding、reranker、LLM、权限分区、增量索引、HTTP API 或线上部署。

## 2026-11-13：可运行本地检索服务

零模型费用、零新增依赖；此版本仍是 **retrieval-only**，不是生成式 RAG。

```bash
PYTHONPATH=src python -m rag_foundation.service --port 8000
# 另一终端：
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"query":"Flask 的测试客户端需要启动真实服务器吗？","k":5}'
PYTHONPATH=src python examples/evaluate_service.py > build/service-development.json
cmp results/service-development.json build/service-development.json
```

响应包含原始/扩展查询、显式中文词典替换、未翻译中文标志、语料词汇覆盖率、原文引用与定位；`answer=null`，`answerability=unverified`。默认启用词典及覆盖门，可用 `expand_zh=false` / `gate=false` 做消融。

已见22题开发集：原始BM25 Hit@5=17/18；词典18/18；加覆盖门18/18，4个不可答题全部无返回。**这是针对已知失败的开发修复，不是独立测试，也不是100%拒答准确率**。`What is my secret key?` 仍返回候选，说明词汇覆盖不能判断可答性。详见[服务协议与实验](docs/service-report.md)。

仅绑定127.0.0.1，单请求处理，3秒socket超时，8192字节body/1000字符query/最多10片段。标准库HTTP服务不适合生产公网部署；无认证、多租户隔离、TLS、负载/并发验证。需要这些之前不可改成公网服务。
