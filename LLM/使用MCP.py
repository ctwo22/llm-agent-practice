import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
import Local_Settings  # 加载本地设置


async def main():
    # 1.启动mcp_server
    async with MCPServerStdio(
            name='普通mcp服务器',
            params={
                'command': 'python',
                'args': ['mcp_server.py']
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
