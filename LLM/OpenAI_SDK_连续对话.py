import asyncio

from agents import Agent, Runner

import Local_Settings  # 加载本地设置

agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友'
)


async def main():
    result = await Runner.run(agent, '1+1=?')
    history = result.to_input_list()  # 历史记录=result的输出列表
    print(history)
    history.append({'role': 'user', 'content': '再加1=?'})  # 对会话内容的管理
    result = await Runner.run(agent, history)
    print(result.final_output)

    print(result.to_input_list())


if __name__ == '__main__':
    asyncio.run(main())
