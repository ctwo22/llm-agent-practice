import asyncio
from agents import Agent, Runner
import Local_Settings  # 加载本地设置

agent_a = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='严格按照中文回答翻译句子',
)
agent_b = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='严格按照英文回答翻译句子',
)
agent_c = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='严格按照日文回答翻译句子',
)


async def main():
    query = '사랑해'
    re1, re2, re3 = await asyncio.gather(
        Runner.run(agent_a,query),
        Runner.run(agent_b,query),
        Runner.run(agent_c,query),
    )
    print(re1.final_output)
    print(re2.final_output)
    print(re3.final_output)


if __name__ == '__main__':
    asyncio.run(main())
