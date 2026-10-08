import os

from openai import AsyncOpenAI

from agents import (
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_disabled
)

client = AsyncOpenAI(
    base_url='https://api.deepseek.com',
    api_key=os.environ.get('DEEPSEEK_API_KEY')
)

set_default_openai_client(client=client, use_for_tracing=False)  # 使用自定义客户端
# set_default_openai_api('chat_completions')  # 使用兼容的API模式 -抛弃了
set_default_openai_api('response') # 现在deepseek可以兼容了
set_tracing_disabled(disabled=True)  # 禁用OpenAI的跟踪服务