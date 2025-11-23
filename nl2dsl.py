# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import ast
from tqdm import tqdm
from copy import deepcopy

project_root_path = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
if os.path.join(project_root_path, "chinatravel") not in sys.path:
    sys.path.insert(0, os.path.join(project_root_path, "chinatravel"))

from chinatravel.agent.llms import Llama


nl_constraint_prompt = (
    """
你是一个约束提取器。请尝试理解输入的要求，并从中提取出自然语言的逻辑约束。
除了 "start_city" (出发城市), "target_city" (目标城市), "people_number" (人数) 和 "days" (天数) 之外，
还存在关于以下内容的约束：
{"total_cost" (总预算), "intercity_cost" (城际交通预算), "accommodation_cost" (住宿预算), "restaurant_cost" (餐饮预算), "attraction_cost" (景点预算), "inner_city_cost" (市内交通预算),
"go_must_type" (去程偏好交通工具), "go_must_not_type" (去程排除交通工具), "back_must_type" (返程偏好交通工具), "back_must_not_type" (返程排除交通工具),
"must_not_accommodation_name" (排除酒店名称), "must_not_accommodation_type" (排除住宿类型), "must_accommodation_name" (必选酒店名称), "must_accommodation_type" (必选住宿类型),
"must_not_restaurant_type" (排除餐厅类型), "must_restaurant_type" (必选餐厅类型), "must_not_restaurant_name" (排除餐厅名称), "must_restaurant_name" (必选餐厅名称),
"must_restaurant_type_any" (必选餐厅类型之一), "must_restaurant_name_any" (必选餐厅名称之一),
"must_not_attraction_name" (排除景点名称), "must_attraction_name" (必选景点名称), "must_not_attraction_type" (排除景点类型), "must_attraction_type" (必选景点类型),
"must_inner_city_transportation" (必选市内交通方式), "must_not_inner_city_transportation" (排除市内交通方式),
"activate_start_time" (活动最早开始时间),  "activate_end_time" (活动最晚到达时间), 
"attraction_between" (景点访问时段), "attraction_stay_time" (景点停留时间), "restaurant_stay_time" (餐厅停留时间)
"distance_transport" (距离触发交通方式),
"must_room_type" (必选房间类型), "must_not_room_type" (排除房间类型), "distance_hotel" (酒店距景点最大距离),
"attraction_seq" (景点游览顺序), "must_accommodation_name_any" (必选酒店名称之一), "must_accommodation_type_any" (必选住宿类型之一), "must_attraction_name_any" (必选景点名称之一), "must_attraction_type_any" (必选景点类型之一)}

!!! 每个约束必须严格按照字典中定义的键值对格式。

起始城市和目标城市：['北京','南京','上海','杭州','深圳','武汉','广州','成都','重庆','苏州']
!!! 约束类型相关的内容必须从下面的列表中选择。

请注意，大部分城市中的景点类型，你必须在这12种类型中选择，['人文景观', '公园', '其它', '博物馆/纪念馆', '历史古迹', '商业街区', '大学校园', '文化旅游区', '游乐园/体育娱乐', '红色景点', '美术馆/艺术馆', '自然风光']
但是在重庆中，没有"其他"和"大学校园"，而在深圳中，没有"其他"，但是有"图书馆/纪念馆"。
请注意，除了这些类型，不要输出其他类型，或者相似类型。

请注意，餐厅的类型必须在这些类型中选择，以下为分城市结果：
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

请注意，住宿的类型必须在这些类型中选择。
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

如果计划中未提及该约束，请忽略它，不要做假设，不要提取此约束，只输出提到的约束，也不要重复输出约束。

如果查询表示多个约束需要满足其中任意一个即可，在约束里添加一个键值对 "or_item" : 1 来标记。
请明确区分整个旅行的总预算，以及景点、餐饮和住宿的单项预算。
根据指定的返回值的要求提取约束。如果返回值提供了选项列表，请从中选择。列表中未提及的约束无需提取。

!!!不要包含任何未提及的约束。
!!!约束选择确保返回的列表包含最相似的类型，不包括其他列表中未出现的类型。

请提取用户请求中的自然语言逻辑约束：

我们提供以下约束列表，可以帮助你提取用户请求中的自然语言逻辑约束。
变量：
(1) plan: 包含具体计划信息的生成计划字典。

约束列表 (Constraint List):

(1) total_cost (总预算)
说明：整个旅行的总花费。请注意，这是指整体支出，不是单项花费。
输出格式举例："total_cost" : 1200.00

(2) intercity_cost (城际交通预算)
说明：跨城市交通的预算。
输出格式举例："intercity_cost" : 900.00

(3) accommodation_cost (住宿预算)
说明：住宿的预算。
输出格式举例："accommodation_cost" : 300.00

(4) restaurant_cost (餐饮预算)
说明：外出就餐的预算。
输出格式举例："restaurant_cost" : 100.00

(5) attraction_cost (景点预算)
说明：景点门票的预算, 如果提到免费景点，约束就是景点预算为0。
输出格式举例："attraction_cost" : 400.00

(6) inner_city_cost (市内交通预算)
说明：城市内交通的预算。
输出格式举例："inner_city_cost" : 200.00

(7) go_must_type (去程偏好交通工具类型)
说明：去程城际旅行偏好的交通工具类型
返回：['train', 'airplane']
输出格式举例："go_must_type" : ['train']

(8) go_must_not_type (去程排除交通工具类型)
说明：去程城际旅行不希望使用的交通工具类型
返回：['train', 'airplane']
输出格式举例："go_must_not_type" : ['train']

(9) back_must_type (返程偏好交通工具类型)
说明：返程城际旅行偏好的交通工具类型
返回：['train', 'airplane']
输出格式举例："back_must_type" : ['airplane']

(10) back_must_not_type (返程排除交通工具类型)
说明：返程城际旅行不希望使用的交通工具类型
返回：['train', 'airplane']
输出格式举例："back_must_not_type" : ['airplane']

(11) must_not_accommodation_name (排除酒店名称)
说明：需要排除的酒店名称
返回：查询酒店名称
输出格式举例："must_not_accommodation_name" : ['全季酒店', '希尔顿酒店']

(12) must_accommodation_name_any (必选酒店名称之一)
说明：必须包含的酒店名称之一（多个中选一个）
返回：查询酒店名称
输出格式举例："must_accommodation_name_any" : ['全季酒店', '希尔顿酒店']

(13) must_not_accommodation_type (排除住宿类型)
说明：需要排除的住宿类型
返回：根据目标城市选择上述表格中的住宿类型
输出格式举例："must_not_accommodation_type" : ['民宿', '温泉']

(14) must_accommodation_name (必选酒店名称)
说明：必须包含的酒店名称
返回：查询酒店名称
输出格式举例："must_accommodation_name" : ['全季酒店', '希尔顿酒店']

(15) must_accommodation_type (必选住宿类型)
说明：必须包含的住宿类型
返回：根据目标城市选择上述表格中的住宿类型
输出格式举例："must_accommodation_type" : ['民宿', '温泉']

(16) must_accommodation_type_any (必选住宿类型之一)
说明：必须包含的住宿类型之一（多个中选一个）
返回：根据目标城市选择上述表格中的住宿类型
输出格式举例："must_accommodation_type_any" : ['民宿', '温泉']

(17) must_not_restaurant_type (排除餐厅类型)
说明：需要排除的餐厅类型
返回：根据目标城市选择上述表格中的餐厅类型
输出格式举例："must_not_restaurant_type" : ['东北菜', '川菜']

(18) must_restaurant_type (必选餐厅类型)
说明：必须包含的餐厅类型
返回：根据目标城市选择上述表格中的餐厅类型
输出格式举例："must_restaurant_type" : ['东北菜', '川菜']

(19) must_not_restaurant_name (排除餐厅名称)
说明：需要排除的餐厅名称
返回：查询餐厅名称
输出格式举例："must_not_restaurant_name" : ['程小棠茶食阁', '全聚德']

(20) must_restaurant_name (必选餐厅名称)
说明：必须包含的餐厅名称
返回：查询餐厅名称
输出格式举例："must_restaurant_name" : ['程小棠茶食阁', '全聚德']

(21) must_restaurant_type_any (必选餐厅类型之一)
说明：必须包含的餐厅类型之一（多个中选一个）
返回：根据目标城市选择上述表格中的餐厅类型
输出格式举例："must_restaurant_type_any" : ['东北菜', '川菜']

(22) must_restaurant_name_any (必选餐厅名称之一)
说明：必须包含的餐厅名称之一（多个中选一个）
返回：查询餐厅名称
输出格式举例："must_restaurant_name_any" : ['程小棠茶食阁', '全聚德']

(23) must_not_attraction_name (排除景点名称)
说明：需要排除的景点名称
返回：查询景点名称
输出格式举例："must_not_attraction_name" : ['西湖名胜风景区', '外滩']

(24) must_attraction_name (必选景点名称)
说明：必须包含的景点名称
返回：查询景点名称
输出格式举例："must_attraction_name" : ['西湖名胜风景区', '外滩']

(25) must_attraction_name_any (必选景点名称之一)
说明：必须包含的景点名称之一（多个中选一个）
返回：查询景点名称
输出格式举例："must_attraction_name_any : ['西湖名胜风景区', '外滩']

(26) must_not_attraction_type (排除景点类型)
说明：需要排除的景点类型
返回：根据目表城市选择上述景点类型表格里的内容
输出格式举例："must_not_attraction_type" : ['自然风光', '历史古迹']

(27) must_attraction_type (必选景点类型)
说明：必须包含的景点类型
返回：根据目表城市选择上述景点类型表格里的内容
输出格式举例："must_attraction_type" : ['自然风光', '历史古迹']

(28) must_attraction_type_any (必选景点类型之一)
说明：必须包含的景点类型之一（多个中选一个）
返回：根据目表城市选择上述景点类型表格里的内容
输出格式举例："must_attraction_type_any" : ['自然风光', '历史古迹']

(29) must_inner_city_transportation (必选市内交通方式)
说明：必须使用的市内交通方式
返回：['metro' (地铁), 'taxi' (出租车), 'walk' (步行)]
输出格式举例："must_inner_city_transportation" : ['taxi']

(30) must_not_inner_city_transportation (排除市内交通方式)
说明：不希望使用的市内交通方式
返回：['metro' (地铁), 'taxi' (出租车), 'walk' (步行)]
输出格式举例："must_not_inner_city_transportation" : ['walk']

(31) activate_start_time (活动最早开始时间)
说明：活动的最早出发时间
返回：活动名称和一个时间值的字符串
输出格式举例："activate_start_time" : ["烟袋斜街", "14:00"]

(32) activate_end_time (活动最晚到达时间)
说明：活动的最晚到达时间
返回：活动名称和一个时间值的字符串
输出格式举例："activate_end_time" : ["昆明湖", "16:00"]

(33) attraction_between (景点访问时段)
说明：在指定时间段内访问景点（在时间A和时间B之间）
返回：活动名称和两个时间值的字符串
输出格式举例："attraction_between" : ["秦大士故居", "9:00", "11:00"]

(34) attraction_stay_time (景点停留时间)
说明：在景点的停留时长
返回：景点名称 + 时间的字符串
输出格式举例："attraction_stay_time" : ['苏堤春晓碑亭', "90"]

(35) distance_transport (距离触发交通方式)
说明：当距离超过阈值时使用特定交通工具
返回：使用的交通方式名称 + 距离字符串
输出格式举例："distance_transport" : ["taxi", "14.69"]

(36) must_room_type (必选房间类型)
说明：必须包含的房间入住类型
返回：1 表示单人间, 2 表示双人间。必须为 1 或 2。
输出格式举例："must_room_type" : 1

(37) must_not_room_type (排除房间类型)
说明：需要排除的房间入住类型
返回：1 表示单人间, 2 表示双人间。必须为 1 或 2。
输出格式举例："must_not_room_type" : 2

(38) distance_hotel (酒店距景点最大距离)
说明：酒店与景点之间允许的最大距离
返回：景点名称 + 距离字符串 
输出格式举例："distance_hotel" : ["天安门城楼", "15.8"]

(39) attraction_seq (景点游览顺序)
说明：景点游览顺序（先游览A，再游览B）
返回：先游览的景点名称 + 后游览的景点名称
输出格式举例："attraction_seq" : ["文宇奶酪店", "银河SOHO"]

(40) days (天数)
说明：旅行的总天数
返回：一个数值
输出格式举例：days : 2

(41) people_number (人数)
说明：旅行的总人数
返回：一个数值
输出格式举例：people_number : 3

(42) start_city (起始城市)
说明：从这个城市出发
返回：['北京','南京','上海','杭州','深圳','武汉','广州','成都','重庆','苏州']
输出格式举例：start_city : "北京"

(43) target_city (目标城市)
说明：到这个城市旅行
返回：['北京','南京','上海','杭州','深圳','武汉','广州','成都','重庆','苏州']
输出格式举例：target_city : "上海"

(44) restaurant_stay_time (餐厅停留时间)
说明：在餐厅的停留时长
返回：餐厅名称 + 时间的字符串
输出格式举例："restaurant_stay_time" : ['全聚德烤鸭店', "90"]


！！！注意，不要输出重复的符号：""或[]。
严格按照输出格式举例的格式输出，
按以下格式输出：

<constraint>
约束 1
约束 2
...
<end>

!!!你必须遵守我们提供的所有规则：返回类型、选项列表、返回格式等！！！
!!!提取的约束必须严格按照给定格式输出。格式为字典，每个键值对为 名称:内容。
!!!不要把思考的过程写在结果里输出，不要输出不是约束的其他信息。

例如：
（1）查询： 我们3人，从上海出发，到深圳旅行4天，要求如下：\n不希望游览深圳博物馆历史民俗馆\n希望游览免费景点\n不希望以walk 和 taxi方式在城市内出行\n在住宿上的预算为9300.0\n不希望乘坐airplane前往目的地，不希望乘坐airplane返回
约束输出：
<constraint>
days : 4
people_number : 3
start_city : "上海"
target_city : "深圳"
must_not_attraction_name: ["深圳博物馆历史民俗馆"]
attraction_cost = 0
must_not_inner_city_transportation: ["walk", "taxi"]
accommodation_cost: 1700.0
go_must_not_type: "airplane"
back_must_not_type: "airplane"
<end>
"""
)


def load_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_constraint_line(line):

    if ':' not in line:
        return None, None
        
    key, value_str = line.split(':', 1)
    key = key.strip()
    value_str = value_str.strip()
    
    try:
        value = ast.literal_eval(value_str)
    except (ValueError, SyntaxError):
        value = value_str
    
    if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    
    return key, value

def get_constraints_prompt(query):
    return nl_constraint_prompt + "\n" + query["nature_language"]


def extract_nl_constraints(query, backbone_llm):
    prompt = get_constraints_prompt(query)
    constraints_dict = {}
    max_retries = 2
    attempts = 0
    
    while attempts < max_retries:
        response = backbone_llm(
            messages=[{"role": "user", "content": prompt}],
            one_line=False,
            json_mode=False,
        )
        
        if "<constraint>" in response and "<end>" in response:
            constraints_text = response.split("<constraint>")[1].split("<end>")[0].strip()
            
            for line in constraints_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                    
                if line.split(".", 1)[0].isdigit():
                    line = line.split(".", 1)[1].strip()
                    
                key, value = parse_constraint_line(line)
                if key:
                    constraints_dict[key] = value
        
        if constraints_dict:
            break
            
        attempts += 1
        print(f"Warning: Empty constraint result (attempt {attempts}/{max_retries})")

    return {"nature_language_constraints": constraints_dict}

def process_query(query, backbone_llm):
    constraints_result = extract_nl_constraints(query, backbone_llm)
    
    result = {
        "uid": query.get("uid", "unknown"),
        "nature_language": query["nature_language"],
        "nature_language_constraints": constraints_result["nature_language_constraints"]
    }
    
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", "-d", type=str, default="tpc_phase1", help="输入数据目录")
    parser.add_argument("--output_dir", "-o", type=str, default="constraints_output30", help="输出目录")
    args = parser.parse_args()

    llama = Llama(model_name="Llama3-8B")

    os.makedirs(args.output_dir, exist_ok=True)

    data_dir = os.path.join(project_root_path, "chinatravel", "data", args.data_dir)
    print(f"Processing directory: {data_dir}")
    
    file_list = os.listdir(data_dir)
    for file_name in tqdm(file_list, desc="Processing files"):
        if not file_name.endswith(".json"):
            continue
            
        file_path = os.path.join(data_dir, file_name)
        
        try:

            query = load_json_file(file_path)

            result = process_query(query, llama)

            output_path = os.path.join(args.output_dir, f"{result['uid']}.json")
            
        except Exception as e:
            print(f"Error occurred while processing file {file_name}: {str(e)}")
            continue
        
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        return super().default(obj)

def format_set(items):
    if not items:
        return "set()"
    items_str = ", ".join(json.dumps(item, ensure_ascii=False) for item in items)
    return "{" + items_str + "}"

def transfor(hard_logic, py):
    result = ""
    if 'total_cost' in hard_logic:
        result = f"total_cost=0 \nfor activity in allactivities(plan):\n    total_cost+=activity_cost(activity)\n    total_cost += innercity_transport_cost(activity_transports(activity))\nresult=(total_cost<={int(hard_logic['total_cost'])})"
    elif 'intercity_cost' in hard_logic:
        result = f"inter_city_transportation_cost=0\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['airplane','train']: inter_city_transportation_cost+=activity_cost(activity)\nresult=inter_city_transportation_cost<={int(hard_logic['intercity_cost'])}"
    elif 'go_must_type' in hard_logic:
        if 'back_must_type' in py:
            result = f"result=False\nintercity_transport_go=''\nintercity_transport_back=''\nif allactivities(plan)[0]['type'] == \"{hard_logic['go_must_type'][0]}\" and intercity_transport_origin(allactivities(plan)[0])==start_city(plan) and allactivities(plan)[-1]['type'] == \"{py['back_must_type'][0]}\" and intercity_transport_origin(allactivities(plan)[-1])==target_city(plan):\n  result=True"
        else:
            result = f"result=False\nintercity_transport_go=''\nintercity_transport_back=''\nif allactivities(plan)[0]['type'] == \"{hard_logic['go_must_type'][0]}\" and intercity_transport_origin(allactivities(plan)[0])==start_city(plan) and allactivities(plan)[-1]['type'] == \"{hard_logic['go_must_type'][0]}\" and intercity_transport_origin(allactivities(plan)[-1])==target_city(plan):\n  result=True"
    elif 'go_must_not_type' in hard_logic:
        if 'back_must_not_type' in py:
            result = f"result=False\nintercity_transport_go=''\nintercity_transport_back=''\nif allactivities(plan)[0]['type'] != \"{hard_logic['go_must_not_type'][0]}\" and intercity_transport_origin(allactivities(plan)[0])==start_city(plan) and allactivities(plan)[-1]['type'] != \"{py['back_must_not_type'][0]}\" and intercity_transport_origin(allactivities(plan)[-1])==target_city(plan):\n  result=True"
        else:
            result = f"result=False\nintercity_transport_go=''\nintercity_transport_back=''\nif allactivities(plan)[0]['type'] != \"{hard_logic['go_must_not_type'][0]}\" and intercity_transport_origin(allactivities(plan)[0])==start_city(plan) and allactivities(plan)[-1]['type'] != \"{hard_logic['go_must_not_type'][0]}\" and intercity_transport_origin(allactivities(plan)[-1])==target_city(plan):\n  result=True"
    elif 'must_not_accommodation_name' in hard_logic:
        result = f"accommodation_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_name_set.add(activity_position(activity))\nresult=not({format_set(hard_logic['must_not_accommodation_name'])}&accommodation_name_set)"
    elif 'must_accommodation_name_any' in hard_logic:
        result = f"accommodation_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_accommodation_name_any'])}&accommodation_name_set)"
    elif 'must_not_accommodation_type' in hard_logic:
        result = f"accommodation_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_type_set.add(accommodation_type(activity, target_city(plan)))\nresult=not({format_set(hard_logic['must_not_accommodation_type'])}&accommodation_type_set)"
    elif 'must_accommodation_type_any' in hard_logic:
        result = f"accommodation_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_type_set.add(accommodation_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_accommodation_type_any'])}&accommodation_type_set)" 
    elif 'must_accommodation_name' in hard_logic:
        result = f"accommodation_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_accommodation_name'])}<=accommodation_name_set)"
    elif 'must_accommodation_type' in hard_logic:
        result = f"accommodation_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_type_set.add(accommodation_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_accommodation_type'])}<=accommodation_type_set)"
    elif 'must_room_type' in hard_logic:
        result = f"result=True\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation' and room_type(activity)!={hard_logic['must_room_type']}: result=False"
    elif 'distance_hotel' in hard_logic:
        result = f"result=False\naccommodation_position=''\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_position=activity_position(activity)\nresult=(poi_distance(target_city(plan), '{hard_logic['distance_hotel'][0]}', accommodation_position)<={hard_logic['distance_hotel'][1]})"
    elif 'accommodation_cost' in hard_logic:
        result = f"accommodation_cost=0\nfor activity in allactivities(plan):\n  if activity_type(activity)=='accommodation': accommodation_cost+=activity_cost(activity)\nresult=accommodation_cost<={int(hard_logic['accommodation_cost'])}"
    elif 'must_not_restaurant_name' in hard_logic:
        result = f"restaurant_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_name_set.add(activity_position(activity))\nresult=not({format_set(hard_logic['must_not_restaurant_name'])}&restaurant_name_set)"
    elif 'must_restaurant_name_any' in hard_logic:
        result = f"restaurant_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_restaurant_name_any'])}&restaurant_name_set)"
    elif 'must_not_restaurant_type' in hard_logic:
        result = f"restaurant_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_type_set.add(restaurant_type(activity, target_city(plan)))\nresult=not({format_set(hard_logic['must_not_restaurant_type'])}&restaurant_type_set)"
    elif 'must_restaurant_type_any' in hard_logic:
        result = f"restaurant_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_type_set.add(restaurant_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_restaurant_type_any'])}&restaurant_type_set)"
    elif 'must_restaurant_name' in hard_logic:
        result = f"restaurant_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_restaurant_name'])}<=restaurant_name_set)"
    elif 'must_restaurant_type' in hard_logic:
        result = f"restaurant_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_type_set.add(restaurant_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_restaurant_type'])}<=restaurant_type_set)"
    elif 'restaurant_cost' in hard_logic:
        result = f"restaurant_cost=0\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['breakfast', 'lunch', 'dinner']: restaurant_cost+=activity_cost(activity)\nresult=restaurant_cost<={int(hard_logic['restaurant_cost'])}"
    elif 'must_not_attraction_name' in hard_logic:
        result = f"attraction_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_name_set.add(activity_position(activity))\nresult=not({format_set(hard_logic['must_not_attraction_name'])}&attraction_name_set)"
    elif 'must_attraction_name_any' in hard_logic:
        result = f"attraction_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_attraction_name_any'])}&attraction_name_set)"
    elif 'must_not_attraction_type' in hard_logic:
        result = f"attraction_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_type_set.add(attraction_type(activity, target_city(plan)))\nresult=not({format_set(hard_logic['must_not_attraction_type'])}&attraction_type_set)"
    elif 'must_attraction_type_any' in hard_logic:
        result = f"attraction_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_type_set.add(attraction_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_attraction_type_any'])}&attraction_type_set)"
    elif 'must_attraction_name' in hard_logic:
        result = f"attraction_name_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_name_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_attraction_name'])}<=attraction_name_set)"
    elif 'must_attraction_type' in hard_logic:
        result = f"attraction_type_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_type_set.add(attraction_type(activity, target_city(plan)))\nresult=({format_set(hard_logic['must_attraction_type'])}<=attraction_type_set)"
    elif 'attraction_cost' in hard_logic:
        result = f"attraction_cost=0\nfor activity in allactivities(plan):\n  if activity_type(activity)=='attraction': attraction_cost+=activity_cost(activity)\nresult=attraction_cost<={int(hard_logic['attraction_cost'])}"
    elif 'attraction_seq' in hard_logic:
        result = f"result=False\nidx_activity0=0\nidx_activity1=0\ni=0\nfor activity in allactivities(plan):\n  if activity_position(activity)=={hard_logic['attraction_seq'][1]}:\n    idx_activity0=i\n  if activity_position(activity)=={hard_logic['attraction_seq'][1]}:\n    idx_activity1=i\n  i+=1\nif idx_activity0<idx_activity1:\n  result=True"
    elif 'attraction_stay_time' in hard_logic:
        result = f"result=False\nfor activity in allactivities(plan):\n  if activity_position(activity)=={hard_logic['attraction_stay_time'][0]}:\n    if activity_time(activity)>={hard_logic['attraction_stay_time'][1]}:\n      result=True"
    elif 'attraction_between' in hard_logic:
        result = f"result=False\nfor activity in allactivities(plan):\n  if activity_position(activity)=='{hard_logic['attraction_between'][0]}':\n    if activity_start_time(activity)<='{hard_logic['attraction_between'][1]}' and activity_end_time(activity)>='{hard_logic['attraction_between'][2]}':\n      result=True"
    elif 'activate_start_time' in hard_logic:
        result = f"result=False\nfor activity in allactivities(plan):\n  if activity_position(activity)=='{hard_logic['activate_start_time'][0]}':\n    if activity_end_time(activity)>='{hard_logic['activate_start_time'][1]}':\n      result=True"
    elif 'activate_end_time' in hard_logic:
        result = f"result=False\nfor activity in allactivities(plan):\n  if activity_position(activity)=='{hard_logic['activate_end_time'][0]}':\n    if activity_start_time(activity)<='{hard_logic['activate_end_time'][1]}':\n      result=True"
    elif 'must_not_inner_city_transportation' in hard_logic:
        result = f"inner_city_transportation_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='transportation': inner_city_transportation_set.add(activity_position(activity))\nresult=not({format_set(hard_logic['must_not_inner_city_transportation'])}&inner_city_transportation_set)"
    elif 'must_inner_city_transportation' in hard_logic:
        result = f"inner_city_transportation_set=set()\nfor activity in allactivities(plan):\n  if activity_type(activity)=='transportation': inner_city_transportation_set.add(activity_position(activity))\nresult=({format_set(hard_logic['must_inner_city_transportation'])}<=inner_city_transportation_set)"
    elif 'inner_city_cost' in hard_logic:
        result = f"inner_city_transportation_cost=0 \nfor activity in allactivities(plan):\n    inner_city_transportation_cost += innercity_transport_cost(activity_transports(activity))\nresult=(inner_city_transportation_cost<={int(hard_logic['inner_city_cost'])})"
    elif 'distance_transport' in hard_logic:
        result = f"result=True\nfor activity in allactivities(plan):\n  if innercity_transport_type(activity_transports(activity)) != '{hard_logic['distance_transport'][0]}' and innercity_transport_distance(activity_transports(activity))>{hard_logic['distance_transport'][1]}:\n    result=False\n    break"
    return result

def result_py(hard_logic):
    hard_logic_py = []
    for key, value in hard_logic.items():
        dict1 = {key : value}
        if 'back_must_type' in dict1 and 'go_must_type' not in hard_logic:
            hard_logic_py.append(transfor({'go_must_type' : value}, hard_logic))
        if 'back_must_type' in dict1 or 'back_must_not_type' in dict1 or 'start_city' in dict1 or 'target_city' in dict1 or 'days' in dict1 or 'people_number' in dict1:
            continue
        hard_logic_py.append(transfor(dict1, hard_logic))
    return hard_logic_py

def result_list_py(hard_logic):
    result_list = "result_list=[]\n"
    for key, value in hard_logic.items():
        dict1 = {key : value}
        if 'back_must_type' in dict1 and 'go_must_type' not in hard_logic:
            hard_logic_py.append(transfor({'go_must_type' : value}, hard_logic))
        if 'back_must_type' in dict1 or 'back_must_not_type' in dict1 or 'start_city' in dict1 or 'target_city' in dict1 or 'days' in dict1 or 'people_number' in dict1 or 'or_item' in dict1:
            continue
        result = transfor(dict1, hard_logic)
        result_list += result + "\n"
        result_list += "result_list.append(result)\n"
    result_list += "result=False\n"
    result_list += "for r in result_list:\n"
    result_list += "  result=result or r"
    hard_logic_py = [result_list]
    return hard_logic_py

def run_NL2DSL(input_json, backbone_llm):
    llama = backbone_llm
    constraint_result = process_query(input_json, llama)
    hard_logic = constraint_result['nature_language_constraints']
    output = {}
    output['uid'] = constraint_result['uid']
    if 'start_city' in hard_logic:
        output['start_city'] = hard_logic['start_city']
    if 'target_city' in hard_logic:
        output['target_city'] = hard_logic['target_city']
    if 'days' in hard_logic:
        output['days'] = hard_logic['days']
    if 'people_number' in hard_logic:
        output['people_number'] = hard_logic['people_number']
    output['nature_language'] = constraint_result['nature_language']
    result = []
    flag = 0
    if 'or_item' in hard_logic:
        result = result_list_py(hard_logic)
        flag = 1
    else:
        result = result_py(hard_logic)
    if flag == 0:
        if "days" in hard_logic:
            result.append("result=(day_count(plan)=={})".format(output['days']))
        if "people_number" in hard_logic:
            result.append("result=(people_count(plan)=={})".format(output['people_number']))
            result.append("result=True\nfor activity in allactivities(plan):\n  if activity_type(activity) in ['attraction', 'airplane', 'train'] and activity_tickets(activity)!={}: result=False\n  if innercity_transport_type(activity_transports(activity))=='metro'and metro_tickets(activity_transports(activity))!={}: result=False".format(output['people_number'], output['people_number']))
            result.append("result=True\nfor activity in allactivities(plan):\n  if innercity_transport_type(activity_transports(activity))=='taxi'and taxi_cars(activity_transports(activity))!={}: result=False".format((output['people_number']+3) // 4))
    output['hard_logic_py'] = result
    
    return output


if __name__ == "__main__":
    run_NL2DSL()