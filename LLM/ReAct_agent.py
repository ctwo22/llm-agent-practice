import json
import os
import openai

# ========== 初始化客户端 ==========
client = openai.OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url='https://api.deepseek.com'
)


# ========== 工具函数：模拟数据库查询 ==========
def get_info_on_ballGame(game_name: str):  # 一个类似数据库的地方
    data = [
        {
            "name": "篮球 (Basketball)",
            "description": "两支球队通过投篮得分，比赛分为四节，每节时间因联赛而异。",
            "team_members": 12,
            "players_on_field": 5
        },
        {
            "name": "排球 (Volleyball)",
            "description": "两队隔网对抗，通过击球过网并使其落在对方场地得分。",
            "team_members": 12,
            "players_on_field": 6
        },
        {
            "name": "足球 (Soccer)",
            "description": "两支球队通过踢球进入对方球门得分，比赛分为上下半场。",
            "team_members": 11,
            "players_on_field": 11
        },
        {
            "name": "沙滩排球 (Beach Volleyball)",
            "description": "排球的变种，在沙地上进行，每队人数较少。",
            "team_members": 2,
            "players_on_field": 2
        },
        {
            "name": "网球 (Tennis)",
            "description": "单打或双打比赛，球员用球拍击球过网，使对手无法回击。",
            "team_members": 1,
            "players_on_field": 1
        },
        {
            "name": "棒球 (Baseball)",
            "description": "进攻方击球后跑垒得分，防守方投球并试图使击球手出局。",
            "team_members": 9,
            "players_on_field": 9
        },
        {
            "name": "冰球 (Ice Hockey)",
            "description": "在冰面上进行，球员用球棍击打冰球进入对方球门。",
            "team_members": 20,
            "players_on_field": 6
        },
        {
            "name": "橄榄球 (Rugby)",
            "description": "球员持球奔跑或传球，通过达阵或射门得分。",
            "team_members": 15,
            "players_on_field": 15
        },
        {
            "name": "乒乓球 (Table Tennis)",
            "description": "两名或四名球员在球桌上用球拍击打小球。",
            "team_members": 1,
            "players_on_field": 1
        },
        {
            "name": "羽毛球 (Badminton)",
            "description": "球员用球拍击打羽毛球过网，使对手无法回击。",
            "team_members": 1,
            "players_on_field": 1
        }
    ]
    ret = []  # 存储和输入匹配的对象
    for d in data:
        if game_name.lower() in d['name'].lower():
            ret.append(d)
    return ret


# ========== 工具定义（告诉 AI 有哪些工具可用） =========
tools = [
    {
        'type': 'function',  # 定义的函数工具
        'function': {
            'name': 'get_info_on_ballGame',
            'description': '获取球类比赛的基本信息和人数规模',
            'parameters': {  # 这个'function'的整个参数包
                'type': 'object',  # 参数本质上是 键值对 ,基本永远都是'object'
                'properties': {  # 里面具体有哪些参数
                    'game_name': {
                        'type': 'string',
                        'description': '要查询的球类名称,如篮球,足球,排球等'
                    }
                },
                'required': ['game_name'],  # LLM调用参数时必须提供'required'里的参数
                'additionalProperties': False  # False不允许LLM调用properties里没有的参数
            },
            'strict': True  # 严格校检模式 -严格遵守parameters的定义,否则不能调用
        }
    }
]

# ========== 系统提示词 ==========
# 提示词对于LLM来说只是引导和建议
system_prompt = ''' 
你运行在一个和思考、行动、观察和回答的循环，在循环结束时输出最终的答案。
用“思考:”来描述你对问题的想法。
用“操作:”运行你可用的工具。
“观察:”将是运行这些操作的结果
“答案:"是分析观察结果后得出的最终回答。
'''

# ========== 对话历史（全局维护） ==========
message_history = []  # 设置历史记录 ,并添加提示词
message_history.append({'role': 'system', 'content': system_prompt})


# ========== 调用 AI（直接用历史记录，不再传参)[-这有点方便啊] ==========
def get_completion():
    '''把message_history 发给AI ,拿到回复并追加历史 ,返回回复字典'''
    response = client.chat.completions.create(
        model='deepseek-chat',
        messages=message_history,
        tools=tools,
    )
    # 用 model_dump() 彻底转字典（比 dict() 更可靠，嵌套对象也会转）
    response_dict = response.choices[0].message.model_dump()  # 将LLM的回答转换为字典(dict)形式
    message_history.append(response_dict)
    return response_dict


# ========== Agent 主循环 ===================
def agent(query):
    # 先把用户问题加入历史
    message_history.append({'role': 'user', 'content': query})

    max_turns = 1  # 最多循环10轮 ,防止卡死烧钱
    current_turn = 0

    # 不用while True 原因:这是工程上的*防御性编程*，防止死循环烧钱
    while current_turn < max_turns:
        current_turn += 1
        # 用户问题已经导入历史 -get_completion(调用AI)返回AI对历史问题的回答(包含结合历史的对话)
        # message 是接AI对问题的回答
        message = get_completion()

        if message['content']:
            print(f'思考:{message['content']}')  # 打印AI的文字回复(可能为空 -只调用工具, 不回复)

        if message['tool_calls']:  # 如果LLM的返回里要调用tools,则'tool_calls':True

            for tool_call in message['tool_calls']:
                # 为什么要记这个 id？ 因为你把工具结果还给 AI 时，
                # 必须带上这个 id，AI 才知道 "这条结果是对应哪次调用的"。就像取快递要报取件码一样。
                # model_dump() 后是字典, 用['key'] 取值
                func_call_id = tool_call['id']
                func_name = tool_call['function']['name']  # 嵌套字典获取'name'
                func_kwargs = json.loads(tool_call['function']['arguments'])
                # tool_calls = [
                #     {
                #         'id': 'call_abc123',  # ← 这次工具调用的唯一编号
                #         'function': {
                #             'name': 'get_info_on_ballGame',
                #             'arguments': '{"game_name": "篮球"}'
                #         }
                #     }
                # ]
                # 所以 func_kwargs = {'game_name': '篮球'}

                print(f'操作: 调用{func_name} , 参数:{func_kwargs}')

                # 匹配&执行对应的函数工具(目前只有一个 ,后续可在此扩展)
                if func_name == 'get_info_on_ballGame':
                    func_result = get_info_on_ballGame(**func_kwargs)  # ** : 解包
                else:
                    func_result = f'错误:未知工具{func_name}'

                print(f'观察: {func_result}')  # 这个就是调用工具后LLM返回的

                # 每个工具调用都要添加进历史(让AI知道)
                message_history.append({
                    'role': 'tool',  # 注意是'tool'
                    'tool_call_id': func_call_id,  # 让AI知道(id唯一)
                    'content': json.dumps(func_result, ensure_ascii=False),
                    # 'content' 必须是字符串
                    # ensure_ascii=False：不强制转成 ASCII 码，中文直接显示中文
                    # json.dumps() 比 str 更规范
                })

        else:
            # 在出结果之前会一直调用,出结果后(即不会再调用工具)要给一个可以出去的地方
            print('未调用工具,回答结束')
            break


# ========== 程序入口（连续对话） ==========
if __name__ == '__main__':  # 只有直接运行这个文件时，才执行这里的代码 -运行该文件的'程序入口'
    print('===球类查询助手=== (输入exit/bye/拜) 结束本次查询')
    while True:
        query = input('c:')
        if query in ['exit', 'bye', '拜']:
            print('下次再见咯!')
            break
        if query.strip():
            # strip() :是去掉字符串首尾的空白字符(空格、换行、Tab)
            # 防止用户用 空格/回车 调用AI而浪费额度
            agent(query)
