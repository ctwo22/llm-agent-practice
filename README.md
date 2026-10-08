# llm-agent-practice

LLM 应用开发实践：从 OpenAI SDK 基础调用，到手写 ReAct 循环、MCP 协议与多 Agent 编排。

本仓库不是教程代码的复制，而是**把 Agent 的核心机制逐个拆开实现一遍**：同一个「让模型调用工具」的需求，
先用框架提供的 `@function_tool` 做一遍，再用原生 `tools=[...]` 参数手写一遍，最后用 MCP 协议跨进程做一遍。
三种方式放在一起看，框架到底替你做了什么就很清楚了。

---

## 能力地图

代码按依赖程度从浅到深排列，建议按这个顺序阅读：

| 阶段 | 文件 | 解决的问题 |
|---|---|---|
| **① SDK 入门** | `OpenAI_SDK.py` | Agent 最小用法 + 流式输出（`run_streamed` / `ResponseTextDeltaEvent`） |
| | `OpenAI_SDK_连续对话.py` | 多轮对话：`result.to_input_list()` 管理历史 |
| | `OpenAI_SDK_结构化输出.py` | Pydantic `output_type` 强制模型返回结构化数据 |
| **② 工具调用** | `OpenAI_SDK_工具使用.py` | `@function_tool` 装饰器声明工具 |
| | `LLM_with_API.py` | 原生 Chat Completions + 流式迭代 |
| | `LLMwithSearch.py` | `client.responses.create` + `web_search` 内置工具 |
| | `LLMwithWeather.py` | **手写 Function Calling 循环** + 滑动窗口上下文管理 + Token 统计 |
| **③ Agent 机制** | `ReAct_agent.py` | **手写 ReAct 循环**：思考 → 操作 → 观察 → 答案 |
| | `OpenAI_SDK_多模态.py` | 图片 base64 编码 + 视觉输入 |
| **④ MCP 协议** | `mcp_server.py` | MCP 服务端，暴露 `get_weather` / `ls` 两个工具 |
| | `使用MCP.py` | MCP 客户端，通过 stdio 把外部工具接进 Agent |
| **⑤ 多 Agent** | `多Agent编排01_顺序.py` | 顺序编排：A 的输出作为 B 的输入 |
| | `多Agent编排02_并行.py` | `asyncio.gather` 并行调用多个 Agent |
| | `多Agent编排03_路由(交接).py` | `handoffs` 路由：前台 Agent 按意图分发 |

`Local_Settings.py` 是共享的客户端配置，把 `AsyncOpenAI` 注册为全局默认客户端（含 `set_tracing_disabled`）。

---

## 环境要求

- **Python 3.14+**（用到 3.12 引入的 f-string 嵌套同类引号语法）
- Windows / macOS / Linux
- 一个 OpenAI 兼容的 API Key（本项目用 [DeepSeek](https://api.deepseek.com)）

## 安装

```powershell
git clone https://github.com/ctwo22/llm-agent-practice.git
cd llm-agent-practice

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

## 配置密钥

代码通过环境变量读取密钥，**不要把 Key 写进代码**：

```powershell
# 当前会话
$env:DEEPSEEK_API_KEY = "sk-你的密钥"

# 永久（Windows）
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-你的密钥", "User")
```

## 运行

所有脚本都依赖 `Local_Settings`，**需要在 `LLM/` 目录下运行**：

```powershell
cd LLM
python OpenAI_SDK.py
python ReAct_agent.py
python 使用MCP.py
```

---

## 依赖治理

初始的 `pip freeze` 快照是 **44 个包**，最终 `requirements.txt` 只保留了 **6 个直接依赖**：

```
openai==3.6.0              LLM 客户端
openai-agents==0.22.0      Agent 框架（agents.Agent / Runner / function_tool）
mcp==2.1.1                 MCP 协议
httpx==0.28.1              HTTP 客户端
pydantic==2.13.5           数据模型
deepseek-tokenizer==0.3.0  分词器
```

判断标准：**这 6 个能在源码里找到对应的 `import`，其余 38 个一个都找不到。**

⚠️ 这里有个容易踩的坑：**「从清单里删掉」不等于「从环境里卸载」**。
`httpx2` / `httpcore2` / `uvicorn` / `starlette` / `sse-starlette` 不在清单里，但它们是
`openai` 和 `mcp` 的**硬依赖**（`openai 3.6.0` 的 METADATA 写着 `Requires-Dist: httpx2<3,>=2.7.0`）。
清单里不列，环境里必须留着，交给 pip 自动解析。

另外清理掉了 `Runner==1.1`——那是 PyPI 上一个 GPLv2 的 Unix shell 命令运行器，和代码里
`from agents import Runner`（来自 `openai-agents`）完全是两回事，属于安装时的包名撞车。

---

## Badcase 记录

这部分是本仓库最有价值的内容：每个 bug 独立一次提交，记录根因与修法。
面试被问到「你遇到的最难的问题是什么」时，这些都是可直接展开的素材。

| 提交 | 文件 | 根因 | 修法 |
|---|---|---|---|
| `dc819a6` | `LLM_with_API.py` | `stream=True` 返回流对象，但只赋值从未迭代，所有 chunk 被丢弃 → **程序一个字都不输出** | 补上 `for chunk in stream` 循环 |
| `9736f15` | `OpenAI_SDK_多模态.py` | ① `r'/\images\1.png'` 被 `os.path.abspath` 解析成 `\\images\1.png`，必然 FileNotFoundError；②**该文件真实格式是 JPEG**（魔数 `FF D8 FF E0`），却硬编码 `data:image/png` | 改用 `Path(__file__).resolve()` 定位；新增按魔数探测 MIME |
| `046d89b` | `ReAct_agent.py` | `max_turns = 1`（注释却写"最多10轮"）→ 模型调用工具后循环立即结束，**看不到工具返回值**，永远拿不到最终答案 | 改为可配置上限 + 整体超时兜底 + 未收敛时明确提示 |
| `5ba979b` | `LLMwithWeather.py` | 两个记忆函数定义在 `while True` **之后**，是死代码；且判断逻辑自相矛盾（外层 `!= 'system'`、内层 `== 'system'`，内层恒假） | 上移到循环之前并接入主流程；改为按 user 消息切分「轮」，避免切断 `tool_calls` 与 `tool` 消息的配对 |
| `93d12a5` | `LLMwithWeather.py` | Token 只统计用户输入，注释自己都承认"输出和 system 都没算" | 改用 API 返回的 `usage`；注意带工具调用时**一轮会发起两次模型调用**，流式需 `stream_options={'include_usage': True}` 且 usage chunk 的 `choices` 为空需判空 |
| `42a7286` | `使用MCP.py` | `params={'command': 'python', 'args': ['mcp_server.py']}` **隐式依赖运行环境**，只在「venv 已激活 且 工作目录是 `LLM/`」时才能跑——典型的"在我机器上能跑" | 改用 `sys.executable`（必然装有依赖，不受 PATH 顺序影响）+ 基于 `__file__` 的绝对路径 |

---

## 已知问题 / 后续计划

- **模型名不统一**：`deepseek-flash` / `deepseek-v4-flash` 混用，需要对齐到实际可用的模型名
- **部分脚本缺 `__main__` 保护**：`LLMwithWeather.py` 的主循环在模块级，import 会阻塞在 `input()`
- **上下文管理偏简单**：目前只有滑动窗口，摘要记忆（`content_summary`）尚未接入
- 下一步：接入向量库，构建带引用标注的 RAG 问答系统

---

## License

个人学习项目，未指定开源协议。
