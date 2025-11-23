import json, sys, math
import pandas as pd
from datetime import datetime, timedelta

project_root_path = "./chinatravel"
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
project_root_path = "./"
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
from chinatravel.environment.world_env import WorldEnv
from chinatravel.agent.tpc_agent.constraint import Constraint_result


def collect_innercity_transport(city, start, end, start_time, env, people_number, trans_type="taxi"):
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
        info[1]["tickets"] = people_number
        info[1]["cost"] = info[1]["price"] * info[1]["tickets"]

        info[0]["price"] = info[0]["cost"]
        info[2]["price"] = info[2]["cost"]
    elif info[0]["mode"] == "taxi":
        info[0]["price"] = info[0]["cost"]
        info[0]["cars"] = int((people_number - 1) / 4) + 1
        info[0]["cost"] = info[0]["price"] * info[0]["cars"]
    elif info[0]["mode"] == "walk":
        info[0]["price"] = info[0]["cost"]

    return info

def transport_result(transport, target_city, previous_end, now_end, previous_end_time, env, people_number):

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
    if isinstance(previous_end_time, datetime):
        previous_end_time = previous_end_time.strftime("%H:%M")
    else:
        try:
            previous_end_time = datetime.strptime(previous_end_time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
        except:
            if previous_end_time == "24:00":
                previous_end_time = "23:59"
            previous_end_time = datetime.strptime(previous_end_time, "%H:%M").strftime("%H:%M")
    if transport == [] or ( "taxi" in transport and len(transport)>1 ):
        traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type="metro")
        if has_invalid_end_time(traffic_data):
            traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type="taxi")
            if has_any_segment_short(traffic_data, 2):
                traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type="walk")
    elif len(transport)==1:
        traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type=transport[0])
        if traffic_data == "No solution":
            traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type="walk")
    else:
        traffic_data = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type=transport[0])
        traffic_data_1 = collect_innercity_transport(city=target_city, start=previous_end, end=now_end, start_time=previous_end_time, env=env, people_number=people_number, trans_type=transport[1])
        if traffic_data != "No solution" and traffic_data_1 != "No solution":
            if transport[0] == "metro":
                return traffic_data
            else:
                return traffic_data_1
        elif traffic_data != "No solution":
            return traffic_data
        elif traffic_data_1 != "No solution":
            return traffic_data_1
    return traffic_data

def add_big_traffic(old_result, days, big_traffic, env, people_number): 
    old_itinerary = old_result["itinerary"] 
    
    if len(old_itinerary) == days:
        return old_result
    
    if len(old_itinerary) > days:
        return None
        
    trr_start = old_itinerary[-1]['activities'][-1]['position']
    trr_end = big_traffic["From"]
    print(big_traffic)
    trr_info = collect_innercity_transport(old_result['target_city'], trr_start, trr_end, "0:00", env, old_result['people_number'], "taxi")[0]
    if "FlightID" in big_traffic:
        new_day = {
            "day": len(old_itinerary) + 1,
            "activities": [
            {
                "start_time": big_traffic["BeginTime"],
                "end_time": big_traffic["EndTime"],
                "start": big_traffic["From"],
                "end": big_traffic["To"],
                "price": big_traffic["Cost"],
                "cost": big_traffic["Cost"] * people_number,
                "FlightID": big_traffic["FlightID"],
                "type": "airplane",
                "tickets": people_number,
                "transports": trr_info,
            }
        ]
        }
    else:
        new_day = {
            "day": len(old_itinerary) + 1,
            "activities": [
            {
                "start_time": big_traffic["BeginTime"],
                "end_time": big_traffic["EndTime"],
                "start": big_traffic["From"],
                "end": big_traffic["To"],
                "price": big_traffic["Cost"],
                "cost": big_traffic["Cost"] * people_number,
                "TrainID": big_traffic["TrainID"],
                "type": "train",
                "tickets": people_number,
                "transports": trr_info,
            }
        ]
        }        
    
    old_result["itinerary"].append(new_day)
    return old_result
        
def convert_itinerary(old_itinerary, people_number, start_city, target_city, earliest_result, lastest_result, env, transport_name, days, restaurant_db, attraction_db, restaurant_query, attraction_query):
    new_itinerary = {
        "people_number": people_number,  
        "start_city": start_city,  
        "target_city": target_city, 
        "itinerary": []
    }
    old_itinerary = dict(sorted(old_itinerary.items(), key=lambda x: x[0]))
    visited_restaurants = set()
    last_day_end_activity_name = None
    start_time = None
    for day_index, (date, activities) in enumerate(old_itinerary.items(), start=1):
        day_plan = {
            "day": day_index,
            "activities": []
        }
        if day_index == 1:
            try:
                day_plan_flight_to = {
                            "start_time": earliest_result["BeginTime"],
                            "end_time": earliest_result["EndTime"],
                            "start": earliest_result["From"],
                            "end": earliest_result["To"],
                            "price": earliest_result["Cost"],
                            "cost": earliest_result["Cost"] * people_number,
                            "FlightID": earliest_result["FlightID"],
                            "type": "airplane",
                            "tickets": people_number,
                            "transports": []
                        }
                previous_end = earliest_result["To"]
                previous_end_time = earliest_result["EndTime"]
                day_plan["activities"].append(day_plan_flight_to)
            except:
                day_plan_train_to = {
                            "start_time": earliest_result["BeginTime"],
                            "end_time": earliest_result["EndTime"],
                            "start": earliest_result["From"],
                            "end": earliest_result["To"],
                            "price": earliest_result["Cost"],
                            "cost": earliest_result["Cost"] * people_number,
                            "TrainID": earliest_result["TrainID"],
                            "type": "train",
                            "tickets": people_number,
                            "transports": []
                        }
                previous_end = earliest_result["To"]
                previous_end_time = earliest_result["EndTime"]
                day_plan["activities"].append(day_plan_train_to)
        else:
            previous_end_time = "07:00"

        j = 0
        
        for activity in activities:
            j += 1 
            transport = []

            constrainted = Constraint_result(None)
            transport_result_final = transport_result(transport_name, target_city, previous_end, activity["name"], previous_end_time, env, people_number)
            for i in range(len(transport_result_final)):
                if transport_result_final[i]["mode"]=="taxi":
                    transport_new = {
                        "start": transport_result_final[i]["start"],
                        "end": transport_result_final[i]["end"],
                        "mode": transport_result_final[i]["mode"],
                        "start_time": transport_result_final[i]["start_time"],
                        "end_time":  transport_result_final[i]["end_time"],
                        "price": transport_result_final[i]["price"],
                        "cost": transport_result_final[i]["price"] * math.ceil(people_number / 4),
                        "distance": transport_result_final[i]["distance"],
                        "cars": math.ceil(people_number / 4)
                    }
                else:
                    transport_new = {
                        "start": transport_result_final[i]["start"],
                        "end": transport_result_final[i]["end"],
                        "mode": transport_result_final[i]["mode"],
                        "start_time": transport_result_final[i]["start_time"],
                        "end_time":  transport_result_final[i]["end_time"],
                        "price": transport_result_final[i]["price"],
                        "cost": transport_result_final[i]["cost"],
                        "distance": transport_result_final[i]["distance"],
                        "tickets": people_number
                    }
                transport.append(transport_new)
            previous_end = activity["name"]
            previous_end_time = transport_result_final[-1]["end_time"]  
            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
            flag = True
            flag_pre = True
            arrival_must = None
            end_must = None
            activity_type = "attraction"
            price = 0
            if activity["type"]=="scenic" or activity["type"]!="meal":
                activity_type = "attraction"
                matched_row = [entry for entry in attraction_db if entry['name'] == activity["name"]]
                if matched_row[0]["endtime"] < matched_row[0]["opentime"]:
                    matched_row[0]["endtime"]="23:59"
                if matched_row[0]["endtime"] == "24:00":
                    matched_row[0]["endtime"]="23:59"
                if attraction_query["must_attraction_name"] != []:
                    attraction = attraction_query["must_attraction_name"]
                else:
                    attraction = []
                price = matched_row[0]["price"]
                if transport_result_final[i]["end_time"] >= "22:30" or end_time < previous_end_time:
                    flag = False
                elif matched_row[0]["name"] in attraction and datetime.strptime(end_time, "%H:%M").time() > datetime.strptime(matched_row[0]["endtime"], "%H:%M").time():
                    flag_pre = False
                elif datetime.strptime(previous_end_time, "%H:%M").time() > datetime.strptime(matched_row[0]["endtime"], "%H:%M").time() or datetime.strptime(end_time, "%H:%M").time() > datetime.strptime(matched_row[0]["endtime"], "%H:%M").time():
                    flag = False
                elif activity["departure_time"] == activity["arrival_time"]:
                    flag = False
            elif activity["type"]=="meal":
                activity_type = activity["meal_slot"]
                price = activity["price"]
                if activity["name"] in visited_restaurants:
                    flag = False
                elif activity["name"] == restaurant_query["restaurant_stay_time"]["must_restaurant_name"]:
                    if restaurant_query["restaurant_stay_time"]["arrival"] is not None:
                        if restaurant_query["restaurant_stay_time"]["arrival"] < datetime.strptime(transport_result_final[-1]["end_time"], "%H:%M"):
                            flag_pre = False
                        previous_end_time = restaurant_query["restaurant_stay_time"]["arrival"].strftime("%H:%M")
                        arrival_must = previous_end_time
                        if restaurant_query["restaurant_stay_time"]["depature"] is not None:
                            end_time = restaurant_query["restaurant_stay_time"]["depature"]
                            end_must = end_time
                        else:
                            if isinstance(previous_end_time, str):
                                end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                                end_must = end_time
                            else:
                                previous_end_time = str(previous_end_time)
                                arrival_must = previous_end_time
                                try:
                                    end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                                    end_must = end_time
                                except:
                                    end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%Y-%m-%d %H:%M:%S")).strftime("%H:%M")
                                    end_must = end_time
                    elif restaurant_query["restaurant_stay_time"]["depature"] is not None:
                        if restaurant_query["restaurant_stay_time"]["depature"] > end_time:
                            end_time = restaurant_query["restaurant_stay_time"]["depature"]
                    else:
                        end_time = (timedelta(hours=int(restaurant_query["restaurant_stay_time"]["time"]) / 60) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        end_must = end_time
                elif activity["meal_slot"] == "breakfast":
                    found_item = next((item for item in restaurant_db if item.get("name") == activity["name"]), None)
                    if found_item["endtime"] < found_item["opentime"]:
                        flag = False
                    if activity["arrival_time"] >= "06:00" and end_time <= "09:00":
                        if found_item["opentime"] > datetime.strptime(activity["arrival_time"], "%H:%M").time() and datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() < found_item["opentime"]:
                            previous_end_time = found_item["opentime"].strftime("%H:%M")
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        elif datetime.strptime(end_time, "%H:%M").time() > found_item["endtime"]:
                            end_time = found_item["endtime"].strftime("%H:%M")
                        elif datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() > found_item["opentime"]:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        else:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    elif activity["arrival_time"] <= "06:00" and transport_result_final[i]["end_time"] < activity["arrival_time"]:
                        previous_end_time = "06:00"
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    elif activity["arrival_time"] >= "06:00" and end_time >= "09:00":
                        end_time = "09:00"
                    else:
                        previous_end_time = found_item["opentime"].strftime("%H:%M")
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    if transport_result_final[i]["end_time"] >= "09:00":
                        flag = False
                    visited_restaurants.add(activity["name"])
                elif activity["meal_slot"] == "lunch":
                    found_item = next((item for item in restaurant_db if item.get("name") == activity["name"]), None)
                    if found_item["endtime"] < found_item["opentime"]:
                        flag = False
                    if activity["arrival_time"] >= "11:00" and end_time <= "14:00":
                        if found_item["opentime"] >= datetime.strptime(activity["arrival_time"], "%H:%M").time() and datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() < found_item["opentime"]:
                            previous_end_time = found_item["opentime"].strftime("%H:%M")
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        elif datetime.strptime(end_time, "%H:%M").time() > found_item["endtime"]:
                            end_time = found_item["endtime"].strftime("%H:%M")
                        elif datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() > found_item["opentime"]:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        else:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    elif activity["arrival_time"] <= "11:00" and transport_result_final[i]["end_time"] < activity["arrival_time"]:
                        previous_end_time = "11:00"
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    else:
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    if transport_result_final[i]["end_time"] >= "14:00":
                        flag = False
                    visited_restaurants.add(activity["name"])
                else:
                    found_item = next((item for item in restaurant_db if item.get("name") == activity["name"]), None)
                    if found_item["endtime"] < found_item["opentime"]:
                        flag = False
                    if activity["arrival_time"] >= "17:00" and end_time <= "20:00":
                        if found_item["opentime"] > datetime.strptime(activity["arrival_time"], "%H:%M").time() and datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() < found_item["opentime"]:
                            previous_end_time = found_item["opentime"].strftime("%H:%M")
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        elif datetime.strptime(end_time, "%H:%M").time() > found_item["endtime"]:
                            end_time = found_item["endtime"].strftime("%H:%M")
                        elif datetime.strptime(transport_result_final[i]["end_time"], "%H:%M").time() > found_item["opentime"]:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                        else:
                            previous_end_time = transport_result_final[i]["end_time"]
                            end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    elif activity["arrival_time"] <= "17:00" and transport_result_final[i]["end_time"] < activity["arrival_time"]:
                        previous_end_time = "17:00"
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    else:
                        previous_end_time = transport_result_final[i]["end_time"]
                        end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                    if transport_result_final[i]["end_time"] >= "20:00":
                        flag = False
                    visited_restaurants.add(activity["name"])
            if isinstance(previous_end_time, datetime):
                previous_end_time = previous_end_time.strftime("%H:%M")
            else:
                try:
                    previous_end_time = datetime.strptime(previous_end_time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
                except:
                    previous_end_time = datetime.strptime(previous_end_time, "%H:%M").strftime("%H:%M")

            previous_end_time_1 = previous_end_time
            if isinstance(previous_end_time, str):
                previous_end_time_1 = datetime.strptime(previous_end_time, "%H:%M")
            if datetime.strptime(activity["arrival_time"], "%H:%M") > previous_end_time_1 and flag_pre:
                previous_end_time = activity["arrival_time"]
                end_time = activity["departure_time"]
            if activity["name"] in restaurant_query["must_restaurant_name"] and not flag:
                flag = True
                flag_pre = False
            if not flag_pre:
                day_plan["activities"].pop()
                if previous_end_time_1 < datetime.strptime(day_plan["activities"][-1]["end_time"], "%H:%M"):
                    day_plan["activities"].pop()
                if (day_plan["activities"][-1]["position"] != activity["name"]):
                    transport = []
                    transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]["position"], activity["name"], day_plan["activities"][-1]["end_time"], env, people_number)
                else:
                    print("Duplicate detected!")
                    day_plan["activities"].pop()
                for i in range(len(transport_result_final)):
                    if transport_result_final[i]["mode"]=="taxi":
                        transport_new = {
                            "start": transport_result_final[i]["start"],
                            "end": transport_result_final[i]["end"],
                            "mode": transport_result_final[i]["mode"],
                            "start_time": transport_result_final[i]["start_time"],
                            "end_time":  transport_result_final[i]["end_time"],
                            "price": transport_result_final[i]["price"],
                            "cost": transport_result_final[i]["price"] * math.ceil(people_number / 4),
                            "distance": transport_result_final[i]["distance"],
                            "cars": math.ceil(people_number / 4)
                        }
                    else:
                        transport_new = {
                            "start": transport_result_final[i]["start"],
                            "end": transport_result_final[i]["end"],
                            "mode": transport_result_final[i]["mode"],
                            "start_time": transport_result_final[i]["start_time"],
                            "end_time":  transport_result_final[i]["end_time"],
                            "price": transport_result_final[i]["price"],
                            "cost": transport_result_final[i]["cost"],
                            "distance": transport_result_final[i]["distance"],
                            "tickets": people_number
                        }
                    transport.append(transport_new)
                if arrival_must is None and end_must is None:
                    previous_end_time = transport_result_final[-1]["end_time"]
                    end_time = (timedelta(hours=activity["travel_time"] / 3600) + datetime.strptime(previous_end_time, "%H:%M")).strftime("%H:%M")
                else:
                    previous_end_time = arrival_must
                    end_time = end_must
                flag_pre = True

            if flag:
                formatted_activity = {
                    "position": activity["name"],
                    "type": activity_type,
                    "transports": transport,
                    "price": price,
                    "cost": price * people_number,
                    "tickets": new_itinerary["people_number"],
                    "start_time": str(previous_end_time),
                    "end_time": str(end_time)
                }
                previous_end_time = formatted_activity["end_time"]
                day_plan["activities"].append(formatted_activity)
            else:
                previous_end = transport_result_final[0]["start"]
                previous_end_time = transport_result_final[0]["start_time"]
        
        if day_index == days and j == len(activities):
            try:
                print("lastest_result:", lastest_result)
                transport = []
                start_time = lastest_result["BeginTime"]
                while day_plan["activities"] != [] and lastest_result["BeginTime"] < day_plan["activities"][-1]["end_time"]:
                    if day_plan["activities"] != []:
                        day_plan["activities"].pop()
                if day_plan["activities"] == []:
                    transport_result_final = transport_result(transport_name, target_city, last_day_end_activity_name, lastest_result["From"], "00:00", env, people_number)
                    print(transport_result_final)
                elif 'position' not in day_plan["activities"][-1]:
                    transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['end'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                else:
                    transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['position'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                while lastest_result["BeginTime"] < transport_result_final[-1]["end_time"]:
                    day_plan["activities"].pop()
                    try:
                        transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['position'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                    except:
                        transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['end'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                for i in range(len(transport_result_final)):
                    if transport_result_final[i]["mode"]=="taxi":
                        transport_new = {
                            "start": transport_result_final[i]["start"],
                            "end": transport_result_final[i]["end"],
                            "mode": transport_result_final[i]["mode"],
                            "start_time": transport_result_final[i]["start_time"],
                            "end_time":  transport_result_final[i]["end_time"],
                            "price": transport_result_final[i]["price"],
                            "cost": transport_result_final[i]["price"] * math.ceil(people_number/4),
                            "distance": transport_result_final[i]["distance"],
                            "cars": math.ceil(people_number/4)
                        }
                    else:
                        transport_new = {
                            "start": transport_result_final[i]["start"],
                            "end": transport_result_final[i]["end"],
                            "mode": transport_result_final[i]["mode"],
                            "start_time": transport_result_final[i]["start_time"],
                            "end_time":  transport_result_final[i]["end_time"],
                            "price": transport_result_final[i]["price"],
                            "cost": transport_result_final[i]["cost"],
                            "distance": transport_result_final[i]["distance"],
                            "tickets": people_number
                        }
                    transport.append(transport_new)
                day_plan_flight_back = {
                            "start_time": lastest_result["BeginTime"],
                            "end_time": lastest_result["EndTime"],
                            "start": lastest_result["From"],
                            "end": lastest_result["To"],
                            "price": lastest_result["Cost"],
                            "cost": lastest_result["Cost"] * people_number,
                            "FlightID": lastest_result["FlightID"],
                            "type": "airplane",
                            "tickets": people_number,
                            "transports": transport
                        }
                day_plan["activities"].append(day_plan_flight_back)
            except:
                transport = []
                try:
                    start_time = lastest_result["BeginTime"]
                    while day_plan["activities"] != [] and lastest_result["BeginTime"] < day_plan["activities"][-1]["end_time"]:
                        if day_plan["activities"] != []:
                            day_plan["activities"].pop()
                    try:
                        if day_plan["activities"] == []:
                            transport_result_final = transport_result(transport_name, target_city, last_day_end_activity_name, lastest_result["From"], "00:00", env, people_number)
                            print(transport_result_final)
                        elif 'position' not in day_plan["activities"][-1]:
                            transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['end'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                        else:
                            transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['position'], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                    except:
                        transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['end'], lastest_result["From"], day_plan["activities"][-1]['end_time'], env, people_number)
                        if transport_result_final == [] and day_plan["activities"][-1]['end'] == lastest_result["From"]:
                            transport_final = {
                            "start": day_plan["activities"][-1]['end'],
                            "end": day_plan["activities"][-1]['end'],
                            "mode": "walk",
                            "start_time": day_plan["activities"][-1]['end_time'],
                            "end_time": day_plan["activities"][-1]['end_time'],
                            "price": 0,
                            "cost": 0,
                            "distance": 0.0,
                            "tickets": people_number}
                            day_plan_train_back = {
                                    "start_time": lastest_result["BeginTime"],
                                    "end_time": lastest_result["EndTime"],
                                    "start": lastest_result["From"],
                                    "end": lastest_result["To"],
                                    "price": lastest_result["Cost"],
                                    "cost": lastest_result["Cost"] * people_number,
                                    "TrainID": lastest_result["TrainID"],
                                    "type": "train",
                                    "tickets": people_number,
                                    "transports": [transport_final]
                                }
                            day_plan["activities"].append(day_plan_train_back) 
                            new_itinerary["itinerary"].append(day_plan)   
                            return new_itinerary
                    while lastest_result["BeginTime"] < transport_result_final[-1]["end_time"]:
                        day_plan["activities"].pop()
                        try:
                            transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['position'], lastest_result["From"], day_plan["activities"][-1]['end_time'], env, people_number)
                        except:
                            transport_result_final = transport_result(transport_name, target_city, day_plan["activities"][-1]['end'], lastest_result["From"], day_plan["activities"][-1]['end_time'], env, people_number)
                    for i in range(len(transport_result_final)):
                        if transport_result_final[i]["mode"] == "taxi":
                            transport_new = {
                                "start": transport_result_final[i]["start"],
                                "end": transport_result_final[i]["end"],
                                "mode": transport_result_final[i]["mode"],
                                "start_time": day_plan["activities"][-1]['end_time'],
                                "end_time":  transport_result_final[i]["end_time"],
                                "price": transport_result_final[i]["price"],
                                "cost": transport_result_final[i]["price"] * math.ceil(people_number / 4),
                                "distance": transport_result_final[i]["distance"],
                                "cars": math.ceil(people_number / 4)
                            }
                        else:
                            transport_new = {
                                "start": transport_result_final[i]["start"],
                                "end": transport_result_final[i]["end"],
                                "mode": transport_result_final[i]["mode"],
                                "start_time": transport_result_final[i]["start_time"],
                                "end_time":  transport_result_final[i]["end_time"],
                                "price": transport_result_final[i]["price"],
                                "cost": transport_result_final[i]["cost"],
                                "distance": transport_result_final[i]["distance"],
                                "tickets": people_number
                            }
                        transport.append(transport_new)
                    day_plan_train_back = {
                                "start_time": lastest_result["BeginTime"],
                                "end_time": lastest_result["EndTime"],
                                "start": lastest_result["From"],
                                "end": lastest_result["To"],
                                "price": lastest_result["Cost"],
                                "cost": lastest_result["Cost"] * people_number,
                                "TrainID": lastest_result["TrainID"],
                                "type": "train",
                                "tickets": people_number,
                                "transports": transport
                            }
                except:
                    try:
                        transport_result_final = transport_result(transport_name, target_city, new_itinerary["itinerary"][-1]['activities'][-1]["position"], lastest_result["From"], "07:00", env, people_number)
                    except:
                        transport_result_final = transport_result(transport_name, target_city, new_itinerary["itinerary"][-1]['activities'][-1]["end"], lastest_result["From"], day_plan["activities"][-1]["end_time"], env, people_number)
                    for i in range(len(transport_result_final)):
                        if transport_result_final[i]["mode"] == "taxi":
                            transport_new = {
                                "start": transport_result_final[i]["start"],
                                "end": transport_result_final[i]["end"],
                                "mode": transport_result_final[i]["mode"],
                                "start_time": "07:00",
                                "end_time":  transport_result_final[i]["end_time"],
                                "price": transport_result_final[i]["price"],
                                "cost": transport_result_final[i]["price"] * math.ceil(people_number / 4),
                                "distance": transport_result_final[i]["distance"],
                                "cars": math.ceil(people_number / 4)
                            }
                        else:
                            transport_new = {
                                "start": transport_result_final[i]["start"],
                                "end": transport_result_final[i]["end"],
                                "mode": transport_result_final[i]["mode"],
                                "start_time": transport_result_final[i]["start_time"],
                                "end_time":  transport_result_final[i]["end_time"],
                                "price": transport_result_final[i]["price"],
                                "cost": transport_result_final[i]["cost"],
                                "distance": transport_result_final[i]["distance"],
                                "tickets": people_number
                            }
                        transport.append(transport_new)
                    day_plan_train_back = {
                                "start_time": lastest_result["BeginTime"],
                                "end_time": lastest_result["EndTime"],
                                "start": lastest_result["From"],
                                "end": lastest_result["To"],
                                "price": lastest_result["Cost"],
                                "cost": lastest_result["Cost"] * people_number,
                                "TrainID": lastest_result["TrainID"],
                                "type": "train",
                                "tickets": people_number,
                                "transports": transport
                            }
                day_plan["activities"].append(day_plan_train_back)
        if day_index != 1 and day_index != days: 
            last_day_end_activity_name = activities[-1]["name"]
        new_itinerary["itinerary"].append(day_plan)   
    new_itinerary = add_big_traffic(new_itinerary, days, lastest_result, env, people_number)
    return new_itinerary    

def calculate_time_difference(start_time_str, end_time_str):
    time_format = "%H:%M"
    start_time = datetime.strptime(start_time_str, time_format)
    end_time = datetime.strptime(end_time_str, time_format)
    time_difference = end_time - start_time
    difference_in_minutes = time_difference.total_seconds() / 60
    return difference_in_minutes

def add_minutes_to_time(time_str, minutes_to_add):
    time_format = "%H:%M"
    time_object = datetime.strptime(time_str, time_format)
    new_time_object = time_object + timedelta(minutes=minutes_to_add)
    new_time_str = new_time_object.strftime(time_format)
    return new_time_str

def final_format(old_itinerary, env, transport_name=["metro"], target_city="重庆", people_number=4, restaurants_db=None):
    for i in range(len(old_itinerary['itinerary'])-1):
        final_name = old_itinerary['itinerary'][i]["activities"][-1]["position"]
        try:
            first_name = old_itinerary['itinerary'][i+1]["activities"][0]["position"]
            start_time = old_itinerary['itinerary'][i+1]["activities"][0]["start_time"]
        except:
            first_name = old_itinerary['itinerary'][i+1]["activities"][0]["start"]
            start_time_str = old_itinerary['itinerary'][i+1]["activities"][0]["start_time"]
            print("start_time_str:", start_time_str)
            start_time = parse_time_string(start_time_str)
            if start_time > parse_time_string("20:00"):
                start_time = "07:00"
            else:
                transport_result_final = transport_result(transport_name, target_city, final_name, first_name, start_time, env, people_number)
                first_transport_start = parse_time_string(transport_result_final[0]["start_time"])
                last_transport_end = parse_time_string(transport_result_final[-1]["end_time"])
                time_gap = last_transport_end - first_transport_start
                start_time = start_time - timedelta(hours=time_gap.seconds // 3600, minutes=(time_gap.seconds // 60) % 60)
                start_time = start_time.strftime("%H:%M")
                print("start_time:", start_time)
        type = old_itinerary['itinerary'][i+1]["activities"][0]["type"]
        price = old_itinerary['itinerary'][i+1]["activities"][0]["price"]
        cost = old_itinerary['itinerary'][i+1]["activities"][0]["cost"]
        tickets = old_itinerary['itinerary'][i+1]["activities"][0]["tickets"]
        interval = calculate_time_difference(old_itinerary['itinerary'][i+1]["activities"][0]["start_time"], old_itinerary['itinerary'][i+1]["activities"][0]["end_time"])
        transport = []
        transport_result_final = transport_result(transport_name, target_city, final_name, first_name, start_time, env, people_number)
        for j in range(len(transport_result_final)):
            if transport_result_final[j]["mode"]=="taxi":
                transport_new = {
                    "start": transport_result_final[j]["start"],
                    "end": transport_result_final[j]["end"],
                    "mode": transport_result_final[j]["mode"],
                    "start_time": transport_result_final[j]["start_time"],
                    "end_time":  transport_result_final[j]["end_time"],
                    "price": transport_result_final[j]["price"],
                    "cost": transport_result_final[j]["price"] * math.ceil(people_number/4),
                    "distance": transport_result_final[j]["distance"],
                    "cars": math.ceil(people_number/4)
                }
            else:
                transport_new = {
                    "start": transport_result_final[j]["start"],
                    "end": transport_result_final[j]["end"],
                    "mode": transport_result_final[j]["mode"],
                    "start_time": transport_result_final[j]["start_time"],
                    "end_time":  transport_result_final[j]["end_time"],
                    "price": transport_result_final[j]["price"],
                    "cost": transport_result_final[j]["cost"],
                    "distance": transport_result_final[j]["distance"],
                    "tickets": people_number
                }
            transport.append(transport_new)
        last_last_time = add_minutes_to_time(transport[-1]["end_time"], interval)
        if "position" in old_itinerary["itinerary"][i+1]["activities"][0]:
            old_itinerary['itinerary'][i+1]["activities"][0] = {
                    "position": first_name,
                    "type": type,
                    "transports": transport,
                    "price": price,
                    "cost": cost,
                    "tickets": tickets,
                    "start_time": transport[-1]["end_time"],
                    "end_time": last_last_time
                }
        else:
            try:
                old_itinerary['itinerary'][i+1]["activities"][0] = {
                        "start": first_name,
                        "end": old_itinerary['itinerary'][i+1]["activities"][0]["end"],
                        "type": type,
                        "transports": transport,
                        "FlightID": old_itinerary['itinerary'][i+1]["activities"][0]["FlightID"],
                        "price": price,
                        "cost": cost,
                        "tickets": tickets,
                        "start_time": old_itinerary['itinerary'][i+1]["activities"][0]["start_time"],
                        "end_time": old_itinerary['itinerary'][i+1]["activities"][0]["end_time"]
                    }
            except:
                old_itinerary['itinerary'][i+1]["activities"][0] = {
                        "start": first_name,
                        "end": old_itinerary['itinerary'][i+1]["activities"][0]["end"],
                        "type": type,
                        "transports": transport,
                        "TrainID": old_itinerary['itinerary'][i+1]["activities"][0]["TrainID"],
                        "price": price,
                        "cost": cost,
                        "tickets": tickets,
                        "start_time": old_itinerary['itinerary'][i+1]["activities"][0]["start_time"],
                        "end_time": old_itinerary['itinerary'][i+1]["activities"][0]["end_time"]
                    }
    return old_itinerary

def format_results(old_itinerary, delete_attraction_result, transport_name, target_city, env, people_number):
    delete_names = set()
    modify_dict = {}
    for item in delete_attraction_result:
        if item['change'] is None:
            delete_names.add(item['name'])
        else:
            modify_dict[item['name']] = item['change']

    for day in old_itinerary['itinerary']:
        activities = day['activities']
        i = 0
        while i < len(activities):
            act = activities[i]
            if act.get('type') == 'attraction':
                pos = act.get('position')
                if pos in delete_names:
                    activities.pop(i)
                    if 0 < i < len(activities):
                        prev = activities[i-1]
                        curr = activities[i]
                        new_transports = transport_result(
                            transport_name, target_city,
                            prev.get('position', prev.get('end')),
                            curr.get('position', curr.get('start')),
                            prev['end_time'],
                            env=env, people_number=people_number
                        )
                        curr['transports'] = new_transports
                    continue
                elif pos in modify_dict:
                    new_pos = modify_dict[pos]
                    act['position'] = new_pos
                    if i > 0:
                        prev = activities[i-1]
                        new_transports = transport_result(
                            transport_name, target_city,
                            prev.get('position', prev.get('end')),
                            new_pos,
                            prev['end_time'],
                            env=env, people_number=people_number
                        )
                        act['transports'] = new_transports
                    if i+1 < len(activities):
                        next_act = activities[i+1]
                        new_transports = transport_result(
                            transport_name, target_city,
                            new_pos,
                            next_act.get('position', next_act.get('start')),
                            act['end_time'],
                            env=env, people_number=people_number
                        )
                        next_act['transports'] = new_transports
            i += 1
    return old_itinerary

from datetime import datetime, timedelta

def parse_time_string(time_str):
    return datetime.strptime(time_str, "%H:%M")

def time_in_range(start, end, current):
    fmt = "%H:%M"
    start = datetime.strptime(start, fmt)
    end = datetime.strptime(end, fmt)
    current = datetime.strptime(current, fmt)
    return start <= current <= end

def fix_meal_time(activity, prev_end, next_start):
    meal_type = activity["type"]
    time_ranges = {
        "breakfast": ("06:00", "09:00"),
        "lunch": ("11:00", "14:00"),
        "dinner": ("17:00", "20:00"),
    }
    if meal_type not in time_ranges:
        return activity

    fmt = "%H:%M"
    start, end = time_ranges[meal_type]
    duration = (
        datetime.strptime(activity["end_time"], fmt) - datetime.strptime(activity["start_time"], fmt)
    )
    earliest = max(datetime.strptime(start, fmt), datetime.strptime(prev_end, fmt))
    latest = min(datetime.strptime(end, fmt) - duration, datetime.strptime(next_start, fmt) - duration)
    if earliest <= latest:
        new_start = earliest
        new_end = earliest + duration
        activity["start_time"] = new_start.strftime(fmt)
        activity["end_time"] = new_end.strftime(fmt)
    return activity

from datetime import datetime, timedelta

def subtract_minutes_from_time(time_str, minutes):
    try:
        time_obj = datetime.strptime(time_str, "%H:%M")
        new_time = time_obj - timedelta(minutes=minutes)
        if new_time.day != time_obj.day:
            return "00:00"
        return new_time.strftime("%H:%M")
    except ValueError:
        return time_str

def add_minutes_to_time(time_str, minutes):
    try:
        time_obj = datetime.strptime(time_str, "%H:%M")
        new_time = time_obj + timedelta(minutes=minutes)
        if new_time.day != time_obj.day:
            return "23:59"
        return new_time.strftime("%H:%M")
    except ValueError:
        return time_str

def calculate_time_difference(start_time, end_time):
    try:
        if isinstance(start_time, str):
            start = datetime.strptime(start_time, "%H:%M")
        else:
            start = start_time
        if isinstance(end_time, str):
            end = datetime.strptime(end_time, "%H:%M")
        else:
            end = end_time
        diff = end - start
        minutes = diff.total_seconds() / 60
        if minutes < 0:
            minutes += 24 * 60
        return int(minutes)
    except ValueError:
        return 0

def compare_times(time1, time2):
    try:
        t1 = datetime.strptime(time1, "%H:%M")
        t2 = datetime.strptime(time2, "%H:%M")
        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        return 0
    except ValueError:
        return 0
    
def fix_all_meal_times(itinerary):
    meal_times = {
        "breakfast": ("06:00", "09:00"),
        "lunch": ("11:00", "14:00"),
        "dinner": ("17:00", "20:00")
    }
    
    for day in itinerary["itinerary"]:
        activities = day["activities"]
        to_delete = []
        
        for i, activity in enumerate(activities):
            if activity["type"] in meal_times:
                meal_type = activity["type"]
                valid_start, valid_end = meal_times[meal_type]
                
                prev_end = "00:00" if i == 0 else activities[i-1]["end_time"]
                next_start = "24:00" if i == len(activities)-1 else activities[i+1]["start_time"]
                
                duration = calculate_time_difference(activity["start_time"], activity["end_time"])
                
                latest_possible_start = subtract_minutes_from_time(valid_end, duration)
                actual_start = max_time(valid_start, prev_end)
                actual_end = min_time(latest_possible_start, next_start)
                
                if compare_times(actual_start, actual_end) <= 0:
                    new_start = actual_start
                    new_end = add_minutes_to_time(new_start, duration)
                    
                    activity["start_time"] = new_start
                    activity["end_time"] = new_end
                else:
                    to_delete.append(i)
                    
        for idx in reversed(to_delete):
            del activities[idx]
    
    return itinerary

def fix_transport_times(itinerary):
    for day in itinerary["itinerary"]:
        activities = day["activities"]
        for i in range(1, len(activities)):
            prev_act = activities[i-1]
            curr_act = activities[i]
            if "transports" in curr_act and curr_act["transports"]:
                transport = curr_act["transports"][0]
                if compare_times(transport["start_time"], prev_act["end_time"]) < 0:
                    duration = calculate_time_difference(transport["start_time"], transport["end_time"])
                    transport["start_time"] = prev_act["end_time"]
                    transport["end_time"] = add_minutes_to_time(transport["start_time"], duration)
    return itinerary

def max_time(t1, t2):
    return t1 if compare_times(t1, t2) >= 0 else t2

def min_time(t1, t2):
    return t1 if compare_times(t1, t2) <= 0 else t2

a = collect_innercity_transport(city="深圳", start="招商蛇口邮轮母港游览", end="深圳湾秋果S1979酒店", start_time="20:41", env=WorldEnv(), people_number=3, trans_type="taxi")
print(a)