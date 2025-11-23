bigtransport_prompt = """你是一个专业的约束抽取者，请你判断当前用户请求中是否有对两个城市之间交通工具的选择，只能选择train或者airplane。注意，没有的结果必须为None，而不是null.
参数说明：
"bigtransport_type"表示两个城市之间的交通方式，其存在两个参数分别为"go_must_type"和"back_must_type"。
"go_must_type"表示去程交通方式，输出格式举例："go_must_type" : ['train']。
"back_must_type"表示回程交通方式，输出格式举例："back_must_type" : ['airplane']。
"intercity_cost"表示跨城市交通预算，输出格式举例："intercity_cost" : 900.00。

例如：
输入：我们3人，从重庆出发，到深圳旅行3天，要求满足以下任意一个：1. 跨城市交通的预算为4300.0 2. 在旅行上的总预算为7200.0
输出：{{"bigtransport_type": {
    "go_must_type": None,
    "back_must_type": None
  },, "intercity_cost": 4300.0}}

输入：当前位置上海。我和两个朋友计划去深圳玩两天，选择火车出行，市内交通方式为地铁。请给我一个旅行规划。
输出：{{"bigtransport_type": {
    "go_must_type": "train",
    "back_must_type": "train"
  },, "intercity_cost": None}}

输入：我们4人，从重庆出发，到北京旅行3天，要求满足：必须做飞机前往，回来的交通方式任意。
输出：{{"bigtransport_type": {
    "go_must_type": "airplane",
    "back_must_type": None
  },, "intercity_cost": None}}

输入：我们2人，从杭州出发，到北京旅行3天，要求满足：跨城市交通单次预算为800.0
输出{{"bigtransport_type": {
    "go_must_type": None,
    "back_must_type": None
  }, "intercity_cost": 1600.0}}
解析：单次预算为800.0，也就是往返需要1600.0

输入：我一个人想去广州玩2天，预算2500人民币，坐火车去，住一间单床房，想去北京路步行街和这样的商业街区，请给我一个旅行规划。
输出：{{"bigtransport_type": {
    "go_must_type": "train",
    "back_must_type": "train"
  }, "intercity_cost": 2000.0}}
解析：这里的预算是指总预算，所以跨城市交通的预算应该要比总预算要低，大概为80%，即2000.0。

输入：我们2人，从广州出发，到重庆旅行2天，要求如下：预算4000人民币，住一间大床房，坐飞机去，想去洪崖洞看一下
输出：{{"bigtransport_type": {
    "go_must_type": "airplane",
    "back_must_type": "airplane"
    }, "intercity_cost": 3200.0}}
解析：这里的预算是指总预算，所以跨城市交通的预算应该要比总预算要低，大概为80%，即3200.0。"""

class TRANSPORT_INSTRUCTION:
    def __init__(self):
        pass

    @classmethod
    def format(cls, nature_language):
        return (
            bigtransport_prompt
            + "\n我的输入为: "
            + str(nature_language)
            + "\n"
            + "\n请你直接输出JSON格式，注意这里说的是跨城市出行预算，而不是城市内出行预算。"
        )

rewrite_request_prompts = """
我会给你我的用户请求，当我说的是“要求满足以下任意一个”，也就意味着我想要满足任意一个约束时，请你给我删除一个约束。当我说的是“要求如下”，也就是我想要全部约束时，请原模原样返回。

示例：
输入：我们4人，从南京出发，到重庆旅行3天，要求如下：不希望以walk 和 taxi方式在城市内出行在城市内出行的预算为140
输出：我们4人，从南京出发，到重庆旅行3天，要求如下：不希望以walk 和 taxi方式在城市内出行在城市内出行的预算为140

输入：我们2人，从武汉出发，到深圳旅行5天，要求如下：在用餐上的预算为2100.0在住宿上的预算为9600.0
输出：我们2人，从武汉出发，到深圳旅行5天，要求如下：在用餐上的预算为2100.0在住宿上的预算为9600.0

输入：我们3人，从上海出发，到深圳旅行4天，要求满足以下任意一个：1. 希望游览历史古迹2. 希望不早于14:00离开深圳华润大厦艺术中心
输出：我们3人，从上海出发，到深圳旅行4天，要求如下：希望不早于14:00离开深圳华润大厦艺术中心

输入：我们4人，从苏州出发，到杭州旅行4天，要求满足以下任意一个：1. 在游览上的预算为1100.02. 希望入住单床房
输出：我们4人，从苏州出发，到杭州旅行4天，要求如下：希望入住单床房

输入：我们3人，从苏州出发，到深圳旅行2天，要求满足以下任意一个：1. 不希望以walk 和 taxi方式在城市内出行2. 在旅行上的总预算为5200.0
输出：我们3人，从苏州出发，到深圳旅行2天，要求满足以下任意一个：不希望以walk 和 taxi方式在城市内出行

解释：请你删除相对困难实现的约束，例如历史古迹景点会相对较少，因此删除该约束。
注意：“要求如下”表示你不能删除约束，“要求满足以下任意一个“表示可以删除约束。不要输出解释。在只需要满足任意一个的时候，尽量少选择城市内出行预算，除非他非常简单，容易满足。"""
class REWRITE_REQUEST:
    def __init__(self):
        pass

    @classmethod
    def format(cls, plan):
        return (
            rewrite_request_prompts
            + "\n我的用户请求为: "
            + str(plan)
            + "\n"
            + "\n请你直接修改之后的用户请求"
        )
init_prompt ="""
请你根据自然语言输出出发城市，到达城市，旅行人数，旅行天数，城市内出行方式 (出行方式只有"taxi", "walk", "metro")。不要自动输出其他内容。
参数说明："start_city"表示出发城市，输出格式举例："start_city": "成都"。
"target_city"表示到达城市，输出格式举例："target_city": "上海"。
"days"表示旅行天数，输出格式举例："days": 3。
"people_number"表示旅行人数，输出格式举例："people_number": 2。
"must_inner_city_transportation"表示城市内出行方式，输出格式举例："must_inner_city_transportation": ["metro", "walk"]。如果没有指定城市内出行方式，则输出空列表[]。
"total_cost"表示总预算，输出格式举例："total_cost": 3600.0。

示例：
输入：我们3人，从成都出发，到上海旅行3天，要求如下：\n不希望游览淀山湖风景区 和 田子坊石库门。
输出：{{"start_city": "成都",
    "target_city": "上海",
    "days": 3,
    "people_number": 3,
    "must_inner_city_transportation": [],
    "total_cost": None}}

输入：我们2人，从重庆出发，到杭州旅行3天，要求如下：\n希望游览西溪天堂商业街。
输出：{{"start_city": "重庆",
    "target_city": "杭州",
    "days": 3,
    "people_number": 2,
    "must_inner_city_transportation": [],
    "total_cost": None}}
    
输入：我们4人，从南京出发，到重庆旅行3天，要求如下：不希望以walk 和 taxi方式在城市内出行在城市内出行的预算为140
输出：{{"start_city": "南京",
    "target_city": "重庆",
    "days": 3,
    "people_number": 4,
    "must_inner_city_transportation": ["metro"],
    "total_cost": None}}
    
输入：我们1人，从北京出发，到深圳旅行3天，要求如下：在旅行上的总预算为3600.0希望入住单床房
输出：{{"start_city": "北京",
    "target_city": "深圳",
    "days": 3,
    "people_number": 1,
    "must_inner_city_transportation": [],
    "total_cost": 3600.0}}

输入：我们1人，从深圳出发，到上海旅行2天，要求如下：在旅行上的总预算为3000.0，若两地点间交通距离超过9.540000000000001千米，则打车出行
输出：{{"start_city": '深圳', 
    "target_city": '上海', 
    "days": 2, 
    "people_number": 1, 
    "must_inner_city_transportation": ["taxi"], 
    "total_cost": 3000.0}}

输入：我们4人，从苏州出发，到北京旅行2天，要求如下：1. 希望乘坐train前往目的地，乘坐train返回 2.跨城市交通的预算为5400.0
输出：{{"start_city": '苏州', 
    "target_city": '背景', 
    "days": 2, 
    "people_number": 4, 
    "must_inner_city_transportation": [], 
    "total_cost": None}}
请注意total_cost应该输出的是总预算，而不是餐饮预算，游览预算，酒店预算，跨城市交通预算或者城市内交通预算。"""

class INIT_INSTRUCTION:
    def __init__(self):
        pass
    @classmethod
    def format(cls, nature_language):
        return (
            init_prompt
            + "\n我的输入为: "
            + str(nature_language)
            + "\n"
            + "\n请你直接输出JSON格式"
        )
attractions_draw_prompts = """你是一个专业的约束抽取者，请你提取出用户请求中是否包含希望游览景点类型和具体景点。
请注意，大部分城市中，你必须在这12种类型中选择，['人文景观', '公园', '其它', '博物馆/纪念馆', '历史古迹', '商业街区', '大学校园', '文化旅游区', '游乐园/体育娱乐', '红色景点', '美术馆/艺术馆', '自然风光']
但是在重庆中，没有"其他"和"大学校园"，而在深圳中，没有"其他"，但是有"图书馆/纪念馆"。
请注意，除了这些类型，不要输出其他类型，或者相似类型。
参数说明：
"must_attraction_type"表示的是用户明确说想去的景点类型，输出格式举例："must_attraction_type" : ['历史古迹', '公园']。
"must_not_attraction_type"表示的是用户明确说不想去的景点类型，输出格式举例："must_not_attraction_type" : ['游乐园/体育娱乐']。
"attraction_cost"表示的是用户在景点上的预算，输出格式举例："attraction_cost" : 300.00。
"must_attraction_name"表示的是用户明确说想去的景点，输出格式举例："must_attraction_name" : ['故宫博物院', '天安门广场']。
"must_not_attraction_name"表示的是用户明确说不想去的景点，输出格式举例："must_not_attraction_name" : ['颐和园']。

示例：
输入：希望游览文化旅游区 和 美术馆/艺术馆，希望只游览免费景点
输出：{{"must_attraction_type":["文化", "美术馆", "艺术馆"], "must_not_attraction_type":[], "attraction_cost": 0.00, "must_attraction_name": [], "must_not_attraction_name": []}}
解释：用户说想要游玩免费景点，所以景点预算为0.00。

输入：[当前位置南京,目标位置北京,旅行人数2,旅行天数4] 坐标南京，两个人想去北京玩四天，必须高铁(G)往返，想看天安门升旗，参观故宫圆明园天坛，并爬长城，要吃到北京烤鸭、豆汁等特色美食，酒店价格不能超过450一晚，可以帮我做一个行程规划吗？预算4000
输出：{{"must_attraction_type":[], "must_not_attraction_type":[], "attraction_cost": None, "must_attraction_name": ["八达岭长城", "天安门广场", "故宫博物院", "圆明园", "天坛"], "must_not_attraction_name": []}}

输入：要求如下：不希望游览历史古迹 和 红色景点 和 游乐园/体育娱乐, 在用餐上的预算为3900.0
输出：{{"must_attraction_type":[], "must_not_attraction_type":["历史古迹", "红色景点", "体育娱乐", "游乐场"], "attraction_cost": None, "must_attraction_name": [], "must_not_attraction_name": []}}

输入：在游览上的预算为200，不希望入住以下类型的酒店免费停车。
输出：{{"must_attraction_type":[], "must_not_attraction_type":[], "attraction_cost": 200.0, "must_attraction_name": [], "must_not_attraction_name": []}}

输入：我们4人，从苏州出发，到杭州旅行4天，要求如下：希望游览历史古迹, 希望在08:10到09:40之间游览保俶塔。
输出：{{"must_attraction_type":["历史古迹"], "must_not_attraction_type":[], "attraction_cost": None, "must_attraction_name": ["保俶塔"], "must_not_attraction_name": []}}

输入：要求如下：希望游览大源中央公园，希望入住以下酒店和光·Alienspace外星人智慧电竞酒店(成都太古里春熙路旗舰店)。
输出：{{"must_attraction_type":[], "must_not_attraction_type":[], "attraction_cost": None, "must_attraction_name": ["大源中央公园"], "must_not_attraction_name": []}}

输入：[当前位置南京,目标位置成都,旅行人数5,旅行天数4] 我们一家五口打算去成都看熊猫，打算坐动车往返，顺带在附近的著名景点玩一下。请帮我们规划一下行程，预算不要超过2万。
输出：{{"must_attraction_type":[], "must_not_attraction_type":[], "attraction_cost": 20000.0, "must_attraction_name": ["成都大熊猫繁育研究基地"], "must_not_attraction_name": []}}

输入：[当前位置南京,目标位置上海,旅行人数2,旅行天数3] 我想从北京出发去上海游玩3天左右，本人对于乐器店感兴趣，想要多逛一些钢琴乐器店，并且去游乐园游玩，预算2000元左右。
输出：{{"must_attraction_type":["游乐园/体育娱乐", "商业街区"], "must_not_attraction_type":[], "attraction_cost": 2000.0, "must_attraction_name": [], "must_not_attraction_name": []}}

输入：[当前位置成都,目标位置重庆,旅行人数2,旅行天数2] 我要和男朋友从成都出发去重庆过周末，想要吃重庆有名的好吃的火锅，再去看看历史文化或者风景名胜，最好凉快一点。请给我一个旅行规划
输出：{{"must_attraction_type":["历史古迹", "自然风光", "文化旅游区"], "must_not_attraction_type":[], "attraction_cost": None, "must_attraction_name": [], "must_not_attraction_name": []}}

请注意，你需要检查必去必不去的应该是景点，而不是餐厅。只输出景点相关内容。
!!!不要包含任何未提及的约束。不要包含任何输出中不存在的约束类型。
请注意，当用户请求为“免费景点”时，budget设置为0.00。如果没有涉及景点类型，景点名称或景点预算，则都设置为None。
"""

class ATTRACTIONS_DRAW:
    def __init__(self):
        pass

    @classmethod
    def format(cls, nature_language):
        return (
            attractions_draw_prompts
            + "\n我的输入为: "
            + str(nature_language)
            + "\n"
            + "\n请你直接输出JSON格式"
        )

restaurants_draw_prompts = """
请你提取出用户请求中是否包含希望去某个餐饮类型和具体餐饮。请注意，你必须在这些类型中选择，以下为分城市结果：
北京：['东北菜', '东南亚菜', '云南菜', '其他', '其他中餐', '农家菜', '创意菜', '北京菜', '咖啡店', '小吃', '川菜', '徽菜', '快餐简餐', '新疆菜', '日本料理', '本帮菜', '江浙菜', '海鲜', '清真菜', '湘菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理', '鲁菜']
成都：['东南亚菜', '中东料理', '其他', '其他中餐', '创意菜', '北京菜', '咖啡店', '小吃', '川菜', '快餐简餐', '新疆菜', '日本料理', '江浙菜', '海鲜', '清真菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '茶馆/茶室', '融合菜', '西藏菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理']
重庆：['东南亚菜', '其他中餐', '创意菜', '北京菜', '咖啡店', '小吃', '川菜', '快餐简餐', '新疆菜', '日本料理', '火锅', '烧烤', '粤菜', '素食', '自助餐', '茶馆/茶室', '融合菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理']
广州：['东北菜', '东南亚菜', '亚洲菜', '其他', '其他中餐', '创意菜', '咖啡店', '客家菜', '小吃', '川菜', '快餐简餐', '日本料理', '江浙菜', '海南菜', '海鲜', '湘菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理', '鲁菜']
杭州：['东北菜', '东南亚菜', '其他中餐', '农家菜', '创意菜', '台湾菜', '咖啡店', '小吃', '川菜', '徽菜', '快餐简餐', '新疆菜', '日本料理', '本帮菜', '江浙菜', '海鲜', '湘菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '茶馆/茶室', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理']
南京：['东南亚菜', '云南菜', '其他中餐', '创意菜', '北京菜', '咖啡店', '小吃', '川菜', '徽菜', '快餐简餐', '新疆菜', '日本料理', '本帮菜', '江浙菜', '海鲜', '清真菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理']
上海：['东南亚菜', '中东料理', '云南菜', '其他', '农家菜', '创意菜', '北京菜', '台湾菜', '咖啡店', '小吃', '川菜', '徽菜', '快餐简餐', '拉美料理', '新疆菜', '日本料理', '本帮菜', '江浙菜', '海鲜', '清真菜', '湖北菜', '湘菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '闽菜', '面包甜点', '韩国料理', '鲁菜']
深圳：['东北菜', '东南亚菜', '云南菜', '亚洲菜', '农家菜', '创意菜', '北京菜', '咖啡店', '客家菜', '小吃', '川菜', '快餐简餐', '拉美料理', '新疆菜', '日本料理', '本帮菜', '江浙菜', '海鲜', '湘菜', '火锅', '烧烤', '粤菜', '素食', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '闽菜', '面包甜点', '韩国料理', '鲁菜']
武汉：['东南亚菜', '云南菜', '其他', '其他中餐', '创意菜', '北京菜', '咖啡店', '小吃', '川菜', '快餐简餐', '日本料理', '江浙菜', '海鲜', '湖北菜', '湘菜', '火锅', '烧烤', '粤菜', '自助餐', '融合菜', '西北菜', '西餐', '酒吧/酒馆', '面包甜点', '韩国料理']
除了这些类型，不要输出其他类型，或者相似类型。
参数说明："must_restaurant_type"表示用户明确说想去的餐饮类型，输出格式举例："must_restaurant_type" : ['川菜', '粤菜']。
"must_not_restaurant_type"表示用户明确说不想去的餐饮类型，输出格式举例："must_not_restaurant_type" : ['火锅']。
"restaurant_cost"表示用户在餐饮上的预算，输出格式举例："restaurant_cost" : 300.00。
"must_restaurant_name"表示用户明确说想去的餐饮，输出格式举例："must_restaurant_name" : ['真地道京味府·鲜橙烤鸭(西单店)', '悦·中餐厅']。
"must_not_restaurant_name"表示用户明确说不想去的餐饮，输出格式举例："must_not_restaurant_name" : ['Ministry of Crab·MOC Restaurant']。
"restaurant_stay_time"表示用户在餐饮停留时间，输出格式举例："restaurant_stay_time" : {"must_restaurant_name": "真地道京味府·鲜橙烤鸭(西单店)", "time": 60, "arrival": None, "depature": None}。其中"must_restaurant_name"表示餐饮名称，"time"表示停留时间，"arrival"表示到达时间，"depature"表示离开时间。

示例：
输入：输入：当前位置深圳。我三个人想去北京玩2天，要求如下：坐火车去\n预算为7600.0\n希望游览历史古迹\n希望入住一间家庭大床房\n市内出行方式走路 和 地铁\n人均每顿别超过70元
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 1260.0, "must_restaurant_name": [], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}

输入：要求如下：1. 不希望尝试以下餐厅：Ministry of Crab·MOC Restaurant 2.在住宿上的预算为800.0
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": [], "must_not_restaurant_name": ['Ministry of Crab·MOC Restaurant'], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}

输入：1. 不希望尝试以下类型的餐厅中东料理 和 韩国料理 和 清真菜 2. 在旅行上的总预算为20200.0
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":["中东料理", "韩国料理", "清真菜"], "restaurant_cost": 0.00, "must_restaurant_name": [], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}

输入：1. 不希望以metro方式在城市内出行 2.希望在真地道京味府·鲜橙烤鸭(西单店)停留不少于60分钟
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": ["真地道京味府·鲜橙烤鸭(西单店)"], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": 真地道京味府·鲜橙烤鸭(西单店), "time": 60, "arrival": None, "depature": None}}}

输入：[当前位置南京,目标位置北京,旅行人数2,旅行天数4] 坐标南京，两个人想去北京玩四天，必须高铁(G)往返，想看天安门升旗，参观故宫圆明园天坛，并爬长城，要吃到北京烤鸭、豆汁等特色美食，酒店价格不能超过450一晚，可以帮我做一个行程规划吗预算4000
输出：{{"must_restaurant_type":["北京菜"], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": [], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": , "time": 60, "arrival": None, "depature": None}}}

输入：要求如下：1.不希望以taxi方式在城市内出行  2.希望不晚于11:00到达重庆高老九火锅(苏州中心店)
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": ["重庆高老九火锅(苏州中心店)"], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": 重庆高老九火锅(苏州中心店), "time": None, "arrival": 11:00, "depature": None}}}

输入：要求如下：1.不希望以taxi方式在城市内出行  2.希望在17:00到17:50之间游览悦·中餐厅
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": ["悦·中餐厅"], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": 悦·中餐厅, "time": None, "arrival": 17:00, "depature": 17:50}}}

输入：我们2人想去武汉玩3天，主要想体验武汉的一些有些历史的区域，同时还想尝一尝本地人常去吃的特色美食，怎么规划行程
输出：{{"must_restaurant_type":["湖北菜"], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": [], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}

输入：当前位置广州。我们三个人计划去重庆玩三天，预算5200元，想吃粤菜，开两间双床房。请给我一个旅行规划。
输出：{{"must_restaurant_type":["粤菜"], "avoidrestaurantstype":[], "restaurant_cost": 5200.0, "must_restaurant_name": [], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}

输入：当前位置南京。我们三个人想去重庆玩2天，想吃解放碑附近的锅碗瓢盆·重庆本土菜，请给我们一个旅行规划。
输出：{{"must_restaurant_type":[], "must_not_restaurant_type":[], "restaurant_cost": 0.00, "must_restaurant_name": ["锅碗瓢盆·重庆本土菜(解放碑店)"], "must_not_restaurant_name": [], "restaurant_stay_time": {"must_restaurant_name": None, "time": None, "arrival": None, "depature": None}}}
请注意：当用户说明要去xx附近的xx餐厅时，你需要提取餐厅名称，并需要提取附近的地点，例如"锅碗瓢盆·重庆本土菜(解放碑店)"。

注意："stop_time"表示用户在该餐饮停留时间。stop_time中添加应该是存在需要在某个餐厅中停留，例如17:00到17:50，或者停留60分钟。如果没有停留时间，只是需要去该餐厅，不要在stop_time中输出内容。
!!!不要包含任何未提及的约束。不要包含任何输出中不存在的约束类型，比如avoidattraction等，你只需要提取餐厅相关的约束，type是餐厅的type，不要提取景点或酒店的type
注意：如果给出人均每顿价格，则需要计算总餐饮预算为人数*天数*人均*3
"""

class RESTAURANTS_DRAW:
    def __init__(self):
        pass

    @classmethod
    def format(cls, nature_language):
        return (
            restaurants_draw_prompts
            + "\n我的输入为: "
            + str(nature_language)
            + "\n"
            + "\n请你直接输出JSON格式"
        )

hotels_draw_prompts = """你是一个专业的约束抽取者，请你提取出用户请求中是否包含希望游览景点类型和具体景点。请注意，你必须在这些类型中选择。
北京：['SPA', '亲子主题房', '会议厅', '停车场', '健身室', '儿童乐园', '充电桩', '免费停车', '动人夜景', '四合院', '多功能厅', '套房', '家庭房', '山景房', '影音房', '拍照出片', '提前入园', '日光浴场', '智能客控', '机器人服务', '桌球室', '桑拿', '棋牌室', '江河景房', '泳池', '洗衣房', '洗衣服务', '温泉', '湖景房', '私人泳池', '窗外好景', '管家服务', '网红泳池', '美食酒店', '自营亲子房', '茶室', '行政酒廊', '行李寄存', '设计师酒店', '酒店公寓']
成都：['24小时前台', 'Boss推荐', 'SPA', '亲子主题房', '停车场', '健身室', '儿童乐园', '儿童俱乐部', '充电桩', '免费停车', '动人夜景', '多功能厅', '家庭房', '山景房', '影音房', '情侣房', '日光浴场', '智能客控', '智能马桶', '机器人服务', '桑拿', '棋牌室', '民宿', '江河景房', '泳池', '湖景房', '私人泳池', '私汤房', '空气净化器', '窗外好景', '管家服务', '网红泳池', '自营亲子房', '茶室', '行政酒廊', '酒店公寓']
重庆：['24小时前台', 'Boss推荐', 'SPA', '停车场', '健身室', '儿童乐园', '儿童俱乐部', '充电桩', '免费停车', '动人夜景', '商务中心', '多功能厅', '家庭房', '山景房', '影音房', '情侣房', '拍照出片', '智能客控', '智能马桶', '机器人服务', '桑拿', '棋牌室', '民宿', '江河景房', '泳池', '洗衣房', '洗衣机', '温泉泡汤', '湖景房', '电竞房', '私人泳池', '空调', '穿梭机场班车', '窗外好景', '管家服务', '茶室', '行政酒廊', '设计师酒店', '酒店公寓']
广州：['Boss推荐', 'SPA', '亲子主题房', '会议厅', '停车场', '健身室', '儿童乐园', '充电桩', '免费停车', '别墅', '动人夜景', '多功能厅', '家庭房', '小而美', '山景房', '影音房', '日光浴场', '智能客控', '智能马桶', '机器人服务', '桑拿', '民宿', '江河景房', '泳池', '洗衣房', '湖景房', '私人泳池', '私汤房', '窗外好景', '管家服务', '网红泳池', '自营亲子房', '行政酒廊', '设计师酒店', '酒店公寓']
杭州：['24小时前台', 'SPA', '中式庭院', '亲子主题房', '会议厅', '停车场', '健身室', '充电桩', '免费停车', '别墅', '动人夜景', '历史名宅', '园林建筑', '多功能厅', '客栈', '家庭房', '小而美', '山景房', '影音房', '日光浴场', '智能马桶', '机器人服务', '桑拿', '民宿', '江河景房', '泳池', '洗衣房', '洗衣机', '湖景房', '湖畔美居', '电竞房', '私人泳池', '空调', '窗外好景', '管家服务', '网红泳池', '茶室', '行政酒廊', '设计师酒店', '酒店公寓', '钓鱼']
南京：['24小时前台', 'Boss推荐', 'SPA', '亲子主题房', '会议厅', '停车场', '健身室', '儿童乐园', '充电桩', '免费停车', '别墅', '动人夜景', '多功能厅', '客栈', '家庭房', '山景房', '影音房', '日光浴场', '机器人服务', '桑拿', '棋牌室', '民宿', '江河景房', '泳池', '温泉泡汤', '湖景房', '湖畔美居', '特色住宿', '电竞房', '电竞酒店', '空气净化器', '空调', '窗外好景', '管家服务', '自营影音房', '酒店公寓']
上海：['24小时前台', 'Boss推荐', 'SPA', '亲子主题房', '会议厅', '停车场', '健身室', '儿童乐园', '充电桩', '免费停车', '别墅', '动人夜景', '历史名宅', '商务中心', '多功能厅', '客栈', '家庭房', '影音房', '拍照出片', '日光浴场', '智能客控', '机器人服务', '桑拿', '棋牌室', '民宿', '江河景房', '泳池', '洗衣房', '湖景房', '特色住宿', '私人泳池', '空调', '窗外好景', '管家服务', '网红泳池', '老洋房', '行政酒廊', '设计师酒店', '酒店公寓']
深圳：['24小时前台', 'SPA', '亲子主题房', '停车场', '健身室', '儿童俱乐部', '充电桩', '免费停车', '动人夜景', '厨房', '多功能厅', '家庭房', '山景房', '影音房', '情侣房', '拍照出片', '日光浴场', '智能客控', '机器人服务', '桑拿', '棋牌室', '泳池', '海景房', '湖景房', '私人泳池', '窗外好景', '管家服务', '网红泳池', '自营亲子房', '自营影音房', '茶室', '行政酒廊', '设计师酒店', '迷人海景', '酒店公寓']
武汉：['24小时前台', 'SPA', '位置超好', '停车场', '儿童乐园', '儿童泳池', '充电桩', '免费停车', '多功能厅', '宠物友好', '家庭房', '小而美', '山景房', '影音房', '情侣房', '日光浴场', '智能客控', '机器人服务', '桑拿', '棋牌室', '民宿', '江河景房', '泳池', '洗衣房', '湖景房', '湖畔美居', '电竞房', '空气净化器', '空调', '穿梭机场班车', '窗外好景', '管家服务', '网红泳池', '自营亲子房', '自营舒睡房', '茶室', '行政酒廊', '酒店公寓']
除了这些类型，不要输出其他类型，或者相似类型。
参数说明："must_accommodation_type"表示用户明确说想去的酒店类型，输出格式举例："must_accommodation_type" : ['家庭房', 'SPA']。
"must_not_accommodation_type"表示用户明确说不想去的酒店类型，输出格式举例："must_not_accommodation_type" : ['免费停车']。
"accommodation_cost"表示用户在酒店上的预算，输出格式举例："accommodation_cost" : 300.00。
"must_accommodation_name"表示用户明确说想去的酒店，输出格式举例："must_accommodation_name" : ['北京四季酒店', '上海浦东丽思卡尔顿酒店']。
"must_not_accommodation_name"表示用户明确说不想去的酒店，输出格式举例："must_not_accommodation_name" : ['北京四季酒店', '上海浦东丽思卡尔顿酒店']。
"nearby_attractions"表示用户明确说想去的景点，输出格式举例："nearby_attractions" : {"name": "天安门广场", "distance": 2.0}。其中"name"表示景点名称，"distance"表示距离酒店的距离，单位为千米。
"count"表示用户明确表明想要住几间房，输出格式举例："count" : 1
"numbed"表示用户明确表明想要住几张床，输出格式举例："numbed" : 2
"avgbudget"表示用户明确表明每晚预算，输出格式举例："avgbudget": 200.0

示例：
输入：我们1人，从北京出发，到深圳旅行3天，要求满足以下任意一个：1. 希望入住以下类型的酒店停车场2. 在旅行上的总预算为4300.0
输出：{{"must_accommodation_type":["停车场"], "must_not_accommodation_type":[], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": None}}

输入：我们5人，从南京出发，到苏州旅行3天，要求满足以下任意一个：1. 希望入住以下类型的酒店之一免费停车2. 在住宿上的预算为3300.0
输出：{{"must_accommodation_type":["免费停车"], "must_not_accommodation_type":[], "accommodation_cost": 3300.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": None}}

输入：我们1人，从深圳出发，到上海旅行2天，要求如下：1. 希望尝试以下类型的餐厅之一粤菜 或 海鲜 或 火锅 2. 希望住宿地在徐家汇书院周围4.1千米内
输出：{{"must_accommodation_type":[], "must_not_accommodation_type":[], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {"name": "徐家汇书院", "distance": 4.1}, "numbed": None, "count": None, "avgbudget": None}}

输入：1. 若两地点间交通距离超过4.3829073106507215千米，则打车出行 2. 希望入住单床房
输出：{{"must_accommodation_type":[], "must_not_accommodation_type":[], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": 1, "count": None, "avgbudget": None}}

输入：当前位置成都。我和我的家人想去广州玩3天，住一间家庭房，请给我一个旅行规划。
输出：{{"must_accommodation_type":['家庭房'], "must_not_accommodation_type":[], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": 2, "count": None, "avgbudget": None}}

输入：我们3人，从上海出发，到深圳旅行4天，要求满足以下任意一个：1. 希望游览历史古迹 2. 希望不早于14:00离开深圳华润大厦艺术中心
输出：{{'must_accommodation_type': [], 'must_not_accommodation_type': [], 'accommodation_cost': 50000.0, 'must_accommodation_name': [], 'must_not_accommodation_name': [], 'nearby_attractions': {}, 'numbed': None, "count": None, "avgbudget": None}}

输入：我们1人，从深圳出发，到上海旅行2天，要求如下：1. 希望入住以下类型的酒店之一管家服务 2.希望住宿地在观光夜市(威尼斯水城之夜)周围28.6千米内
输出：{{'must_accommodation_type': ["管家服务"], 'must_not_accommodation_type': [], 'accommodation_cost': 50000.0, 'must_accommodation_name': [], 'must_not_accommodation_name': [], 'nearby_attractions': {'name': '观光夜市(威尼斯水城之夜)', 'distance': 28.6}, 'numbed': None, "count": None, "avgbudget": None}}

输入：我们1人，从北京出发，到深圳旅行3天，要求如下：1. 不希望入住以下酒店深圳福田皇岗口岸秋果酒店 和 深圳摩登克斯酒店， 2.希望在滨海文化公园停留不少于90分钟
输出：{{'must_accommodation_type': [], 'must_not_accommodation_type': [], 'accommodation_cost': 50000.0, 'must_accommodation_name': [], 'must_not_accommodation_name': ["深圳福田皇岗口岸秋果酒店", "深圳摩登克斯酒店"], 'nearby_attractions': {}, 'numbed': None, "count": None, "avgbudget": None}}

输入：我们4人，从成都出发，到深圳旅行5天，要求如下：希望入住以下类型的酒店自营影音房
输出：{{'must_accommodation_type': ["自营影音房"], 'must_not_accommodation_type': [], 'accommodation_cost': 50000.0, 'must_accommodation_name': [], 'must_not_accommodation_name': [], 'nearby_attractions': {}, 'numbed': None, "count": None, "avgbudget": None}}
解释：请注意，“滨海文化公园”中并没有说明和住宿地的关系，不要在nearby_attractions中输出任何内容。

输入：当前位置广州。我两个人想去重庆玩2天，预算4000人民币，住一间大床房，坐飞机去，想去洪崖洞看一下，请给我一个旅行规划。
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": 2, "count": 1, "avgbudget": None}}

输入：我们3人，从杭州出发，到南京旅行3天，预算4000元，要求如下：想去商业街区，开一间单床房
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": 1, "avgbudget": None}}

输入：我目前在成都，计划独自前往南京游玩两天，酒店选择南京南站旁玺悦·弘酒店，请帮我制定一个旅行计划。
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 50000.0, "must_accommodation_name": ["玺悦·弘酒店(南京南站店)"], "must_not_accommodation_name": [], "nearby_attractions": {'name': '南京南站', 'distance': 28.6}, "numbed": None, "count": None, "avgbudget": None}}

输入：输入：当前位置南京，我一个人想去北京玩三天，要求如下：预算为2500.0\n酒店价格不能超过¥200一晚
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 400.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": 200.0}}
说明：这里说酒店价格不能超过200一晚，一人共两晚，因此为200*2=400，因此预算为400.0.

输入：当前位置上海。我们三个人想去广州玩3天，住雅致酒店，在珠江新城广州塔附近，请给我们一个旅行规划。
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 50000.0, "must_accommodation_name": ["雅致酒店(珠江新城广州塔店)"], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": None}}

输入：当前位置北京。我们四个人想去广州玩3天，住美豪丽致酒店，在广州天河金融城附近，请给我们一个旅行规划。
输出：{{"must_accommodation_type": [], "must_not_accommodation_type": [], "accommodation_cost": 50000.0, "must_accommodation_name": ["美豪丽致酒店(广州天河金融城店)"], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": None}}
请注意：当用户说明xx酒店需要在xx附近时，你需要提取酒店名称，并需要提取附近的地点，例如"美豪丽致酒店(广州天河金融城店)"。

解释说明："numbed"表示的是用户想要住几人间，注意“家庭房”表示的是类型，不是几人间。
请你注意的是有三个人并不意味着要住3间房，只有用户明确说明住单床房或者双床房等，numbed才有值；"希望不早于14:00离开深圳华润大厦艺术中心"里面并没有说明住宿地需要在该景点旁边，只是需要访问，nearby_attractions
必须是住宿地离景点等距离，而不是时间或者其他内容，不要随便推测。请注意"免费停车"和“停车场”是两个不同的类型。
注意：只有住宿的预算才修改budget，其他预算，例如游览、总预算等不属于住宿预算，budget设置为50000.0。
希望入住以下酒店之一茶·醒香山房 或 杭州安朴酒店'，表示只需要满足其中的某一家就可以，因此你在'hotels': []随机输出一家。
请注意，用户请求输入的“住一间xxx的房子“的意思就是所有人住一间房，所以numbed需要按照人数来设置，而不是每个人都住一间房。
请注意，count表明用户想要住几间房间，例如住一间大床房，则count为1，住两间单床房，则count为2
!!!不要包含任何未提及的约束。不要包含任何输出中不存在的约束类型，比如avoidattraction等，你只需要提取酒店相关的约束，type是酒店的type，不要提取景点或餐饮的type
"""

class HOTEL_DRAW:
    def __init__(self):
        pass

    @classmethod
    def format(cls, nature_language):
        return (
            hotels_draw_prompts
            + "\n我的输入为: "
            + str(nature_language)
            + "\n"
            + "\n请你直接输出JSON格式"
        )