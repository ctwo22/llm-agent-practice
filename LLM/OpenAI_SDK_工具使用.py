# 减少代码量

import asyncio
from agents import Agent, Runner, function_tool
import httpx
import Local_Settings  # 加载本地设置


@function_tool  # 转换为Agent可识别工具
def get_weather(city):
    # """xxx"""  文档注释 -可被识别
    """根据城市名查询指定地点的当前实时天气.
    当用户询问任何城市的天气、气温、温度、多冷、多热、穿什么衣服等此类时调用此工具。"""
    try:
        url = 'https://uapis.cn/api/v1/misc/weather'  # 调用API的地址
        response = httpx.get(
            url,
            params={
                'city': city,
                'extended': True,
                'indices': True,
            },

            timeout=30.0
        )

        response.raise_for_status()  # 状态码不是200就报错

        data = response.json()  # json → python字典

        # 上面的data就是表示从天气API里输入城市后返回的数据 ,实际都在运行中了
        city_name = data.get('city', city)
        weather = data.get('weather', "未知")
        temperature = data.get('temperature', '未知')
        wind_power = data.get('wind_power', "")
        humidity = data.get('humidity', "")
        feels_like = data.get('feels_like', "")
        report_time = data.get('report_time', "")

        result = (  # 如果调用此工具 ,一定会返回的一些答案
            f"{city_name}当前天气:{weather},"
            f"温度:{temperature},"
            f'风力:{wind_power},'
            f'湿度:{humidity},'
            f'体感温度:{feels_like},'
            f'发布时间:{report_time},'

        )
        return result

    except Exception as e:
        return f'天气查询失败:{str(e)}'


agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友',
    tools=[get_weather, ]  # 要告诉Agent使用工具这一块OvO
)


async def main():
    result = await Runner.run(agent, '三明天气详细信息')
    print(result.final_output)


if __name__ == '__main__':
    asyncio.run(main())
