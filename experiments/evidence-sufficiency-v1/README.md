# Evidence gate 对照实验 · 2026-11-16 MYT

**结论：不建议启用本轮 evidence gate。实际跑通了链路，但没有验证出可靠的证据充分性判断。**

12 个新问题组成 6 个英中事实对，按充分、相关不足、主题缺失分层；每层都包含数值和
非数值题。先保存实际检索片段、人工充分性标签并独立复核，再冻结执行。
生成器、检索、上下文、提示词、采样及输出校验在 gate off/on 两臂保持相同。
on 额外调用一次同一模型做证据判断，**总计算成本并不相等**。

## 真实结果

- 2 题没有检索候选，两臂都未调用模型，排除新门增益。
- 其余 10 题的 gate-on **全部引用校验失败**，不是合法的“证据不足”判定。
- gate-off 接受了 3 个有支持的正确答案、4 个无依据或答非所问答案；3 个输出无效。
- gate-on 没有让生成器执行。有支持正确回答覆盖从 **3/4 降至 0/4**。
- 增加的合法正确证据拒绝为 **0/6**；4 个充分题也全被协议错误阻断。
  “合法误拒判定为 0”不能解释成误拒率良好，因为门没有任何合法判定。
- 同题 full/删唯一值的 4 个诊断全部无效；14 个 gate raw 都声称 `sufficient=true`，
  包括全部不足题。没有证明门能随决定性证据变化作出正确判定。

[逐层报告](REPORT.md) · [可复算汇总](summary.json) · [人工结果复核](manual-review.json) ·
[原始记录](recorded/) · [事后引用失败诊断](quote-diagnostics.json)

## 最短审核路径：不下载、不运行模型

从仓库根目录运行，Python 3.10+，仅标准库：

```bash
python experiments/evidence-sufficiency-v1/audit_record.py
python -m unittest discover -s experiments/evidence-sufficiency-v1 -p 'test_*.py' -v
```

审计成功表示冻结输入、实际片段、原始输出哈希和计数一致，不表示模型通过。
语义标签来自预先人工审阅，不是自动引用检查产生的真值。旧题只作记录回归审计。

## 可选真实模型复现

Linux x86_64、Python 3.12，约 586 MB 公开下载，建议至少 5 GB 可用 RAM 和 2 GB
临时磁盘。仍使用已固定的 Qwen3.5-0.8B Q4_0 / 官方 llama.cpp b12359，免费 CPU。
模型与下载包只放 `/tmp`，不放进 Git：

```bash
python3 experiments/evidence-sufficiency-v1/prepare_assets.py --directory /tmp/rag-local-assets
python3 experiments/evidence-sufficiency-v1/run_experiment.py \
  --assets /tmp/rag-local-assets --output build/evidence-sufficiency-v1-my-run
```

runner 同环境启动/关闭本地 loopback 服务，先校验模型、源码、冻结问题和实际检索结果，
再执行 24 个 off/on 流程与 4 个 gate-only 诊断。不覆盖旧运行、不重试或修复答案。
本轮共 24 次实际模型调用：10 次 baseline 生成、10 次 pipeline gate、4 次诊断 gate。
通常测试/CI 不下载或启动模型。新运行日志只留在 `build/`，不得未经检查发布机器路径。

## 材料和边界

- [cases.json](cases.json)：新题、人工标签、真正供给的片段、协议和冻结源码哈希。
- [cases.lock.json](cases.lock.json)：首请求前冻结和独立审查记录。
- [run_experiment.py](run_experiment.py)：实际执行版本，其哈希在 manifest 中。
- `recorded/`：28 个完整流程返回和 manifest，保留原始模型响应文本。
- `quote-diagnostics.json`：只在事后解释失败，空白归一化没有进入正式门，没有补跑“修复臂”。

Flask 文档源为固定提交 `ab8149664182b662453a563161aa89013c806dc9`，BSD-3-Clause，
见 [NOTICE](../../NOTICE.md)。诊断对原文仅删除唯一 `500_000`，并明确标识为修改片段；
不伪装成完整上游原文。模型 Apache-2.0、运行时 MIT，固定下载/哈希/许可见
[来源清单](../local-generation-smoke/sources.json)。没有私有资料、收费服务、权重或第三方程序入库。

这是作者了解语料后的开发实验，12 题不是 12 个独立事实。诊断设计事先已知，
不是 untouched held-out 集。精确引用只能证明出处，不能证明它支持所问论断。
