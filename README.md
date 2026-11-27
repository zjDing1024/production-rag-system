# production-rag-system

离线可追溯检索 + 可选本地生成原型。它不是生产级或可靠知识问答系统。

## 先选你要审核的路径

### 1. 离线检索：不下载模型

Python 3.10+，仅标准库；从仓库根目录运行：

```bash
PYTHONPATH=src python -m rag_foundation ingest
PYTHONPATH=src python -m rag_foundation query 'test client live server' -k 3
```

这里返回来源片段，`answer=null`，**没有生成回答**。

### 2. 审核已记录实验：不运行模型

```bash
python experiments/version-binding-v1/replay.py --check
python experiments/version-binding-v1/audit_live.py --check
```

该命令复核冻结输入、原始记录和计数，不重新生成、不自动判定语义真值。
[最新版本交叉与生成记录](experiments/version-binding-v1/README.md)。
[上一轮真实生成报告](experiments/source-transfer-v1/REPORT.md) ·
[分层计数与逐题结果](experiments/source-transfer-v1/summary.json) ·
[原始模型记录](experiments/source-transfer-v1/recorded/)。
上一轮[索引冲突机制实验](experiments/indexed-scope-v1/README.md)仅使用spy，保持原记录，不与本轮模型结果混算。
旧的[typed scope实测与语义注释](experiments/typed-scope-v1/README.md)保留。
旧的[同题证据替换实验](experiments/matched-evidence-v1/README.md)、[编号选择实验](experiments/numbered-spans-v1/README.md)、
[证据门实验](experiments/evidence-sufficiency-v1/README.md)与
[生成实验审计](experiments/bilingual-generation-v1/README.md)保留为回归记录。

### 3. 可选真实 CPU 模型：显式下载与运行

Linux x86_64、Python 3.12，公开下载约586 MB，临时RAM建议至少5 GB。无收费API。
模型/运行时固定校验并仅下载到 `/tmp`，runner自动启动和停止本地服务：

```bash
python3 experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python3 experiments/source-transfer-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/my-source-transfer-run
```

[环境、固定许可/来源、实验边界](experiments/source-transfer-v1/README.md)。
每次使用新的输出目录。通常测试和CI仅检索/审计，不下载或执行模型。

## 2026-11-28：CPython 文档证据的范围、单位与精确链接

新增可选来源渲染入口。保留已有上游锚点，将本地分块坐标单列；从排名结果到模型引用用同一来源定位，不改历史入口和冻结记录。

```bash
python -B experiments/cpython-timeout-provenance-v1/audit.py --case py311-connection-shutdown
python -B experiments/cpython-timeout-provenance-v1/audit.py --case py311-connection-shutdown-removed
python -B experiments/cpython-timeout-provenance-v1/live.py --check
```

五案离线验证：三个有证据的计划匹配整数、秒单位与精确来源，两案在排序前停止。可选 CPU 路径实际调用三次，引用和数字都匹配，但三次均未输出要求的秒单位，冻结完整判据 **0/3**。没有把裸数字或确定性停止当成完整回答。
[完整对照、源码许可及原始记录](experiments/cpython-timeout-provenance-v1/README.md)。

## 2026-11-27：实际 CPU 生成的同题证据对照

先用只读入口复现：相同的 PostgreSQL 17.0 问题，有正确证据时返回整数 0 毫秒并引用固定源码位置；只有邻近设置时，排序前返回 `no_matching_scope`。

```bash
python -B experiments/postgres-agent-transfer-v1/replay.py --case pg17-transaction
python -B experiments/postgres-agent-transfer-v1/replay.py --case pg17-neighbors-only
python -B experiments/postgres-agent-transfer-v1/compare_live.py --check
```

另用同一批五案实跑 7 次免费本地 CPU 生成：未过滤组 3/3 不足证据仍进入无支持的回答分支；范围组 3/3 在排序前停止，未调用模型。两个可答案在两组都引用了正确来源，人工复核陈述值正确；因输出为完整句，冻结的裸值格式判据两组均为 0/2，不改判据。不把模型拒答、确定性停止和引用支持混为一谈。
[命令、结果与原始记录](experiments/postgres-agent-transfer-v1/README.md)。

## 2026-11-26：PostgreSQL 同值引用迁移对照

用 PostgreSQL 16.0／17.0 文档新增五案离线验证：两条正确定位并引用整数 0 毫秒，三条仅有近邻或例外说明的请求均在范围预检停止。
无范围过滤的独立诊断中，三条停止案均能命中词法候选，因此不能把命中误当证据。无数据库或模型调用，原入口不变。
[复现、冻结判据与证据](experiments/postgres-agent-transfer-v1/README.md)。

## 2026-11-25：有预算的只读文档问答 Agent

新增可选离线入口：从已审核请求绑定范围，用真实 BM25 找证据，只返回有引用的已审阅值，或给出明确停止原因。
十条实际命令验收：三条带引用回答、七条确定性停止；最多两次检索尝试，模型调用为零。
不执行外部工具、不推断自由文本范围、不修改原检索与生成默认行为。
[运行命令、来源和原始追踪](experiments/read-only-agent-v1/README.md)。

## 2026-11-24：SQLite 同值不等于同证据

用一条 SQLite 问题做四组离线对照。两个错配的候选值都是 3，但分别引用了错对象和错字段。
真实 BM25 都命中并打包了相应片段；可信夹具绑定保留正确项，在排序前拦下两个错配。
缺字段仍由原管线返回无匹配范围。没有模型调用或默认路径改动。
[实验说明、运行时来源和复现](experiments/sqlite-attribution-v1/README.md)。

## 2026-11-22：范围匹配不代表问题版本与范围一致

新增可选的字面版本一致性检查，不改旧入口或默认行为。用同一份 Express 目录交叉两条问题与
两个版本范围：旧路径四条匹配请求均保留支持证据，四条错配请求却都打包了错误版本；
新入口保留全部匹配请求，在单次查询执行前拦下四条错配。英中只是相关变体。
其中英语四对实跑 6 次本地 CPU 生成：两条匹配请求两臂皆正确，旧路径两条错配都给出格式合法
但版本错误且无所需证据的回答，新入口两条均不调用模型。版本匹配后仍运行原目录检查；附加未登记的无关记录，仍可阻止原本可答的请求。
[复现、结果和适用边界](experiments/version-binding-v1/README.md)。

## 2026-11-21：在 CPython / Express 新来源上跑真实生成

22行英中开发试验、两个来源族、三个设置事实族与五个release-specific目标，先冻结来源、
逐题判据和实际BM25覆盖，再完成32次免费本地CPU生成。正确且有引用支持的可答结果为
**9/10→10/10**；唯一修复来自scope在top-1前取回被explicit示例挤掉的默认值片段，非推理能力提升。

未过滤的12个不足条件全部进入无支持的answer分支，其中9个明确错误事实、3个歧义`None`；
过滤后12次确定性`no_matching_scope`不运行，**不是模型拒答**。`False`、`0`、参数不存在、
显式设置与默认值严格区分。无传输/格式错误，旧默认与历史记录不变。
这是已知来源的人工开发试验，不是独立盲测或生产可靠性证明。
[复现与来源](experiments/source-transfer-v1/README.md) · [完整分层报告](experiments/source-transfer-v1/REPORT.md)。

## 2026-11-20：接入真实 BM25，检索不到的冲突也必须先查

新增默认关闭的索引自有 scope / reviewed单值目录管线。先完整检查同scope记录的
冲突、未知和审查数量上限，再用原BM25全索引分数筛选eligible候选、取top-k、打包。
因此不能靠增加k解决的“零词面重叠冲突”也不会被漏检。历史源码、默认流程和结果保持不变。

22个构造控制包含英中数值/路径冲突与同值、ID/顺序重排、错版本、显式null、缺元数据、
缺review、scan cap、packing cap、无匹配和top-1筛除反例。使用真实BM25与完整新管线，
生成端仅用明确标注的spy及本地HTTP合同fixture，**不是模型正确率实验**。
首轮英文“零重叠”标签因共享is失败，原记录保留；另冻结两条修正输入验证，未修改旧输出。

这依赖可信的一chunk一scope及人工结构化单值声明。原文hash/quote只能绑定字节，不能
证明手工值的语义或真实性，也不是权限控制。完整目录以外的冲突仍不在保证范围。
[接口/离线CLI](docs/indexed-scope-pipeline.md) · [复现](experiments/indexed-scope-v1/README.md) ·
[判据与实测](experiments/indexed-scope-v1/REPORT.md)。

## 2026-11-19：显式版本 / 对象 / 时间过滤，不冒充语义理解

新增默认关闭的 typed scope 过滤器，调用方明确提供版本或对象与时间；不从问题推断，
不读答案值，不验证元数据真假，也不是权限控制。无匹配时 `not_run`，不调用模型。

64 行新开发条件、32 个同题证据配对，跨英中、同类双记录、独立 ID / 顺序重排。
相同分支生成器实测：未过滤的可答题 **23/32** 给出正确值且全部引用在所问范围内，
32 个无所问证据条件全部错误放行；过滤后为 **32/32 正确答案 + 32 次确定性不运行**。
这不是 64 个模型正确答案，也不是模型学会拒答。若整个答案必须仅等于字面量，未过滤为21/32。

过滤同时改变上下文长度和可选引用集；小型已知事实与重复布局不证明泛化能力。
`None` 是 Flask 新版本的有效配置值，和“无匹配记录”分开。旧默认生成/检索流程不变。
[接口和信任边界](docs/typed-scope-gate.md) · [复现](experiments/typed-scope-v1/README.md) ·
[分层结果](experiments/typed-scope-v1/REPORT.md)。

无需模型即可看筛选结果：

```bash
PYTHONPATH=src python -m rag_foundation.scope_gate \
  experiments/typed-scope-v1/example-input.json --gate
```

## 2026-11-18：同题替换证据，格式通过仍可能引用错误对象

8 个英中同题配对、16 行证据条件，文档默认值和明确虚构的运行快照都同时包含可答/不足条件。
每对保持问题、片段数量/顺序/形状与字符长度，只换相关文档字段或虚构对象名。不是实际用户遥测。

编号选择器命中全部 8 个可答证据，但误放 6 个不足条件，仅 **2/8 整对判断正确**。
相同选中证据上，新的 answer/refusal 分支 schema 让 14/14 下游输出满足最终合同，
交付正确有支持答案由旧 schema 的 1/8 增至 7/8；同时也放行了 **6 个无支持答案和 1 个错误路径值**。
两臂原始答案字符串完全相同，不能把结构改善说成语义能力提升。虚构运行条件仍 0/4 整对正确。

无默认行为更改，不自动补引用。新增模型外审计支持 `--check`，避免依赖 shell 编码和 `cmp`。
[复现与边界](experiments/matched-evidence-v1/README.md) · [逐层结果](experiments/matched-evidence-v1/REPORT.md)。

## 2026-11-17：编号避免复制错误，不等于证据判断可靠

16 个新开发问题、4 个事实族，英中和数值/非数值均衡；两臂得到完全相同的固定短 span 池。
完整逐字复制臂 16/16 输出不合合同；编号臂有 11 个合法选择，其中仅 6 个支持所问问题，
另有 3 个正确拒绝、2 个错误拒绝。编号由 schema 限定，程序回填原文，不能把 ID 合法率称为回答准确率。

下游 11 次生成只有 1 个合法答案，却把默认 cookie 寿命当作真实剩余时间，无依据。
**两臂已接受、有支持的正确答案均为 0/8 可答题**。这是受控接口策略对照，不是检索排名或
独立 held-out 评测，也不代表语义能力提升。无生产默认行为变更。
[复现与分层指标](experiments/numbered-spans-v1/README.md) · [失败详情](experiments/numbered-spans-v1/REPORT.md)。

## 2026-11-16：证据门运行成功，但能力验证失败

12个新英中问题、实际 context 由 AI 助理预先逐题标注；同一生成器比较gate off/on，另做同题删值诊断。
10个非空context的门输出全部逐字引用校验失败，**不能计作正确拒答**。
已接受且有支持的正确答案从off的3/4降到on的0/4；原有2个无候选退出不计新门增益。
4个删值诊断也未产生合法判定。该模型门保持默认关闭，不建议启用。

精确引用只能检查出处，不能证明所问论断得到支持。门的协议失败、合法不足判断、
传输故障和下游错误分别记录。新增门多一次模型计算，不是等算力比较。
[接口与限制](docs/local-generation-contract.md) · [失败分析](experiments/evidence-sufficiency-v1/REPORT.md)。

## 历史实验与实现记录

以下日期段落保留当时状态，不表示当前完整能力。当前入口以上面的三条路径为准。

## 2026-11-15：可选本地引用回答

新增检索→本地 llama.cpp→结构化回答/引用校验的完整入口，默认检索服务仍不调用模型。生成结果区分有效结构回答、证据拒答、传输错误与无效输出；合法引用不等于语义正确。模型独立启动，CI不下载模型。

```bash
mkdir -p build
PYTHONPATH=src python -m rag_foundation.generation 'What is MAX_CONTENT_LENGTH?' \
  --endpoint http://127.0.0.1:8080 > build/generated-answer.json
```

[引用合同与状态定义](docs/local-generation-contract.md) · [12 题实测与复现命令](experiments/bilingual-generation-v1/README.md) · [逐题结果](experiments/bilingual-generation-v1/summary.json)。真实端到端的 5 个合同有效答案中仅 1 个正确且受支持，不能作为可靠知识问答使用。以下日期段落保留当时状态。


## 2026-11-14：独立本地生成实验，不是 RAG 集成

公开 Apache-2.0 的 Qwen3.5-0.8B Q4_0 配合官方 llama.cpp，已实际完成三条 CPU 生成请求。人工固定上下文，没有连接检索器。英文返回 `S1.`、中文答案漏引用、无依据题拒答标记多句点，按运行前要求严格 **0/3 通过**。完整保留失败，不把请求成功当回答正确。

[复现脚本、来源和原始输出](experiments/local-generation-smoke/README.md) · [实验报告](experiments/local-generation-smoke/REPORT.md)。模型/第三方二进制不入库，普通测试与 CI 不下载模型。主检索管线仍为 retrieval-only。

## 2026-11-14：冻结双语挑战揭示证据不足问题

新增24题、12英中配对的冻结挑战，区分可答、相关但证据不足、完全缺失。没有改词典或门槛。当前配置可答Hit@5=8/8、缺失题无返回8/8，但**相关不足8/8仍返回候选**。这是候选误放，不是模型错误回答；该评测未连接生成模型。小样本为作者已知语料/策略的挑战，不是独立泛化证明。a02重复证据句的事后锚点审计完整保留。

[协议、逐类结果与限制](docs/bilingual-challenge-report.md) · [原始结果](results/bilingual-challenge-v1.json) · [证据锚点审计](results/bilingual-challenge-v1-audit.json)

```bash
mkdir -p build
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
mkdir -p build
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

下一步：优先把具体论断的证据充分性作为独立关卡，在新题上验证误答与误拒。向量检索、reranker、权限分区、增量索引及线上部署尚未完成。

## 2026-11-13：可运行本地检索服务

零模型费用、零新增依赖；此版本仍是 **retrieval-only**，不是生成式 RAG。

```bash
mkdir -p build
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


## 2026-11-23：Cargo resolver 的根范围与证据边界

新增 Cargo 0.86.0 的离线来源实验，区分根包 edition、虚拟工作区根和显式 resolver。
4 条根/虚拟范围证据可支持预期值，成员级或仅说明“需显式设置”的材料不支持数字默认值。
这是来源范围与证据支持审计，不运行 Cargo，不修改默认检索。
[实验说明](experiments/cargo-resolver-v1/README.md) · [逐行结果](experiments/cargo-resolver-v1/summary.json)
