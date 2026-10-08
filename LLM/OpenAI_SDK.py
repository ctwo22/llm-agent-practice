import asyncio
from agents import Agent, Runner
from openai.types.responses import ResponseTextDeltaEvent

import Local_Settings  # 加载本地设置

agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友'
)


# async def main():  # Runner.run(调用对象, 问题)
#     result = await Runner.run(agent, '你是谁?')
#     print(result.final_output)

# 流式
async def main():
    result = Runner.run_streamed(agent, '讲一个故事,最多200字')
    async for event in result.stream_events():
        if event.type == 'raw_response_event' and isinstance(event.data, ResponseTextDeltaEvent):
            # result.stream_events 来自LLM的响应
            # run_stream_event 来自Runner事件 :工具调用...
            print(event.data.delta, end='', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
