# 首先: 该模型一定要支持多模态(图片识别)
# 其次: 使用的这个框架也要支持该模态
import asyncio
import base64
from pathlib import Path

from agents import Agent, Runner
import Local_Settings  # 加载本地设置

# 用 __file__ 定位图片:本文件在 Startagent/LLM/ 下,上一级就是项目根 Startagent/
# 原写法 r'/\images\1.png' 会被 os.path.abspath 解析成 \\images\1.png → 必然 FileNotFoundError
# 依赖「当前工作目录」的路径是坑:换个目录运行就崩,用 __file__ 则任何位置运行都正确
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_PATH = BASE_DIR / 'images' / '1.png'

agent = Agent(
    model='deepseek-flash',
    name='AI助手',
    instructions='你作为我女朋友'
)


def sniff_mime(image_bytes: bytes) -> str:
    """按文件头「魔数」判断图片的真实格式

    扩展名不可信:本项目的 images/1.png 实际是 JPEG(FF D8 FF E0 + JFIF),
    若按扩展名声明成 image/png,部分服务端会因「声明格式与实际内容不符」直接拒绝。
    """
    if image_bytes[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if image_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return 'image/webp'
    return 'application/octet-stream'


def encode_image(image_path):
    """把图片读成 base64 字符串 —— LLM 只收字符串,不收二进制"""
    with open(image_path, 'rb') as f:  # with open (图片路径 ,'rb'二进制) as(命名为) f
        bin_content = f.read()  # 读取f的二进制码
        return base64.b64encode(bin_content).decode('utf-8')


async def main():
    # 路径解析错误的报错信息很隐蔽(只说 No such file),这里主动给出可读提示
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f'找不到图片:{IMAGE_PATH}')

    base64_image = encode_image(IMAGE_PATH)
    # base64_image 图片的字符串格式 -LLM可以接收字符串格式
    # data URL 里的 MIME 必须与文件真实格式一致,不能照搬扩展名
    mime = sniff_mime(IMAGE_PATH.read_bytes())
    print(f'图片真实格式:{mime}')  # 调试提示:此处若显示 image/jpeg 说明扩展名具有误导性

    # 【关键】openai-agents 底层走的是 Responses API(client.responses.create),
    # 它和 Chat Completions 的消息格式不一样,内容分片的 type 完全不同:
    #
    #   Chat Completions : {'type': 'image_url', 'image_url': {'url': ...}}
    #                      {'type': 'text',      'text': ...}
    #   Responses API    : {'type': 'input_image', 'image_url': <data URL 字符串>}
    #                      {'type': 'input_text',  'text': ...}
    #
    # 按 Chat Completions 的写法传会得到 422:
    #   unknown variant `image_url`, expected one of
    #   `input_text`, `output_text`, `input_image`, `input_file`
    #
    # 另外注意 image_url 在这里是「数据 URL 字符串」,不再是 {'url': ...} 嵌套对象。
    # (参考 agents/models/chatcmpl_converter.py 中 SDK 自身的拼装方式)
    message = [
        {'role': 'user', 'content': [
            {'type': 'input_image', 'image_url': f'data:{mime};base64,{base64_image}'},
            {'type': 'input_text', 'text': '评价这张图片'}
        ]}
    ]

    result = await Runner.run(agent, message)
    print(result.final_output)


if __name__ == '__main__':
    asyncio.run(main())
