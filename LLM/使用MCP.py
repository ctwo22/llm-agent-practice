import asyncio
import sys
from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStdio
import Local_Settings  # 加载本地设置

# MCP 服务器脚本的绝对路径:用 __file__ 定位,不再依赖「当前工作目录恰好在 LLM/」
SERVER_SCRIPT = Path(__file__).resolve().parent / 'mcp_server.py'


async def main():
    # 原写法 params={'command': 'python', 'args': ['mcp_server.py']} 藏了两个隐式依赖,
    # 导致它只能在「.venv 已激活 且 工作目录是 LLM/」时才能跑起来:
    #
    #   ① 'python' 取的是 PATH 上第一个 python。只有 venv 已激活时它才是装了 mcp 的解释器;
    #      否则会解析到系统里的另一个 python,子进程直接 ModuleNotFoundError: No module named 'mcp'。
    #   ② 'mcp_server.py' 是相对路径,换个工作目录(比如项目根目录)就找不到文件。
    #
    # 这就是典型的「在我机器上能跑」:环境一变就失效。
    # sys.executable = 正在运行本文件的解释器,它必然装有 mcp,而且不依赖 PATH 顺序。
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f'找不到 MCP 服务器脚本:{SERVER_SCRIPT}')

    # 1.启动mcp_server
    async with MCPServerStdio(
            name='普通mcp服务器',
            params={
                'command': sys.executable,
                'args': [str(SERVER_SCRIPT)]
            }
    ) as mcp_server:
        agent = Agent(
            model='deepseek-flash',
            name='AI助手',
            instructions='你作为我女朋友',
            mcp_servers=[mcp_server, ] #mcp是把工具从别的进程递进来
        )
        result = await Runner.run(agent, '三明现在的天气怎样')
        print(result.final_output)


if __name__ == '__main__':
    asyncio.run(main())
