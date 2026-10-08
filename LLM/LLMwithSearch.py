import os
from openai import OpenAI

# 试试专用于三明学院信息查询

# 直接传参更可靠
client = OpenAI(
    base_url='https://api.deepseek.com',
    api_key=os.environ.get('DEEPSEEK_API_KEY')  # 本地部署
)

stream = client.responses.create(
    model='deepseek-v4-flash',  # 使用正确的模型名称
    tools=[{'type': 'web_search'}],
    input=[  # ← 改成 input，并且是列表
        {'role': "system", 'content': "作为女朋友"},
        {"role": "user", "content": input()}
    ],
    temperature=1,
    # stream=True,  # 注释掉表示非流式输出
)

# 直接完整输出
print(stream)  # 打印完整响应对象
print(stream.output_text)  # 打印文本内容
