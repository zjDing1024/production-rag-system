# production-rag-system

**Day 1: evidence-first retrieval foundation.** 目前完成离线文档导入、可追溯切分、原创 BM25 关键词检索与首批评测。仓库名表示长期目标，当前版本没有生成模型、向量检索或生产部署，不是完整 RAG。

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
