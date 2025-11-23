from datetime import datetime, timedelta
import concurrent.futures
import json, sys, os
import time
from itertools import combinations
from pypinyin import lazy_pinyin
import requests
import logging

sys.path.append("./../../../")
project_root_path = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
from agent.tpc_agent.prompts_test import arrival_time_prompts, date_prompts, ask_day, stay_time, order, sequence, inclusion, exclusion, travel_tenseness, must_poi


if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)

class Constraint_result():

    def __init__(self, model):
        self.model = model
    
    def fix_double_braces_json(self, json_string):

        if json_string.startswith('{{') and json_string.endswith('}}'):
            fixed_string = json_string[1:-1]
            return fixed_string
        return json_string

    def send_request(self, prompt_func, user_query):
        try:
            query = [{"role": "user", "content": prompt_func(user_query)}]
            response = self.model(query, one_line=False, json_mode=False)
            response = self.fix_double_braces_json(response)
            return json.loads(response.replace("&quot;", "\"").replace("```json", "").replace("```", ""))
        except Exception as e:
            return {"error": str(e)}
        
    def constraint_extraction(self, user_query):
        task_definitions = {
            "arrival_time": lambda: self.send_request(arrival_time_prompts, user_query),
            "stay_time": lambda: self.send_request(stay_time, user_query),
            "order": lambda: self.send_request(order, user_query),
            "sequence": lambda: self.send_request(sequence, user_query),
            "inclusion": lambda: self.send_request(inclusion, user_query),
            "exclusion": lambda: self.send_request(exclusion, user_query),
            "ext_infos": lambda: self.send_request(travel_tenseness, user_query)
            }
        results = {}
        for task_name, task in task_definitions.items():
            try:
                result = task()
                results[task_name] = result
            except Exception as e:
                results[task_name] = {"error": str(e)}
        today = datetime.today()
        formatted_date = today.strftime("%Y-%m-%d")
        days_query = [{'role': 'user', 'content': ask_day(query=user_query)}]
        days = int(self.model(days_query, one_line=False, json_mode=False))
        dates = [today + timedelta(days=i) for i in range(1, days + 1)]
        formatted_dates = [date.strftime("%Y-%m-%d") for date in dates]

        play_date_query = [{'role': 'user', 'content': date_prompts(query=user_query, date_constraints=formatted_dates)}]
        try:
            arrival_time = json.loads(self.model(play_date_query, one_line=False, json_mode=False).replace("&quot;", "\"").replace("```json", "").replace("```", ""))
        except:
            arrival_time = self.model(play_date_query, one_line=False, json_mode=False)
        results["date"] = arrival_time
        return results, days, formatted_dates

    def generate_schedule(self, formatted_dates, days, arrival_time, departure_time, earliest_result, lastest_result):
        schedule = {}
        for i in range(days):
            if i == 0:
                schedule[formatted_dates[i].replace("-", "")] = {
                    "arrival": {"time": arrival_time},
                    "departure": {"time": earliest_result["EndTime"]}
                }
            elif i == days - 1:
                schedule[formatted_dates[i].replace("-", "")] = {
                "arrival": {"time": lastest_result["BeginTime"]},
                "departure": {"time": departure_time}
            }
            else:
                schedule[formatted_dates[i].replace("-", "")] = {
                    "arrival": {"time": arrival_time},
                    "departure": {"time": departure_time}
                }

        return schedule


    def check_and_update_coordinates(full_poi_list, required_scenics_data):
        poi_dict = {poi["poi_id"]: poi for poi in full_poi_list}

        for scenic in required_scenics_data["required_scenics"]:
            poi_id = scenic["poi_id"]
            if poi_id in poi_dict:
                original_latitude = poi_dict[poi_id]["latitude"]
                original_longitude = poi_dict[poi_id]["longitude"]

                if scenic["latitude"] != original_latitude or scenic["longitude"] != original_longitude:
                    scenic["latitude"] = original_latitude
                    scenic["longitude"] = original_longitude

        return required_scenics_data

    def transform_data(self, input_data):
        scenic_list = []
        for poi in input_data.get("pois_info", []):
            scenic_list.append({
                "name": poi["poi_name"],
                "score":8.7,
                "cityCode": "310100", 
                "id": poi["poi_id"],
                "location": [poi["longitude"], poi["latitude"]],
                "latitude": poi["latitude"],
                "longitude": poi["longitude"],
                "type": [poi["type"]],
                "travel_time": poi["travel_time"]
            })

        scenic_traffic_list = []
        for key in ["constraint_1", "constraint_2", "constraint_3", "constraint_4", "constraint_5", "constraint_6", "constraint_7"]:
            for constraint in input_data.get(key, []):
                if constraint.get("type") == "traffic":
                    scenic_pair = constraint.get("ids", [])
                    traffic_info = constraint.get("traffic_info", [])
                    edge_id = len(scenic_traffic_list) + 1
                    scenic_traffic_list.append({
                        "scenic_pair": scenic_pair,
                        "traffic_info": traffic_info,
                        "edge_id": edge_id
                    })
        user_preference = {
            "ext_infos": input_data.get("ext_infos", {}),
            "scheduling": input_data.get("scheduling", {}),
            "udf_scenic_date": {},
            "day_fixed": True,
            "udf_scenic_time": {},
            "planning_hotel": False,
            "day_fixed": True,
            "required_scenic_ids": input_data.get("required_scenic_ids", [])
        }

        constraints = []
        for key in ["constraint_1", "constraint_2", "constraint_3", "constraint_4", "constraint_5", "constraint_6", "constraint_7"]:
            for constraint in input_data.get(key, []):
                if constraint.get("type") != "traffic":  
                    new_constraint = {
                        "type": constraint.get("type"),
                        "ids": constraint.get("ids", []),
                        "info": constraint.get("info"),
                    }
                    if "value" in constraint:
                        new_constraint["value"] = constraint["value"]
                    constraints.append(new_constraint)

        result = {
            "scenic_list": scenic_list,
            "scenic_traffic_list": scenic_traffic_list,
            "user_preference": user_preference,
            "constraints": constraints
        }

        return result
    
    def collect_innercity_transport(self, city, start, end, start_time, env, query=None, trans_type="taxi"):
        call_str = (
            'goto("{city}", "{start}", "{end}", "{start_time}", "{trans_type}")'.format(
                city=city,
                start=start,
                end=end,
                start_time=start_time,
                trans_type=trans_type,
            )
        )
        if start == end:
            return []
        info = env(call_str)["data"]

        if not isinstance(info, list):
            return "No solution"
        
        time_format = "%H:%M"

        if len(info) == 3:
            info[1]["price"] = info[1]["cost"]
            info[1]["tickets"] = query["people_number"]
            info[1]["cost"] = info[1]["price"] * info[1]["tickets"]

            info[0]["price"] = info[0]["cost"]
            info[2]["price"] = info[2]["cost"]
        elif info[0]["mode"] == "taxi":
            info[0]["price"] = info[0]["cost"]
            info[0]["cars"] = int((query["people_number"] - 1) / 4) + 1
            info[0]["cost"] = info[0]["price"] * info[0]["cars"]
        elif info[0]["mode"] == "walk":
            info[0]["price"] = info[0]["cost"]

        return info
    
    def generate_travel_plan(self, attraction_queries, city_name, recommended):
        required_scenics = []
        for attraction in attraction_queries:
            for recommend in recommended:
                if recommend["name"] == attraction:
                    scenic_info = {
                        "name": attraction,
                        "poi_name": attraction,
                        "poi_id": ''.join(lazy_pinyin(attraction)),
                        "city_name": city_name+"市",
                        "latitude": recommend["lat"],  
                        "longitude": recommend["lon"]  
                    }
                    required_scenics.append(scenic_info)
        travel_plan = {
            "required_scenics": required_scenics,
            "required_scenic_ids": [scenic["poi_id"] for scenic in required_scenics]
        }
        
        return travel_plan

    def time_range_to_seconds(self, start: str, end: str) -> int:
        fmt = "%H:%M"
        if end == "24:00":
            end = "23:59"
        t1 = datetime.strptime(start, fmt)
        t2 = datetime.strptime(end, fmt)
        if t2 <= t1:
            t2 += timedelta(days=1)
        return int((t2 - t1).total_seconds())
    
    def poi_match(self, recommended, city_name):
        required_scenics = []
        for recommend in recommended:
            if int(recommend["recommendmaxtime"]*3600) <= int(self.time_range_to_seconds(recommend["opentime"], recommend["endtime"])):
                recommendmaxtime = int(recommend["recommendmaxtime"]*3600)
            else:
                recommendmaxtime = int(self.time_range_to_seconds(recommend["opentime"], recommend["endtime"]))
            scenic_info = {
                "name": recommend["name"],
                "poi_name": recommend["name"],
                "poi_id": ''.join(lazy_pinyin(recommend["name"])),
                "city_name": city_name + "市",
                "latitude": recommend["lat"],  
                "longitude": recommend["lon"],
                "type": recommend["type"],
                "travel_time": [recommendmaxtime, int(self.time_range_to_seconds(recommend["opentime"], recommend["endtime"]))]
            }
            required_scenics.append(scenic_info)
        return required_scenics

    def format_result(self, user_query, constraint, days, attractions, city_name, recommended, attraction_query, formatted_dates, earliest_result, lastest_result):
        query_analysis = self.generate_travel_plan(attraction_query["must_attraction_name"], city_name, recommended)
        query_ask = self.poi_match(recommended, city_name)

        format_constraint = {
            "type": "format_constraints",
            "pois_info": query_ask,    
            "constraint_1": constraint.get('arrival_time', {}).get('constraints', []),
            "constraint_2": [],
            "constraint_3": constraint.get('stay_time', {}).get('constraints', []),
            "constraint_4": [],
            "constraint_5": constraint.get('sequence', {}).get('constraints', []),
            "constraint_6": [],
            "constraint_7": [],
            "days": days,
            "scheduling": self.generate_schedule(formatted_dates, days, arrival_time="22:00", departure_time="7:00", earliest_result=earliest_result, lastest_result=lastest_result),
            "ext_infos": constraint['ext_infos'],
            "required_scenics": query_analysis['required_scenics'],
            "required_scenic_ids": query_analysis['required_scenic_ids']
        }
        return format_constraint
    
    def generate_traffic_info(self, pairs, name_mapping, env, query, json_load):
        city = query["target_city"]
        start_time = "07:00"
        trans_type = None

        TIME_FMT = "%H:%M"
        LEGAL_END = datetime.strptime("23:59", TIME_FMT)
        def is_valid_end_time(t_str: str) -> bool:
            try:
                t = datetime.strptime(t_str, TIME_FMT)
                return t <= LEGAL_END
            except Exception:
                return False
        def has_invalid_end_time(data) -> bool:
            if data == "No solution" or data is None:
                return True

            segments = []
            if isinstance(data, dict):
                segments = [data]
            elif isinstance(data, list):
                for item in data:
                    segments.extend(item if isinstance(item, list) else [item])
            else:
                return True
            for seg in segments:
                if not isinstance(seg, dict):
                    return True
                if not is_valid_end_time(seg.get("end_time", "")):
                    return True
            return False
        def has_any_segment_short(data, threshold=2):
            if data == "No solution" or data is None:
                return True

            segments = []
            if isinstance(data, dict):
                segments = [data]
            elif isinstance(data, list):
                for item in data:
                    segments.extend(item if isinstance(item, list) else [item])
            else:
                return True
            for seg in segments:
                if not isinstance(seg, dict):
                    return True
                if seg.get("distance", 0) < threshold:
                    return True
            return False
        result = []
        edge_id = 1

        for start_id, end_id in pairs:
            start_name = name_mapping.get(start_id)
            end_name = name_mapping.get(end_id)

            if not start_name or not end_name or start_name == end_name:
                continue
            if json_load["must_inner_city_transportation"] == [] or "taxi" in json_load.get("must_inner_city_transportation", []):
                traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type="metro")
                if has_invalid_end_time(traffic_data):
                    traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type="taxi")
                    if has_any_segment_short(traffic_data, 2):
                        traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type="walk")
            elif len(json_load["must_inner_city_transportation"])==1:
                traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type=json_load["must_inner_city_transportation"][0])
                if traffic_data == "No solution":
                    traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type="walk")
            else:
                traffic_data = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type=json_load["must_inner_city_transportation"][0])
                traffic_data_1 = self.collect_innercity_transport(city, start_name, end_name, start_time, env, query, trans_type=json_load["must_inner_city_transportation"][1])
                if traffic_data != "No solution":
                    traffic_data.append(traffic_data_1)
            if traffic_data == "No solution" or not traffic_data:
                continue
            time_format = "%H:%M"

            traffic_info_list = []

            for data in traffic_data:
                if isinstance(data, list): 
                    for info in data:
                        if isinstance(info, dict):  
                            traffic_info = {
                                "distance": info.get("distance", 0) * 1000,
                                "cost_time": (datetime.strptime(info.get("end_time", "00:00"), time_format) - datetime.strptime(info.get("start_time", "00:00"), time_format)).total_seconds(),
                                "traffic_type": info.get("mode", "unknown")
                            }
                            traffic_info_list.append(traffic_info)

                elif isinstance(data, dict):  
                    traffic_info = {
                        "distance": data.get("distance", 0) * 1000,
                        "cost_time": (datetime.strptime(data.get("end_time", "00:00"), time_format) - datetime.strptime(data.get("start_time", "00:00"), time_format)).total_seconds(),
                        "traffic_type": data.get("mode", "unknown")
                    }
                    traffic_info_list.append(traffic_info)

            result.append({
                "scenic_pair": [start_id, end_id],
                "traffic_info": traffic_info_list,
                "edge_id": edge_id
            })

            edge_id += 1

        return {"scenic_traffic_list": result}

    def format_id(self, results, env, query, json_load):
        name_list = [item["name"] for item in results["scenic_list"]]
        name_list_1 = [item["id"] for item in results["scenic_list"]]
        scenic_pairs = list(combinations(name_list_1, 2))
        spot_mapping = {pinyin: name for pinyin, name in zip(name_list_1, name_list)}
        a = self.generate_traffic_info(scenic_pairs, spot_mapping, env, query, json_load)["scenic_traffic_list"]
        results["scenic_traffic_list"] = a

        pinyin_to_id = {}
        for id, name in spot_mapping.items():
            name_pinyin = ''.join(lazy_pinyin(name))
            pinyin_to_id[name_pinyin] = id

        unmatched = []
        for i in range(len(results["constraints"])):
            result = []
            for pinyin in results["constraints"][i]["ids"]:
                matched = False
                for name_pinyin, id in pinyin_to_id.items():
                    if pinyin in name_pinyin:  
                        result.append(id)
                        results["constraints"][i]["ids"] = result
                        matched = True
                        break  
                if not matched:
                    unmatched.append(pinyin)
        return results
    
    def constraint_time(self, solution, recommended):
        scheduling = solution["user_preference"]["scheduling"]
        dates = list(scheduling.keys())
        i = 0
        for item in solution["scenic_list"]:    
            item['scenic_time'] = self.generate_schedule_new(dates, recommended, i)
            i += 1
        return solution
    
    def generate_schedule_new(self, dates, recommended, i):
        schedule_structure = {
            'closing_time':str(recommended[i].get('endtime')),
            'is_open': True,
            'opening_time':str(recommended[i].get('opentime'))
        }
        
        schedule = {date.replace("-", ""): schedule_structure.copy() for date in dates}
        
        return schedule
    
    def combined_metro(self, result):
        for scenic_data in result["scenic_traffic_list"]:
            traffic_info = scenic_data["traffic_info"]
            new_traffic_info = []
            i = 0

            while i < len(traffic_info):
                current = traffic_info[i]

                if current.get("traffic_type") == "metro":
                    total_distance = current["distance"]
                    total_cost_time = current["cost_time"]
                    merged = False

                    if i > 0 and traffic_info[i-1]["traffic_type"] == "walk" and (i == 1 or traffic_info[i-2]["traffic_type"] != "metro"):
                        total_distance += traffic_info[i-1]["distance"]
                        total_cost_time += traffic_info[i-1]["cost_time"]
                        if new_traffic_info and new_traffic_info[-1]["traffic_type"] == "walk":
                            new_traffic_info.pop()
                        merged = True

                    if i + 1 < len(traffic_info) and traffic_info[i+1]["traffic_type"] == "walk":
                        total_distance += traffic_info[i+1]["distance"]
                        total_cost_time += traffic_info[i+1]["cost_time"]
                        i += 1  
                        merged = True

                    new_traffic_info.append({
                        "distance": int(total_distance),
                        "cost_time": int(total_cost_time),
                        "traffic_type": "metro"
                    })

                    if merged and i > 0 and traffic_info[i-1]["traffic_type"] == "walk":
                        pass  
                    else:
                        i += 1

                else:
                    new_traffic_info.append(current)
                    i += 1

            scenic_data["traffic_info"] = new_traffic_info

        return result


    def merge_metro_walk(self, traffic_info_list):
        merged_traffic = []
        try:
            if len(traffic_info_list) == 3:
                i =1
                current = traffic_info_list[i]
                if current["traffic_type"] == "metro":
                    total_distance = current["distance"]
                    total_cost_time = current["cost_time"]

                    if i > 0 and traffic_info_list[i - 1]["traffic_type"] == "walk" and i + 1 < len(traffic_info_list) and traffic_info_list[i + 1]["traffic_type"] == "walk":
                        prev_walk = traffic_info_list[i - 1]
                        total_distance += prev_walk["distance"]
                        total_cost_time += prev_walk["cost_time"]
                        next_walk = traffic_info_list[i + 1]
                        total_distance += next_walk["distance"]
                        total_cost_time += next_walk["cost_time"]                        

                        merged_traffic.append({
                            "distance": int(total_distance),
                            "cost_time": int(total_cost_time),
                            "traffic_type": "metro_1"
                        })
                    else:
                        return traffic_info_list
                else:
                    traffic_info_list
        except:
            return traffic_info_list
        return merged_traffic