# 首先: 该模型一定要支持多模态(图片识别)
# 其次: 使用的这个框架也要支持该模态
import asyncio
import base64

from agents import Agent, Runner
import Local_Settings  # 加载本地设置

agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友'
)


def encode_inage(image_path):
    with open(image_path, 'rb') as f:  # with open (图片路径 ,'rb'二进制) as(命名为) f
        bin_content = f.read()  # 读取f的二进制码
        return base64.b64encode(bin_content).decode('utf-8')


async def main():
    base64_image = encode_inage(r'/\images\1.png')
    # base64_image 图片的字符串格式 -LLM可以接收字符串格式
    # r'' 使用普通字符
    message = [
        {'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image}'}},
            # 'image_url':{'url':f'data:image/png;base64,{base64_image}'}
            # png == 传入图片的格式    {图片路径}
            {'type': 'text', 'text': '评价这张图片'}
        ]}
    ]

    result = await Runner.run(agent, message)
    print(result.final_output)


if __name__ == '__main__':
    asyncio.run(main())
