import os
import httpx  # 第三方库 -pip install httpx
from openai import OpenAI

# 直接传参更可靠
client = OpenAI(
    base_url='https://api.deepseek.com',
    api_key=os.environ.get('DEEPSEEK_API_KEY')  # 本地部署
)  # 固定格式

stream = client.chat.completions.create(

    model='deepseek-v4-flash',  # 使用正确的模型名称
    messages=[
        {'role': "system", 'content': "作为女朋友"},
        {"role": "user", "content": input()},
    ],
    temperature=1,
    stream=True,
)

# stream=True 返回的是「流对象」,必须逐块迭代才会真正拿到内容
# 之前只把返回值赋给 stream 却从未迭代 → 请求发出去了,但程序一个字都不打印
# 逐步、增量的输出内容 -配合stream
for chunk in stream:
    if chunk.choices[0].delta.content:  # 部分 chunk 的 content 为 None(如末尾块)
        print(chunk.choices[0].delta.content, end='', flush=True)
print()  # end='' 会吃掉换行,末尾手动补一个

# 非流式的等价写法(stream=False 时用):
# completion = client.chat.completions.create(model=..., messages=..., stream=False)
# print(completion.choices[0].message.content)

'''

LLM 对话通过Messages进行,每个消息都是一个词典
基础的key:
①role:
'user' : 用户输入的消息
'assistant' : AI助手的消息,LLM的回复 -历史回复记录
'system' : 给LLM的设定 -可以强制LLM的回答

②content:文本内容

③temperature: 温度控制LLM 生成文本的创造性和随机性, 范围0-2, 默认1
t→0 :保守,重复性高 -准确性and一致性的任务
t→2 :创新,发散,重复性低 -创造性和灵感的任务


'''
