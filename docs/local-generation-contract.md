# 可选本地生成：引用合同与失败隔离

日期：2026-11-15（UTC+08）。本模块连接自行启动的本地 llama.cpp b12359 OpenAI兼容接口，不安装或下载模型。零新增Python依赖。历史检索及冻结挑战代码不变。

## 可运行路径

模型启动方式和固定权重信息见本轮真实模型实验记录。先启动仅绑定127.0.0.1的llama-server，然后从仓库根目录运行：

```bash
mkdir -p build
PYTHONPATH=src python -m rag_foundation.generation \
  'What error is raised when MAX_CONTENT_LENGTH is exceeded?' \
  --endpoint http://127.0.0.1:8080 > build/generated-answer.json
```

Python接口：`GenerationPipeline(Path('.'), endpoint='http://127.0.0.1:8080').answer(query, k=3)`。

引用检索保持原0.6覆盖门与中文词典，最多3个完整片段、总计12000字符。模型获得原始问题与片段ID/正文；prompt要求不把片段当指令，不依据话题相似推断实际配置、近期事件或普遍保证。这是提示约束，不是可靠的注入防护证明。

默认temperature=0、seed=42、max_tokens=512、enable_thinking=false。`response_format=json_schema`请求恰好三个字段：`answer`、`citations`、`abstain`。本地拒绝外层/内层重复JSON键与非有限数，并再次校验类型、字段集合、重复/越界引用，且只接受finish_reason=stop。语法或引用ID合法不能证明语义充分，因此所有结果仍标记`semantic_support=unverified`。

## 状态必须分开计数

- `answered`：返回非空文本、至少一个属于真实供给片段的引用ID，结构合同通过。不是自动判为正确答案。
- `evidence_abstained` / `no_retrieved_context`：检索无可供上下文，未调用模型。
- `evidence_abstained` / `model_abstention`：模型明确返回空答案、空引用、abstain=true。拒答是否恰当须用标签另评估。
- `transport_error`：连接/超时/HTTP非200。不可算成功拒答。
- `invalid_response`：畸形JSON、schema/引用错误、截断输出、响应超限。不可算成功拒答，也不展示为有效答案。

响应保存真实retrieval、供给context、raw_response、引用来源定位。失败不会悄悄退回检索片段并冒称生成答案。错误响应最多262144字节；超限不保存完整body。客户端只连接字面127.0.0.1，不读代理、不跟随重定向、不接受用户名密码/远端host；无自动重试。超时限制socket等待而非完整任务绝对截止，非公网生产服务。

## 验证范围

新增16项合同测试，真实本地fake HTTP socket覆盖正常回答、模型拒答、503、畸形输出、非法引用、截断及超限。fake server只验证协议，不是模型实验。另验证无上下文不调用模型、引用来源回映和仅回环地址。本轮完整源码75项测试通过，真实模型结果由独立冻结实验记录给出，不把mock输出计为模型成功率。CI不下载模型、不运行付费服务。

## 来源与限制

[llama.cpp b12359服务文档](https://github.com/ggml-org/llama.cpp/tree/b12359/tools/server)和[MIT许可证](https://github.com/ggml-org/llama.cpp/blob/b12359/LICENSE)是接口参考，不复制其实现。语料保持Flask BSD-3-Clause，模型许可独立记录。小模型可能生成有合法引用但不受证据支持的答案，需要逐例审查，不等于生产RAG或用户已掌握相关技能。
