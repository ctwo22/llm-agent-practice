import asyncio
from agents import Agent, Runner
import Local_Settings  # 加载本地设置

agent_a = Agent(
    model='deepseek-flash',
    name='AI中文翻译助手',
    instructions='严格按照中文回答翻译句子',
    handoff_description='严格按照中文回答翻译句子'
    # handoff_description：是给“其他 agent / 路由决策者”看的，用来判断要不要把任务转交给你。
    # instructions：是 agent 自己被激活后，用来指导它具体怎么回答、怎么做事的。
)
agent_b = Agent(
    model='deepseek-flash',
    name='AI英文翻译助手',
    instructions='严格按照英文回答翻译句子',
)
agent_c = Agent(
    model='deepseek-flash',
    name='AI日语翻译助手',
    instructions='严格按照日文回答翻译句子',
)
agent_d = Agent(
    model='deepseek-flash',
    name='前台助手',
    instructions='不回答问题,而是将问题交接给适合的agent',
    handoffs=[agent_a, agent_b, agent_c]
)


async def main():
    query = 'I love you,只翻译成纯中文,还要带点情趣,要有直译版、古风版等等(不下5个,不超过8个)'
    result = await Runner.run(agent_d, query)
    print(result.final_output)

    # 使用流式可以获取内部调用流程 --有点费钱
    # result = Runner.run_streamed(agent_d,query)
    # async for event in result.stream_events():
    #     print(event)


if __name__ == '__main__':
    asyncio.run(main())
