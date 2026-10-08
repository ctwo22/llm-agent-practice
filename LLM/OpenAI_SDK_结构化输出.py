import asyncio
from agents import Agent, Runner
from pydantic import BaseModel
import Local_Settings  # 加载本地设置


class data(BaseModel):
    姓名: str
    年龄: int
    性别: str
    事迹: str


agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友',
    output_type=data # 要和Agent说明输出格式按照data
)


async def main():
    result = await Runner.run(agent, '介绍一个中国值得被铭记得人')
    print(result.final_output)
    ojb: data = result.final_output
    print(ojb.姓名)
    print(ojb.年龄)
    print(ojb.性别)
    print(ojb.事迹)


if __name__ == '__main__':
    asyncio.run(main())
