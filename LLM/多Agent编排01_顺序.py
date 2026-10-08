import asyncio
from agents import Agent, Runner
import Local_Settings  # 加载本地设置

agent_a = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友',
)
agent_b = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为情感导师,对我女朋友说的话进行评价',
)


async def main():
    result = await Runner.run(agent_a, '你有多喜欢我啊')
    print('a:'+result.final_output)

    result = await Runner.run(agent_b, result.final_output)
    print('b:'+result.final_output)


if __name__ == '__main__':
    asyncio.run(main())
