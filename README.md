# llm-agent-practice

LLM 应用开发实践：从 OpenAI SDK 基础调用，到手写 ReAct 循环、MCP 协议与多 Agent 编排。

## 项目说明

同一件事——**让模型调用工具**——在本仓库中用三种方式各实现了一遍：

1. 用 `openai-agents` 的 `@function_tool` 装饰器：由框架生成 JSON Schema 并驱动调用循环
2. 用原生 `client.chat.completions.create(tools=[...])`：手动实现完整的调用循环
3. 用 **MCP 协议**：把工具放进独立进程，通过 stdio 跨进程调用

三种实现并排放置，框架封装了什么、付出的代价是什么，可以直接对比。

---

## 文件与能力对应

按依赖程度从浅到深排列，也是建议的阅读顺序。

### 一、SDK 基础

| 文件 | 内容 |
|---|---|
| `OpenAI_SDK.py` | Agent 最小用法；流式输出通过消费 `stream_events()` 事件实现 |
| `OpenAI_SDK_连续对话.py` | 多轮对话：用 `result.to_input_list()` 取回历史再传入 |
| `OpenAI_SDK_结构化输出.py` | 用 Pydantic `output_type` 约束模型返回结构化对象 |

### 二、工具调用

| 文件 | 内容 |
|---|---|
| `OpenAI_SDK_工具使用.py` | `@function_tool` 装饰器声明工具 |
| `LLM_with_API.py` | 原生 Chat Completions + 流式迭代 |
| `LLMwithSearch.py` | `client.responses.create` + `web_search` 内置工具。注意该 API 的参数名是 `input` 而非 `messages` |
| `LLMwithWeather.py` | **手写 Function Calling 循环**：模型请求工具 → 执行 → 结果回灌历史 → 再次请求。含滑动窗口上下文管理与 Token 统计 |
| `ReAct_agent.py` | **不使用框架，手写 ReAct 循环**：思考 → 操作 → 观察 → 答案 |
| `OpenAI_SDK_多模态.py` | 图片 base64 编码 + 视觉输入 |

### 三、MCP 协议

| 文件 | 内容 |
|---|---|
| `mcp_server.py` | MCP 服务端，暴露 `get_weather` / `ls` 两个工具 |
| `使用MCP.py` | MCP 客户端，通过 stdio 将外部进程提供的工具接入 Agent |

工具不再只是代码里的一个函数，而是独立进程提供的服务：可以换语言实现、可以独立部署、可以被多个 Agent 复用。

### 四、多 Agent 编排

| 文件 | 编排模式 |
|---|---|
| `多Agent编排01_顺序.py` | 顺序：上游 Agent 的输出作为下游 Agent 的输入 |
| `多Agent编排02_并行.py` | 并行：`asyncio.gather` 同时调用多个 Agent |
| `多Agent编排03_路由(交接).py` | 路由：入口 Agent 依据 `handoff_description` 分发任务 |

`Local_Settings.py` 是共享的客户端配置，将 `AsyncOpenAI` 注册为全局默认客户端（含 `set_tracing_disabled`）。

`handoff_description` 与 `instructions` 的区别：前者供其他 Agent 判断是否转交任务，后者约束本 Agent 被激活后的行为。

---

## 环境与安装

**Python 3.14+**（用到 3.12 引入的 f-string 嵌套同类引号语法）

```powershell
git clone https://github.com/ctwo22/llm-agent-practice.git
cd llm-agent-practice

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

密钥通过环境变量注入，不写入代码：

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
```

## 运行

脚本通过 `Local_Settings` 共享客户端配置，需要在 `LLM/` 目录下执行：

```powershell
cd LLM
python OpenAI_SDK.py
python ReAct_agent.py
python 使用MCP.py
```

---

## 依赖治理

`pip freeze` 输出 44 个包，`requirements.txt` 最终只保留 **6 个直接依赖**——其余 38 个在源码中找不到任何对应的 `import`：

```
openai==3.6.0              LLM 客户端
openai-agents==0.22.0      Agent 框架（Agent / Runner / function_tool）
mcp==2.1.1                 MCP 协议
httpx==0.28.1              HTTP 客户端
pydantic==2.13.5           数据模型
deepseek-tokenizer==0.3.0  分词器
```

---

## 问题记录

以下 6 个问题均已定位并修复。**每个问题对应一次独立提交**，提交信息中记录了完整根因。

### 1. `LLM_with_API.py` — 流式对象未被迭代，程序无任何输出

**现象**：脚本执行完毕，终端没有任何输出，也不报错。

**定位**：用 `ast` 解析模块顶层节点，结果只有 3 个 import、2 个赋值和 1 个字符串字面量，没有任何语句会执行打印。

**根因**：`stream=True` 返回的是**流对象**而非结果。代码把它赋值给变量后就结束了，真正消费内容的 `for chunk in stream` 一段被注释掉。对象已创建，但从未被迭代，所有 chunk 被丢弃。

**修复**：补回流式迭代循环，并对 `delta.content` 为 `None` 的 chunk 做判空。

**要点**：流式 API 的返回值与普通调用语义不同——**迭代它才是请求真正发生的位置**。

### 2. `OpenAI_SDK_多模态.py` — 三层叠加的错误：路径、MIME 声明、API 协议格式

这一个功能连续暴露出三个互相独立的问题，每修掉一个才会浮现下一个。

#### 第一层：路径解析

**现象**：`FileNotFoundError: [Errno 2] No such file or directory: '\images\1.png'`

**根因**：`r'/\images\1.png'` 开头的 `/` 使其成为**相对当前盘符根目录**的路径，经 `os.path.abspath` 解析后得到 `\\images\1.png`，该路径不存在。

**修复**：改用 `Path(__file__).resolve().parent.parent / 'images' / '1.png'`，不再依赖当前工作目录。

#### 第二层：声明格式与实际内容不符

**现象**：路径修好后请求仍可能被服务端拒绝。

**根因**：读取 `images/1.png` 的文件头，魔数为 `FF D8 FF E0` 且带 `JFIF` 标识——**该文件实际是 JPEG**，而代码硬编码 `data:image/png`。data URL 中声明的 MIME 与内容不一致。

**修复**：新增 `sniff_mime()` 按魔数判断真实格式（支持 JPEG / PNG / GIF / WEBP），输出变为 `data:image/jpeg;base64,/9j/4AAQ...`。

#### 第三层：消息格式用的是另一套 API

**现象**：路径与 MIME 都正确后，服务端返回

```
422 - unknown variant `image_url`,
      expected one of `input_text`, `output_text`, `input_image`, `input_file`
```

**根因**：`openai-agents` 底层调用的是 **Responses API**，而非 Chat Completions。两套 API 的内容分片格式完全不同：

| | Chat Completions | Responses API |
|---|---|---|
| 图片 | `{'type': 'image_url', 'image_url': {'url': ...}}` | `{'type': 'input_image', 'image_url': <字符串>}` |
| 文本 | `{'type': 'text', 'text': ...}` | `{'type': 'input_text', 'text': ...}` |

**定位过程**：

1. 报错信息中 `image_url` 这个变体名在服务端不存在，说明格式本身用错了
2. 检查调用栈，确认实际执行的是 `client.responses.create(**create_kwargs)`（`agents/models/openai_responses.py:824`）
3. 查阅 SDK 类型定义 `openai/types/responses/response_input_image_param.py`，确认正确写法
4. 排查 SDK 是否会做格式转换：`_remove_openai_responses_api_incompatible_fields()` 只处理 `provider_data`、假 ID 与 reasoning 项，**内容分片原样透传**，不会自动纠正

**修复**：改用 Responses API 格式。

**验证**：拦截 SDK 实际发出的请求体，逐项核对内容分片类型：

```
实际发出  : ['input_image', 'input_text']
服务端允许: ['input_file', 'input_image', 'input_text', 'output_text']
不合法类型: 无
```

**要点**：
- **同一个模型服务可能提供多套 API，消息格式互不兼容**。排查时先确认 SDK 实际调用的是哪个端点，而不是凭习惯套用格式。
- 报错中 `expected one of ...` 列出的合法取值，通常就是最直接的线索。
- 定位这类问题靠的是**读调用栈和类型定义**，而不是猜测模型能力。

### 3. `ReAct_agent.py` — 循环上限写死为 1，模型读不到工具结果

**现象**：模型发起了工具调用，工具也返回了数据，但**始终给不出最终答案**，程序静默结束。

**根因**：`max_turns = 1`，而注释写的是"最多循环10轮"。流程实际是：模型请求工具 → 执行并写回历史 → **循环条件 `1 < 1` 为假 → 立即退出**。模型没有机会读取自己刚请求到的数据。

**验证**：用 mock 的 `get_completion` 做修复前后对照：

```
MAX_TURNS=1 : 操作 → 观察 → (静默结束，无最终答案)
MAX_TURNS=10: 操作 → 观察 → 思考:篮球每队12人,场上5人 → 未调用工具,回答结束
```

**修复**：改为可配置上限 `MAX_TURNS`（默认 10）+ 整体超时 `MAX_SECONDS` 兜底，并在未收敛时明确输出提示而非静默退出。

**要点**：注释与代码不一致时以代码为准。防御性编程不应把功能本身防死。

### 4. `LLMwithWeather.py` — 上下文管理函数是死代码，且判断逻辑自相矛盾

**现象**：上下文管理功能已实现但从未生效，对话历史无限增长。

**根因一（死代码）**：`content_summary` 与 `new_message_list_window` 定义在 `while True` **之后**。主循环只能通过 `break` 退出，函数虽然能定义成功，却永远不会被调用。

**根因二（逻辑矛盾）**：滑动窗口函数中的判断外层为 `role != 'system'`、内层为 `role == 'system'`，**内层恒为假**，补全系统提示的分支永远不会执行。

**根因三（更隐蔽）**：直接用 `message_list[-k:]` 切片可能把 `assistant(tool_calls)` 与其后的 `tool` 消息**切断**，使 `tool_call_id` 找不到对应调用，API 会直接报错。实测确认：当历史以 `tool` 消息结尾、取 `[-1:]` 时产生孤儿 tool 消息。

**修复**：两个函数上移到循环之前并通过 `MAX_HISTORY_MESSAGES` 接入主流程；窗口改为**按 `user` 消息切分「轮」**，保证工具调用与结果成对保留。

**要点**：简单的尾部切片会破坏 `tool_calls` 与 `tool` 消息的配对关系，上下文裁剪必须保证消息序列对 API 仍然合法。

### 5. `LLMwithWeather.py` — Token 统计遗漏输出与 system 提示

**现象**：Token 计数明显偏低。原代码注释中也写明了"仅计算了输入，输出和 system 都没算"。

**根因**：统计方式为 `len(ds_token.encode(user_input))`，只计入用户本轮输入。实际消耗应为：

```
prompt_tokens     = system 提示 + 完整历史 + 本轮输入
completion_tokens = 模型输出
```

**修复**：改用 API 返回的 `usage` 字段累计。

**修复过程中另有两个坑**：

- 有工具调用时，一轮对话**实际发起两次模型请求**（第一次判断是否需要工具，第二次生成回答），两次用量都必须计入
- 流式调用需开启 `stream_options={'include_usage': True}` 才能获得 usage；而**携带 usage 的那个 chunk 的 `choices` 是空列表**，原有的 `chunk.choices[0].delta.content` 写法会触发 `IndexError`

**要点**：流式响应中带统计信息的分片不携带内容，读取 `choices[0]` 前必须判空。

### 6. `使用MCP.py` — 隐式依赖 PATH 与工作目录

**现象**：在本机运行正常，换环境或换工作目录即失败。

**根因**：`params={'command': 'python', 'args': ['mcp_server.py']}` 中藏了两个隐式环境依赖：

| 场景 | 结果 |
|---|---|
| venv 未激活 | ❌ 子进程 `ModuleNotFoundError: No module named 'mcp'`——PATH 上第一个 `python` 是另一个未安装 mcp 的解释器 |
| 工作目录不是 `LLM/` | ❌ `can't open file`——相对路径找不到目标脚本 |
| venv 已激活且位于 `LLM/` | ✅ 正常 |

**更容易误导排查的地方**：MCP 服务器是子进程，其崩溃不会传播到主进程——外部现象只是"Agent 似乎没有可用工具"，排查方向容易跑偏。

**修复**：

- `'command': sys.executable`（正在运行本文件的解释器，必然装有依赖，且不受 PATH 顺序影响）
- `'args': [str(Path(__file__).resolve().parent / 'mcp_server.py')]`，并增加脚本存在性校验

**要点**：依赖"运行环境恰好如何"的代码不可移植。代码应当自行确定所需条件，而不是假设环境已经准备好。

---

## 已知问题

- **部分脚本缺少 `__main__` 保护**：`LLMwithWeather.py` 的主循环位于模块级，被 import 时会阻塞在 `input()`
- **上下文管理只完成一半**：滑动窗口已接入；摘要记忆 `content_summary` 尚未启用，也缺少「滑窗 vs 摘要」压缩损失的对比数据

## 后续计划

本仓库覆盖的是 Agent 的基础调用与核心机制。后续按 **RAG 全链路 → 服务化与评测 → Agent 可靠性** 的顺序继续推进。

### 一、RAG 全链路

| 环节 | 内容 |
|---|---|
| 文档解析与切块 | 固定长度 / 递归 / 语义三种切块策略对比 |
| 向量化与检索 | Embedding 接入、向量库建索引、top-k 检索 |
| 混合召回与重排 | BM25 + 向量召回、RRF 融合、Rerank API、K 值对比 |
| 生成与边界 | 上下文组装、引用标注、拒答策略、Prompt Injection 防护 |

### 二、服务化与评测

| 环节 | 内容 |
|---|---|
| 接口服务化 | FastAPI：Pydantic 请求/响应模型、`async` 异步、SSE 流式返回 |
| 部署 | `Dockerfile` + `docker compose` 全栈编排、可视化界面 |
| 评测体系 | golden set（含无答案题）、`Recall@K` / `MRR` / `nDCG`、引用准确率、拒答准确率、P95 延迟、Token 成本 |

### 三、Agent 可靠性（直接扩展本仓库）

| 环节 | 内容 | 对应本仓库 |
|---|---|---|
| 记忆与上下文工程 | 短期/长期记忆、提取与压缩、冲突更新；滑窗与摘要的压缩损失对比 | `LLMwithWeather.py` 的 `content_summary` / `new_message_list_window`（问题记录 4） |
| 工具调用可靠性 | schema 校验、权限、失败分类、幂等、结果验证、工具幻觉 | `mcp_server.py` 的工具 schema、`使用MCP.py` 的子进程失败与未知工具回喂（问题记录 6） |
| 终止与兜底 | 步数上限、超时、转人工 | `ReAct_agent.py` 的 `MAX_TURNS` / `MAX_SECONDS`（问题记录 3） |
| 对比实验 | 如「有记忆 vs 无记忆」在多轮问题上的任务完成率 | 基于上述改动设计 |

「Agent 可靠性」这一部分的目标，是把本仓库已经暴露出问题的几处（问题记录 3、4、6）改造成**可测、可复现**的实现，并给出量化对比。

---

## License

个人学习项目，未指定开源协议。
