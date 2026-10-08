# 从调 API 到编排 Agent —— 我的 LLM 应用实践

我是 ctwo22，正在找 **AI 应用工程师**方向的实习。

这个仓库是我第 1 周的学习产出：**15 个脚本、9 次提交、6 个真实 bug 的完整定位与修复记录**。

我写它不是为了"跑通一个 demo"。我想搞清楚一件事：

> 当框架替我做了很多事的时候，我到底懂不懂底下发生了什么？

所以我用**三种方式**实现了同一个需求——让模型调用工具：

1. 用 `openai-agents` 的 `@function_tool` 装饰器（框架替我生成 JSON Schema、替我跑循环）
2. 用原生 `client.chat.completions.create(tools=[...])` 手写整个调用循环
3. 用 **MCP 协议**把工具放到另一个进程里，跨进程调用

三种写法放在一起，框架到底封装了什么、代价是什么，就很清楚了。

---

## 我的学习路径

代码按依赖程度从浅到深排列，这也是我实际的推进顺序。

### 第一步：把 SDK 用熟

| 文件 | 我在这里搞懂了什么 |
|---|---|
| `OpenAI_SDK.py` | Agent 最小用法；流式不是 `print` 出来的，是要消费 `stream_events()` 里的事件 |
| `OpenAI_SDK_连续对话.py` | 多轮对话的本质是**手动维护历史**——`result.to_input_list()` 拿回来再塞回去 |
| `OpenAI_SDK_结构化输出.py` | 用 Pydantic `output_type` 让模型返回对象而不是字符串，之后可以直接 `.姓名` 取值 |

### 第二步：工具调用——框架版 vs 手写版

| 文件 | 我的收获 |
|---|---|
| `OpenAI_SDK_工具使用.py` | `@function_tool` 一行搞定。**但我不满足于此**：它到底生成什么 Schema？循环跑了几轮？ |
| `LLM_with_API.py` | 回到最原始的 Chat Completions，理解 `messages` / `temperature` / `stream` |
| `LLMwithSearch.py` | 发现 `client.responses.create` 是另一套 API，连参数名都不一样（`input` 而不是 `messages`） |
| `LLMwithWeather.py` | **手写完整 Function Calling 循环**：模型要工具 → 我执行 → 把结果塞回历史 → 再问一次。同时在这里做了上下文管理和 Token 统计 |
| `ReAct_agent.py` | **完全不用框架手写 Agent 循环**：思考 → 操作 → 观察 → 答案 |

这两个文件是我花时间最多的。写完我才真正明白：**所谓 Agent，就是一个 while 循环 + 工具调用的结果回灌。**

### 第三步：MCP 协议

| 文件 | 说明 |
|---|---|
| `mcp_server.py` | 用 `MCPServer` 暴露 `get_weather` / `ls` 两个工具 |
| `使用MCP.py` | 客户端通过 **stdio 跨进程**把这些工具接进 Agent |

这一步让我理解了 MCP 的价值：**工具不再是代码里的一个函数，而是一个独立进程提供的服务**——可以换语言写、可以独立部署、可以被多个 Agent 复用。

### 第四步：多 Agent 编排

| 文件 | 编排模式 |
|---|---|
| `多Agent编排01_顺序.py` | 顺序：A 的输出直接作为 B 的输入 |
| `多Agent编排02_并行.py` | 并行：`asyncio.gather` 同时问三个翻译 Agent |
| `多Agent编排03_路由(交接).py` | 路由：前台 Agent 靠 `handoff_description` 判断该把任务交给谁 |

`handoff_description` 和 `instructions` 的区别是我在这里踩明白的：前者是**给其他 Agent 看的**（判断要不要转交），后者是**给自己看的**（转交后怎么做）。

---

## 我踩过的坑（这部分我最有话说）

每个 bug 一次独立提交。**这些都是我真实遇到、逐个定位出来的**，不是从教程里抄的。

### ① `dc819a6` — 程序一个字都不输出

**现象**：脚本跑完，终端空白，不报错。

**定位**：我没有瞎猜，而是用 `ast` 把模块顶层节点打出来看——只有 3 个 import、2 个赋值、1 个字符串字面量，**没有任何语句会执行打印**。

**根因**：`stream=True` 返回的是一个**流对象**，不是结果。我只把它赋值给变量就完事了，`for chunk in stream` 那段被注释掉了。对象建好了，但从来没人消费它。

**学到**：流式 API 的返回值和普通 API 完全不同——**拿到手只是开始，迭代它才是请求真正发生的时候**。

### ② `9736f15` — 图片路径 + 一个我完全没想到的副因

**现象**：`FileNotFoundError: [Errno 2] No such file or directory: '\images\1.png'`

**定位**：我把 `r'/\images\1.png'` 丢给 `os.path.abspath` 实测，得到 `\\images\1.png`——**开头的 `/` 让它变成了相对当前盘符根目录的路径**。修复后用 `Path(__file__).resolve().parent.parent` 定位，从任何目录运行都正确。

**副因**：路径修好了还是可能被拒。我读了图片的文件头，发现**`images/1.png` 的真实魔数是 `FF D8 FF E0` + `JFIF`——它其实是个 JPEG 文件**，而我的代码硬编码 `data:image/png`。

**学到**：**扩展名不可信**。我加了一个 `sniff_mime()` 按魔数判断真实格式，输出变成 `data:image/jpeg;base64,/9j/4AAQ...`。

### ③ `046d89b` — 模型看不到工具的返回结果

**现象**：模型调了工具，工具也返回了数据，但**它永远给不出最终答案**，程序静默结束。

**定位**：`max_turns = 1`——注释上写着"最多循环10轮"，代码里却是 1。所以：调工具 → 结果写回历史 → **循环条件 `1 < 1` 为假 → 立即退出** → 模型根本没机会读到自己刚才要的数据。

**验证**：我写了个假的 `get_completion` 做对照实验，把修复前后两个版本都跑了一遍：

```
MAX_TURNS=1 : 操作 → 观察 → (静默结束，永远没有答案)
MAX_TURNS=10: 操作 → 观察 → 思考:篮球每队12人,场上5人 → 未调用工具,回答结束
```

**学到**：注释和代码不一致的时候，**信代码**。而且"防御性编程"不能防到把功能本身防死。

### ④ `5ba979b` — 死代码 + 一个自相矛盾的判断

**现象**：上下文管理功能写了但从来没生效，对话历史无限增长。

**定位**：两个函数定义在 `while True` **之后**。主循环只能靠 `break` 退出，函数虽然能定义成功，**却永远不会被调用**。

同时那个滑动窗口函数里有个诡异判断——外层 `if role != 'system'`，内层 `if role == 'system'`：**内层恒为假**，补全系统提示的代码永远不会执行。

**我还发现了一个更隐蔽的问题**：直接用 `message_list[-k:]` 切片，可能把 `assistant(tool_calls)` 和紧随其后的 `tool` 消息**切断**，导致 `tool_call_id` 找不到对应调用——API 会直接报错。我实测确认了这一点，所以改成**按 `user` 消息切分"轮"**，工具调用和结果天然成对保留。

### ⑤ `93d12a5` — Token 统计少算了一大半

**现象**：我自己在代码注释里都写了"这个 Token 仅计算了我输入，输出和 system 都没算"。

**定位**：原来只统计 `len(ds_token.encode(user_input))`。但真实消耗是：

```
prompt_tokens     = system 提示 + 完整历史 + 本轮输入
completion_tokens = 模型输出
```

**修的过程中又踩了两个坑**：
- 有工具调用时，一轮对话**实际发起了两次**模型请求（第一次判断要不要调工具，第二次生成回答），两次用量都得计入
- 流式要拿到 usage 必须开 `stream_options={'include_usage': True}`，而**带 usage 的那个 chunk 的 `choices` 是空列表**——原来那句 `chunk.choices[0].delta.content` 会直接 `IndexError`

### ⑥ `42a7286` — 典型的"在我机器上能跑"

**现象**：我在自己电脑上一切正常。但换台机器 / 换个目录就挂。

**定位**：`params={'command': 'python', 'args': ['mcp_server.py']}` 藏了两个**隐式环境依赖**：

| 场景 | 结果 |
|---|---|
| venv 未激活 | ❌ 子进程 `ModuleNotFoundError: No module named 'mcp'`——因为 PATH 上第一个 `python` 是系统里的另一个解释器 |
| 工作目录不是 `LLM/` | ❌ `can't open file`——相对路径找不到 |
| venv 已激活 + 在 `LLM/` | ✅ 能跑（也就是我的环境） |

**最坑的是报错方式**：MCP 服务器是子进程，它崩了主程序**完全不知道**——现象只是"Agent 好像没有工具"，排查方向很容易跑偏。

**修法**：`sys.executable`（正在运行本文件的解释器，必然是装了依赖的那个，且不受 PATH 顺序影响）+ 基于 `__file__` 的绝对路径。

**学到**：**任何依赖"环境恰好如何"的代码都是定时炸弹**。代码应该自己确定它需要什么，而不是假设运行环境已经准备好了。

---

## 我的工程取舍

### 依赖治理：44 个包精简到 6 个

`pip freeze` 出来 44 行。我一个个核对源码里的 `import`，最后只留下 **6 个直接依赖**——其余 38 个**在源码里一个都找不到**。

```
openai==3.6.0              LLM 客户端
openai-agents==0.22.0      Agent 框架
mcp==2.1.1                 MCP 协议
httpx==0.28.1              HTTP 客户端
pydantic==2.13.5           数据模型
deepseek-tokenizer==0.3.0  分词器
```

**但我差点犯一个错**：一开始我以为 `httpx2` / `httpcore2` 是没用的包，想直接卸载。查了 METADATA 才发现：

```
openai 3.6.0   Requires-Dist: httpx2<3,>=2.7.0     ← 硬依赖
mcp 2.1.1      Requires-Dist: httpx2>=2.5.0        ← 硬依赖
httpx2 2.12.0  Requires-Dist: httpcore2==2.12.0
```

**它们是 `openai` 和 `mcp` 的必需依赖，卸掉直接崩。** 正确做法是：**清单里不列，环境里保留，让 pip 自动解析传递依赖。**

顺手还清掉了一个真正的垃圾：`Runner==1.1`——PyPI 上一个 GPLv2 的 Unix shell 命令运行器。我大概是看到代码里 `from agents import Runner` 就去 `pip install Runner` 了，**但那个 `Runner` 来自 `openai-agents` 包，根本不需要单独安装**。

### 其他习惯

- **密钥零硬编码**：5 处 `api_key` 全部走 `os.environ.get('DEEPSEEK_API_KEY')`，推送前用 `git grep` 扫过一遍确认没有泄漏
- **`.gitignore` 先行**：`git init` 之前就写好，确保 `.venv`（7847 个文件）和 `.idea` 从第一次提交起就不进仓库
- **提交粒度**：一个 bug 一次提交，message 写清根因而不只是"修复bug"

---

## 我还没搞定的

我把这些也写出来，因为它们是我下一步的待办：

- **模型名不统一**：`deepseek-flash` 和 `deepseek-v4-flash` 混用，需要对齐到实际可用的模型名
- **部分脚本缺 `__main__` 保护**：`LLMwithWeather.py` 的主循环在模块级，被 import 时会直接阻塞在 `input()`
- **上下文管理只做了一半**：滑动窗口接进去了，但摘要记忆（`content_summary`）还没启用
- **没有测试**：目前全靠手动跑，应该补上 mock 掉 API 的单元测试
- **下一步方向**：接入向量库，做带引用标注的 RAG 问答，并加上评测

---

## 怎么跑起来

**环境**：Python 3.14+（用到了 3.12 引入的 f-string 嵌套同类引号语法）

```powershell
git clone https://github.com/ctwo22/llm-agent-practice.git
cd llm-agent-practice

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 配置密钥（不要写进代码）
$env:DEEPSEEK_API_KEY = "sk-你的密钥"
```

**运行**：脚本之间靠 `Local_Settings` 共享客户端配置，所以需要在 `LLM/` 目录下执行：

```powershell
cd LLM
python OpenAI_SDK.py
python ReAct_agent.py
python 使用MCP.py
```

---

## 写在最后

这个仓库记录的是我第 1 周的状态。我知道它离"工程完备"还有距离——没有测试、没有 CI、模型名还没统一。

但我可以说清楚**每一行代码为什么这么写**，以及**每一个 bug 我是怎么定位出来的**。

如果你对我的排查思路感兴趣，仓库里的 6 个 `fix:` 提交都可以展开聊。

---

*个人学习项目，未指定开源协议。*
