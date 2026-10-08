import json
import os
import httpx
from deepseek_tokenizer import ds_token
from openai import OpenAI
from openai.types.beta import assistant

# 1.初始化LLM客户端
client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
)


# 2.python语言构造天气查询工具
def get_weather(city):
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


# 3.给LLM看的'工具说明书' -固定格式居多
tools = [
    {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'description': (
                "根据城市名查询指定地点的当前实时天气。"
                "当用户询问任何城市的天气、气温、温度、多冷、多热、穿什么衣服等此类时调用此工具。"
            ),  # 每个key的最后一个可以不需要写','
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {
                        'type': 'string',
                        'description': "要查询的城市名,例如'北京'、'上海'等等"
                    }
                },
                'required': ['city']
            },
            'strict': True
        }
    }
]

# 4.初始化历史对话
messages = [
    {'role': 'system', 'content': '作为女朋友'}
]


# ========== 上下文管理工具 ==========
# 原代码把这两个函数写在 while True 之后:主循环只能靠 break 退出,
# 所以函数虽然能被定义成功,却永远不会被调用 —— 等于死代码。
# 现在提到循环之前定义,并真正接进主流程。

MAX_HISTORY_MESSAGES = 20  # 历史消息超过这个条数时启用滑动窗口


def content_summary(message_list):
    """摘要记忆:让 LLM 把已有对话压缩成一条 system 消息,替代完整历史

    适合超长对话(比滑动窗口保留更多语义),代价是要多花一次 API 调用。
    """
    response = client.chat.completions.create(
        model='deepseek-v4-flash',
        messages=[{
            'role': 'user',
            'content': f'请对以下对话内容进行总结:{message_list}'
        }]
    )
    return [{'role': 'system', 'content': f'此前对话的总结:{response.choices[0].message.content}'}]


def new_message_list_window(message_list: list, k=2):
    """滑动窗口:保留 system 提示 + 最近 k 轮完整对话

    【原实现的两个 bug】
    ① 外层判断 != 'system',内层判断 == 'system',两者互相矛盾 → 内层恒为假,
       系统提示永远不会被补回。
    ② 直接取 message_list[-k:] 可能把 assistant(tool_calls) 和紧随其后的 tool
       消息切断,API 会因为「tool_call_id 找不到对应调用」直接报错。

    这里改为以 user 消息作为「轮」的起点切分,工具调用与其结果天然成对保留。
    """
    system_msgs = [m for m in message_list if m.get('role') == 'system']
    rest = [m for m in message_list if m.get('role') != 'system']

    turn_starts = [i for i, m in enumerate(rest) if m.get('role') == 'user']
    if len(turn_starts) <= k:
        return list(message_list)  # 轮数还不够,无需裁剪

    return system_msgs + rest[turn_starts[-k]:]


# 5.主循环
print('AI助手启动!')


# ========== Token 统计 ==========
# 原实现只统计「用户本轮输入」:re_token = ds_token.encode(user_input)
# 代码末尾的注释自己都承认「输出和 system 都没算」—— 数字严重偏低。
# 现在改用 API 返回的 usage 字段,它天然覆盖全部消耗:
#   prompt_tokens     = system 提示 + 完整历史 + 本轮输入
#   completion_tokens = 模型输出
#   total_tokens      = 两者之和
# 部分中转/兼容接口不返回 usage,此时退回 deepseek_tokenizer 估算。
TOTAL_PROMPT = 0
TOTAL_COMPLETION = 0
TOTAL_TOKENS = 0


def count_with_ds_token(*texts):
    """离线兜底:用 deepseek_tokenizer 估算 token 数"""
    return sum(len(ds_token.encode(t)) for t in texts if t)


def report_usage(usage, *fallback_texts):
    """累加并打印本轮用量;usage 为 None 时用分词器估算"""
    global TOTAL_PROMPT, TOTAL_COMPLETION, TOTAL_TOKENS

    if usage is not None:
        TOTAL_PROMPT += usage.prompt_tokens
        TOTAL_COMPLETION += usage.completion_tokens
        TOTAL_TOKENS += usage.total_tokens
        print(f'本轮 Token —— 输入(含system与历史):{usage.prompt_tokens} , '
              f'输出:{usage.completion_tokens} , 合计:{usage.total_tokens}')
    else:
        est = count_with_ds_token(*fallback_texts)
        TOTAL_TOKENS += est
        print(f'本轮 Token —— 服务端未返回 usage,估算:{est}')

    print(f'累计 Token —— 输入:{TOTAL_PROMPT} , 输出:{TOTAL_COMPLETION} , 合计:{TOTAL_TOKENS}')


while True:
    user_input = input("c:")

    if user_input in ['退出', 'exit', '拜']:
        print('CgF:下次再见咯💕')
        print(f'本次对话累计 Token:{TOTAL_TOKENS}')
        break
    # 字典表示 {}
    messages.append({"role": "user", 'content': user_input})

    # 5.0 历史过长时启用滑动窗口,避免上下文超限导致调用失败
    # (修复前这两个函数是死代码,上下文只会无限增长)
    if len(messages) > MAX_HISTORY_MESSAGES:
        before = len(messages)
        # 用切片赋值原地替换,保持 messages 这个列表对象的身份不变
        messages[:] = new_message_list_window(messages, k=3)
        print(f'[上下文管理] 历史 {before} 条 → 裁剪为 {len(messages)} 条')

    # 5.1 第一次调用模型 ,判断是否需要调用工具
    response = client.chat.completions.create(  # 固定格式这一块
        model='deepseek-v4-flash',
        messages=messages,
        tools=tools,
        tool_choice='auto',  # 大模型自己判断是否要调用工具
        temperature=1.0
    )
    # 5.2.1写个变量读取大模型的回复
    assistant_msg = response.choices[0].message

    # ! 此次if下去了就表示大模型需要调用工具 !
    if assistant_msg.tool_calls:
        messages.append(assistant_msg)  # 向历史消息中穿入要调用的信息

        # for -因为大模型可能一次调用多个工具
        for tool_call in assistant_msg.tool_calls:
            # 5.2.2 从这开始为调用函数(weather)做准备
            func_name = tool_call.function.name  # 取出大模型要调用的函数名
            func_args = json.loads(tool_call.function.arguments)  # 取出大模型传的参数
            # print(f"函数:{func_name}, 参数:{func_args}")  # 真正运行时注释掉

            # 5.2.3 匹配函数名
            if func_name == 'get_weather':
                tool_result = get_weather(func_args['city'])
            else:
                tool_result = '未知工具'

            # print(f'工具返回结果:{tool_result}')  # 正式运行时注释

            messages.append({  # 将第一次调用模型时 对工具的使用的结果放入历史消息中
                'role': 'tool',
                'tool_call_id': tool_call.id,
                'content': str(tool_result)
            })

        # 流式输出agent的回答
        # stream_options={'include_usage': True} 让服务端在最后一个 chunk 里带上 usage,
        # 否则流式调用拿不到任何 token 统计
        stream = client.chat.completions.create(
            model='deepseek-v4-flash',
            messages=messages,
            temperature=1,
            stream=True,
            stream_options={'include_usage': True}
        )

        print('CgF:', end='')
        full_answer = ''
        stream_usage = None
        for chunk in stream:
            # 带 usage 的那个 chunk 的 choices 是「空列表」,必须先判空再取 [0],
            # 否则会 IndexError —— 这是开启 include_usage 后最常见的坑
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end='', flush=True)  # 流式的固定格式
                full_answer += chunk.choices[0].delta.content
            if getattr(chunk, 'usage', None):
                stream_usage = chunk.usage
        print()

        # 这一轮实际发生了两次模型调用,两次的 token 都要计入
        report_usage(response.usage)                                  # 第一次:判断是否调工具
        report_usage(stream_usage, user_input, full_answer)           # 第二次:生成回答
        print()  # 使用end='' 后换行符会不起作用 ,用print换行
        messages.append({"role": 'assistant', 'content': full_answer})

    else:
        # 改为流式有2种方法:
        # 1.再调用一次model
        # 2.把第一次调用改为流式 ,这个要大改 ,挺复杂的
        full_answer = assistant_msg.content
        print(f'CgF:{full_answer}')
        report_usage(response.usage, user_input, full_answer)
        messages.append({'role': 'assistant', 'content': full_answer})
'''
因为只有输出的时候为了客户端看得更舒服 ,所以会用到流式输出(需要再次调用model)。
Token 统计已改为读取 API 返回的 usage 字段:
  prompt_tokens 覆盖 system 提示 + 完整历史 + 本轮输入,
  completion_tokens 覆盖模型输出,
因此原来「输出和 system 都没算」的问题已修复。
'''


# 注:content_summary / new_message_list_window 已上移到主循环之前(见「上下文管理工具」),
# 并在循环内通过 MAX_HISTORY_MESSAGES 真正生效。
