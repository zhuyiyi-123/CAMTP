import json, sys, argparse, re
import pandas as pd
import copy
from datetime import datetime, timedelta
from pypinyin import lazy_pinyin
from chinatravel.environment.world_env import WorldEnv
from chinatravel.symbol_verification.hard_constraint import evaluate_constraints_py

project_root_path = "."
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)

from agent.tpc_agent.hotel import HotelPlanner, csv_to_hotel_db
from agent.tpc_agent.format import convert_itinerary, final_format, format_results

def fix_final_json(all_constraint, backbone_llm, nature_language, planned_itinerary, query, env, transport_name, start_citys, hotel_query, json_load, attraction_query,restaurant_query):
    print(all_constraint)  
    delete_attraction_result = []
    add_attraction_result = []
    change_hotel_result = []
    change_delete_hotel_result = []
    target_places = []
    target_attraction_type = []
    target_restaurant_type = []
    print(attraction_query)
    print(restaurant_query)
    for name in attraction_query["must_attraction_name"]:
        target_places.append(name)
    for name in restaurant_query["must_restaurant_name"]:
        target_places.append(name)
    for name in attraction_query["must_attraction_type"]:
        target_attraction_type.append(name)
    for name in restaurant_query["must_restaurant_type"]:
        target_restaurant_type.append(name)
    chengshi = query["target_city"]
    city_pingyin = ''.join(lazy_pinyin(chengshi))
    remain_attr_type, remain_rest_type = type_count(planned_itinerary, city_pingyin)
    lost_attr_type, lost_rest_type = [], []
    
    for constraint in all_constraint:
        if any(key in constraint and constraint[key] is not None for key in ["total_budget"]):
            upper_bound = constraint["total_budget"]
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            original_data = copy.deepcopy(planned_itinerary)
            try:
                planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
            except:
                planned_itinerary = original_data
            print("sum_cost",sum_costs(planned_itinerary))
        if any(key in constraint and constraint[key] is not None for key in ["restaurant_stop_name"]):
            if constraint["restaurant_stop_time_min"] is not None and constraint["restaurant_stop_time_min"] is None:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_min"])
            else:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_min"])
            if constraint["restaurant_stop_time_max"] is not None:
                planned_itinerary = late_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_max"], flag=1)
        
        if any(key in constraint and constraint[key] is not None for key in ["go_must_type"]):
            allowed_transport = constraint["go_must_type"]
            print(f"Applying outbound transportation constraint: {allowed_transport}")
            planned_itinerary = change_transport_new(planned_itinerary, all_constraint=allowed_transport)
        
        if any(key in constraint and constraint[key] is not None for key in ["back_must_type"]):
            allowed_transport = constraint["back_must_type"]
            print(f"Applying return-trip transportation constraint: {allowed_transport}")
            planned_itinerary = change_transport_new(planned_itinerary, all_constraint=allowed_transport)
    
        if any(key in constraint and constraint[key] is not None for key in ["must_not_attraction_type"]):
            attraction_names = [place["position"] for i in range(len(planned_itinerary['itinerary'])) for place in planned_itinerary['itinerary'][i]["activities"] if "type" in place and place["type"] == "attraction"]
            chengshi = query["target_city"]
            attraction_df = pd.read_csv(f"./chinatravel/environment/database/attractions/{''.join(lazy_pinyin(chengshi))}/attractions.csv", encoding="utf-8")
            types_list = attraction_df[attraction_df['name'].isin(attraction_names)]['type'].tolist()
            delete_attraction_result.append([attraction_names[i] for i, t in enumerate(types_list) if t in constraint["must_not_attraction_type"]])
        if any(key in constraint and constraint[key] is not None for key in ["must_attraction_type"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            attractions = pd.read_csv(f"./chinatravel/environment/database/attractions/{''.join(lazy_pinyin(chengshi))}/attractions.csv", encoding="utf-8")
            for attr_type in constraint["must_attraction_type"]:
                if attr_type not in remain_attr_type:
                    lost_attr_type.append(attr_type)
            for target_attr_type in lost_attr_type:
                target_place = attractions.loc[attractions["type"] == target_attr_type]
            for idx, place in enumerate(target_place["name"].values):
                try:
                    planned_itinerary = Interpolation_place(planned_itinerary, place, "attractions", city_pingyin, target_places)
                    break
                except:
                    continue
        if any(key in constraint and constraint[key] is not None for key in ["must_restaurant_type"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            restaurants = pd.read_csv(f"./chinatravel/environment/database/restaurants/{city_pingyin}/restaurants_{city_pingyin}.csv")
            for rest_type in constraint["must_restaurant_type"]:
                if rest_type not in remain_rest_type:
                    lost_rest_type.append(rest_type)
            for target_res_type in lost_rest_type:
                target_res_type = target_res_type.strip("'")               
                target_place = restaurants.loc[restaurants["cuisine"] == str(target_res_type)]
                target_place = target_place.sort_values(by="price", ascending=True)
                print(target_place)
            for idx, place in enumerate(target_place["name"].values):
                try:
                    planned_itinerary = Interpolation_place(planned_itinerary, place, "restaurants", city_pingyin, target_places)
                    print(planned_itinerary)
                    break
                except:
                    continue
        if any(key in constraint and constraint[key] is not None for key in ["must_attraction"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            cleaned_places = [place.strip("'") for place in constraint["must_attraction"]]
            for place in cleaned_places:
                print(place)
                planned_itinerary = Interpolation_place(planned_itinerary, place, "attractions", city_pingyin, target_places)

        if any(key in constraint and constraint[key] is not None for key in ["must_restaurant"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            cleaned_places = [place.strip("'") for place in constraint["must_restaurant"]]
            for place in cleaned_places:
                print(place)
                planned_itinerary = Interpolation_place(planned_itinerary, place, "restaurants", city_pingyin, target_places)

        if any(key in constraint and constraint[key] is not None for key in ["activity_stop_time"]):
            add_attraction_result.append(constraint)

        chengshi = query["target_city"]
        city_pingyin = ''.join(lazy_pinyin(chengshi))
        if any(key in constraint and constraint[key] is not None for key in ["inner_city_transportation_cost"]):
            upper_bound = float(constraint["inner_city_transportation_cost"])

            target_place = attraction_query["must_attraction_name"]
            print("Current total inner-city transportation cost:", sum_costs(planned_itinerary, 2), compute_total_transport_cost(planned_itinerary, query))
            planned_itinerary = change_transport(planned_itinerary, env)
            print("After changes, current total inner-city transportation cost:", compute_total_transport_cost(planned_itinerary, query))
            if compute_total_transport_cost(planned_itinerary, query) > upper_bound:
                print("Still over budget after changes; attractions will be removed next")
                original_data = copy.deepcopy(planned_itinerary)
                try:
                    planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
                except:
                    planned_itinerary = original_data
                print("After changes, current total inner-city transportation cost:", compute_total_transport_cost(planned_itinerary, query))

        if any(key in constraint and constraint[key] is not None for key in ["stop_name"]):
            if constraint["stop_time_min"] is not None:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["stop_name"], constraint["stop_time_min"])
                planned_itinerary = late_visit(planned_itinerary, env, constraint["stop_name"], constraint["stop_time_max"])
        if any(key in constraint and constraint[key] is not None for key in ["attraction_cost"]):
            upper_bound = float(constraint["attraction_cost"])
            original_data = copy.deepcopy(planned_itinerary)
            try:
                planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
            except:
                planned_itinerary = original_data
        if any(key in constraint and constraint[key] is not None for key in ["must_hotel_type"]):
            planner = HotelPlanner(
                itinerary=format,
                hotel_db=csv_to_hotel_db(f"./chinatravel/environment/database/accommodations/{start_citys}/accommodations.csv"),
                total_budget=hotel_query["accommodation_cost"],
                must_include=hotel_query["must_accommodation_name"],
                must_exclude=hotel_query["must_not_accommodation_name"],
                type_prefer=hotel_query["must_accommodation_type"],
                type_avoid=hotel_query["must_not_restaurant_type"],
                people_count=int(query["people_number"]),
                circle_distance = hotel_query["nearby_attractions"],
                transport_name=json_load["must_inner_city_transportation"],
                target_city = query["target_city"], 
                numbed = hotel_query["numbed"],
                count=hotel_query["count"],
                avgbudget=hotel_query["avgbudget"],
                env = WorldEnv(),
                query=attraction_query
            )
            print(f"Hotel Planner Details:\n"
            f"itinerary: {planner.itinerary}\n"
            f"hotel_db: {planner.hotel_db}\n"
            f"total_budget: {planner.total_budget}\n"
            f"must_include: {planner.must_include}\n"
            f"must_exclude: {planner.must_exclude}\n"
            f"type_prefer: {planner.type_prefer}\n"
            f"type_avoid: {planner.type_avoid}\n"
            f"people_count: {planner.people_count}\n"
            f"circle_distance: {planner.circle_distance}\n"
            f"transport_name: {planner.transport_name}\n"
            f"target_city: {planner.target_city}\n"
            f"numbed: {planner.numbed}")
            planned_itinerary = planner.plan_hotels()
            planned_itinerary = final_format(planned_itinerary, env, transport_name=json_load["transport"], target_city=query["target_city"], people_number=query["people_number"])    
        print(evaluate_constraints_py(query["hard_logic_py"], planned_itinerary, verbose=True))
        if all(evaluate_constraints_py(query["hard_logic_py"], planned_itinerary, verbose=True)):
            return planned_itinerary
    return planned_itinerary

def type_count(data, city_pingyin=None):
    plan = data["itinerary"]
    activity_pool = []
    attraction_type_count = {}
    restaurant_type_count = {}
    attractions = pd.read_csv(f"./chinatravel/environment/database/attractions/{city_pingyin}/attractions.csv")
    restaurants = pd.read_csv(f"./chinatravel/environment/database/restaurants/{city_pingyin}/restaurants_{city_pingyin}.csv")
    for day in plan:
        idx = day["day"]
        activities = day.get("activities", [])
        for activity in activities:
            activity["day"] = idx
            attraction_type = "非景点"
            restaurant_type = "非餐饮"
            activity_pool.append(activity)

            if activity["type"] == "attraction":
                attraction_type = attractions.loc[attractions["name"]==activity["position"]]["type"].item()
            if attraction_type_count.get(attraction_type) is None:
                attraction_type_count[attraction_type] = 1
            else:
                attraction_type_count[attraction_type] += 1

            if activity["type"] in ("breakfast", "lunch", "dinner"):
                restaurant_type = restaurants.loc[restaurants["name"]==activity["position"]]["cuisine"].item()
            if restaurant_type_count.get(restaurant_type) is None:
                restaurant_type_count[restaurant_type] = 1
            else:
                restaurant_type_count[restaurant_type] += 1

    return attraction_type_count, restaurant_type_count

def fix_final_json_v2(all_constraint, backbone_llm, nature_language, planned_itinerary, query, env, transport_name, start_citys, hotel_query, json_load, attraction_query,restaurant_query):

    delete_attraction_result = []
    add_attraction_result = []
    change_hotel_result = []
    change_delete_hotel_result = []
    target_places = []
    target_attraction_type = []
    target_restaurant_type = []
    redo_flag = 0
    for name in attraction_query["must_attraction_name"]:
        target_places.append(name)
    for name in restaurant_query["must_restaurant_name"]:
        target_places.append(name)
    for name in attraction_query["must_attraction_type"]:
        target_attraction_type.append(name)
    for name in restaurant_query["must_restaurant_type"]:
        target_restaurant_type.append(name)

    restaurant_contraints = {}
    hotel_contraints = {}

    for constraint in all_constraint:
        if any(key in constraint and constraint[key] is not None for key in ["total_budget"]):
            upper_bound = constraint["total_budget"]
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            original_data = copy.deepcopy(planned_itinerary)
            try:
                planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
            except:
                planned_itinerary = original_data

        if any(key in constraint and constraint[key] is not None for key in ["restaurant_stop_name"]):
            if constraint["restaurant_stop_time_min"] is not None and constraint["restaurant_stop_time_min"] is None:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_min"])
            else:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_min"])
            if constraint["restaurant_stop_time_max"] is not None:
                planned_itinerary = late_visit(planned_itinerary, env, constraint["restaurant_stop_name"], constraint["restaurant_stop_time_max"], flag=1)
        
        
        if any(key in constraint and constraint[key] is not None for key in ["go_must_type"]):
            allowed_transport = constraint["go_must_type"]
            print(f"Applying outbound transportation constraint: {allowed_transport}")
            planned_itinerary = change_transport_new(planned_itinerary, all_constraint=allowed_transport)
        
        if any(key in constraint and constraint[key] is not None for key in ["back_must_type"]):
            allowed_transport = constraint["back_must_type"]
            print(f"Applying return-trip transportation constraint: {allowed_transport}")
            planned_itinerary = change_transport_new(planned_itinerary, all_constraint=allowed_transport)
        
        if any(key in constraint and constraint[key] is not None for key in ["must_not_attraction_type"]):
            attraction_names = [place["position"] for i in range(len(planned_itinerary['itinerary'])) for place in planned_itinerary['itinerary'][i]["activities"] if "type" in place and place["type"] == "attraction"]
            chengshi = query["target_city"]
            attraction_df = pd.read_csv(f"./chinatravel/environment/database/attractions/{''.join(lazy_pinyin(chengshi))}/attractions.csv", encoding="utf-8")
            types_list = attraction_df[attraction_df['name'].isin(attraction_names)]['type'].tolist()
            delete_attraction_result.append([attraction_names[i] for i, t in enumerate(types_list) if t in constraint["must_not_attraction_type"]])
        if any(key in constraint and constraint[key] is not None for key in ["must_attraction_type"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            attractions = pd.read_csv(f"./chinatravel/environment/database/attractions/{''.join(lazy_pinyin(chengshi))}/attractions.csv", encoding="utf-8")
            for target_attr_type in constraint["must_attraction_type"]:
                target_place = attractions.loc[attractions["type"] == target_attr_type]
            for place in target_place:
                try:
                    planned_itinerary = Interpolation_place(planned_itinerary, place, "attractions", city_pingyin, target_places)
                    break
                except:
                    continue
        if any(key in constraint and constraint[key] is not None for key in ["must_restaurant_type"]):
            redo_flag = max(redo_flag, 1)
            restaurant_contraints["restaurantstype"] = constraint["must_restaurant_type"]
        if any(key in constraint and constraint[key] is not None for key in ["must_attraction"]):
            chengshi = query["target_city"]
            city_pingyin = ''.join(lazy_pinyin(chengshi))
            cleaned_places = [place.strip("'") for place in constraint["must_attraction"]]
            for place in cleaned_places:
                print(place)
                planned_itinerary = Interpolation_place(planned_itinerary, place, "attractions", city_pingyin, target_places)
        if any(key in constraint and constraint[key] is not None for key in ["must_restaurant"]):
            redo_flag = max(redo_flag, 1)
            restaurant_contraints["restaurants"] = constraint["must_restaurant"]
        if any(key in constraint and constraint[key] is not None for key in ["activity_stop_time"]):
            add_attraction_result.append(constraint)
        chengshi = query["target_city"]
        city_pingyin = ''.join(lazy_pinyin(chengshi))
        if any(key in constraint and constraint[key] is not None for key in ["inner_city_transportation_cost"]):
            upper_bound = float(constraint["inner_city_transportation_cost"])
            target_place = attraction_query["must_attraction_name"]
            print("Current total inner-city transportation cost:", sum_costs(planned_itinerary, 2), compute_total_transport_cost(planned_itinerary, query))
            planned_itinerary = change_transport(planned_itinerary, env)
            print("After changes, current total inner-city transportation cost:", compute_total_transport_cost(planned_itinerary, query))
            if compute_total_transport_cost(planned_itinerary, query) > upper_bound:
                print("Still over budget after changes; deleting attractions soon")
                original_data = copy.deepcopy(planned_itinerary)
                try:
                    planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
                except:
                    planned_itinerary = original_data
                print("After changes, current total inner-city transportation cost:", compute_total_transport_cost(planned_itinerary, query))
        if any(key in constraint and constraint[key] is not None for key in ["stop_name"]):
            if constraint["stop_time_min"] is not None:
                planned_itinerary = early_visit(planned_itinerary, env, constraint["stop_name"], constraint["stop_time_min"])
                planned_itinerary = late_visit(planned_itinerary, env, constraint["stop_name"], constraint["stop_time_max"])
        if any(key in constraint and constraint[key] is not None for key in ["attraction_cost"]):
            upper_bound = float(constraint["attraction_cost"])
            original_data = copy.deepcopy(planned_itinerary)
            try:
                planned_itinerary = reduce_cost(planned_itinerary, env, upper_bound, flag=2, target_place=target_places, target_attraction_type=target_attraction_type, target_restaurant_type=target_restaurant_type, city_pingyin=city_pingyin)
            except:
                planned_itinerary = original_data
        if any(key in constraint and constraint[key] is not None for key in ["must_hotel_type"]):
            redo_flag = max(redo_flag, 2)
            hotel_contraints["type"] = constraint["must_hotel_type"]
        if all(evaluate_constraints_py(query["hard_logic_py"], planned_itinerary, verbose=True)):
            return planned_itinerary, 999, restaurant_contraints, hotel_contraints
    return planned_itinerary, redo_flag, restaurant_contraints, hotel_contraints

def time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m

def minutes_to_time(m):
    h = m // 60
    m = m % 60
    return f"{h:02d}:{m:02d}"

def is_meal(activity):
    return activity["type"] in ("breakfast", "lunch", "dinner")

def get_meal_time_range(meal_type):
    if meal_type == "breakfast":
        return (6*60, 9*60)
    elif meal_type == "lunch":
        return (11*60, 14*60)
    elif meal_type == "dinner":
        return (17*60, 20*60)
    else:
        return (0, 24*60)

def update_itinerary_with_strict_meal_time(itinerary, constraint):
    stop_name = constraint["stop_name"]
    stop_time_min = constraint.get("stop_time_min")
    stop_time_max = constraint.get("stop_time_max")
    found = False

    for day in itinerary["itinerary"]:
        for idx, activity in enumerate(day["activities"]):
            if activity.get("position") == stop_name and not found:
                found = True
                orig_start = activity.get("start_time")
                orig_end = activity.get("end_time")
                if orig_start and orig_end:
                    duration = time_to_minutes(orig_end) - time_to_minutes(orig_start)
                else:
                    duration = None

                if stop_time_min is not None:
                    activity["start_time"] = stop_time_min
                    if stop_time_max is not None:
                        activity["end_time"] = stop_time_max
                    elif duration is not None:
                        activity["end_time"] = minutes_to_time(time_to_minutes(stop_time_min) + duration)
                else:
                    if stop_time_max is not None and duration is not None:
                        activity["end_time"] = stop_time_max
                        activity["start_time"] = minutes_to_time(time_to_minutes(stop_time_max) - duration)
                prev_end = activity["end_time"]

                if "transports" in activity and activity["transports"]:
                    for t in activity["transports"]:
                        t_duration = time_to_minutes(t["end_time"]) - time_to_minutes(t["start_time"])
                        t["start_time"] = minutes_to_time(time_to_minutes(activity["start_time"]) - t_duration)
                        t["end_time"] = activity["start_time"]

                j = idx + 1
                while j < len(day["activities"]):
                    next_activity = day["activities"][j]
                    prev_time = prev_end
                    if "transports" in next_activity and next_activity["transports"]:
                        for t in next_activity["transports"]:
                            t_duration = time_to_minutes(t["end_time"]) - time_to_minutes(t["start_time"])
                            t["start_time"] = prev_time
                            t["end_time"] = minutes_to_time(time_to_minutes(prev_time) + t_duration)
                            prev_time = t["end_time"]
                    orig_start = next_activity.get("start_time")
                    orig_end = next_activity.get("end_time")
                    if orig_start and orig_end:
                        duration = time_to_minutes(orig_end) - time_to_minutes(orig_start)
                    else:
                        duration = None
                    next_activity["start_time"] = prev_time
                    if duration is not None:
                        next_activity["end_time"] = minutes_to_time(time_to_minutes(prev_time) + duration)
                        prev_end = next_activity["end_time"]
                    else:
                        next_activity["end_time"] = None
                        prev_end = None

                    if is_meal(next_activity):
                        meal_start, meal_end = get_meal_time_range(next_activity["type"])
                        act_start = time_to_minutes(next_activity["start_time"])
                        if not (meal_start <= act_start < meal_end):
                            if j > 0 and not is_meal(day["activities"][j-1]):
                                day["activities"][j], day["activities"][j-1] = day["activities"][j-1], day["activities"][j]
                                j -= 1
                                continue
                            else:
                                next_activity["start_time"] = minutes_to_time(meal_start)
                                if duration is not None:
                                    next_activity["end_time"] = minutes_to_time(meal_start + duration)
                                    prev_end = next_activity["end_time"]
                                else:
                                    next_activity["end_time"] = None
                                    prev_end = None
                                if "transports" in next_activity and next_activity["transports"]:
                                    for t in next_activity["transports"]:
                                        t_duration = time_to_minutes(t["end_time"]) - time_to_minutes(t["start_time"])
                                        t["start_time"] = minutes_to_time(meal_start - t_duration)
                                        t["end_time"] = minutes_to_time(meal_start)
                    if prev_end and time_to_minutes(prev_end) > 24 * 60:
                        day["activities"] = day["activities"][:j]
                        break
                    j += 1
                break
        if found:
            break
    return itinerary

def find_activities_by_stop_name(itinerary, constraint):
    result = []
    stop_name = constraint["stop_name"]
    for day in itinerary["itinerary"]:
        for activity in day["activities"]:
            if activity.get("position") == stop_name:
                result.append(activity)

    return result

def adjust_itinerary_to_budget(itinerary, budget, query):
    for i in range(query["days"]):
        activities = itinerary['itinerary'][i]['activities']
        for activity in activities[:]:
            current_cost = compute_total_transport_cost(itinerary, query)
            if current_cost <= budget:
                return itinerary
            
            if activity['type'] == 'attraction':
                activity_cost = sum(transport.get('cost', 0) for transport in activity.get('transports', []))
                
                if activity_cost > 0:
                    activities.remove(activity)
    
    print("Adjusted itinerary to fit within budget.")
    return itinerary

def compute_total_transport_cost(itinerary, query):
    inner_city_transportation_cost = 0
    for i in range(query["days"]):
        for j in range(len(itinerary['itinerary'][i]["activities"])):
            for z in range(len(itinerary['itinerary'][i]["activities"][j]["transports"])):
                inner_city_transportation_cost += float(itinerary['itinerary'][i]["activities"][j]["transports"][z]["cost"])

    return inner_city_transportation_cost

def sum_costs(obj, flag=0):
    total = 0
    if isinstance(obj, dict):
        if 'cost' in obj:
            if flag == 1:
                if 'type' in obj:
                    if obj['type'] == 'accommodation' or obj['type'] == 'airplane' or obj['type'] == 'train':
                        total += obj['cost']
            elif flag == 2:
                if 'mode' in obj:
                    total += obj['cost']        
            elif flag == 3:
                if 'type' in obj:
                    if obj['type'] == 'attraction':
                        total += obj['cost']
            else:
                total += obj['cost']
        for value in obj.values():
            total += sum_costs(value, flag)
    elif isinstance(obj, list):
        for item in obj:
            total += sum_costs(item, flag)
    return total

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

def safe_parse_time(t):
    h, m = map(int, t.split(":"))
    return h >= 24

def change_transport(data, env):
    plan = data["itinerary"]
    people = data["people_number"]
    city = data["target_city"]
    for day in plan:
        activities = day.get("activities", [])
        for activity in activities:
            transport = activity.get("transports", [])
            visit_start_time = activity.get("start_time", [])
            if len(transport) == 0:
                continue
            start_time = transport[0]["start_time"]
            end_time = transport[0]["end_time"]
            start = transport[0]["start"]
            end = transport[0]["end"]
            mode = transport[0]["mode"]
            price = transport[0]["price"]
            cost = transport[0]["cost"]
            distance = transport[0]["distance"]
            if mode == "taxi":
                activity["transports"] = collect_innercity_transport(city, start, end, start_time, env, people, trans_type="walk")
            if safe_parse_time(activity["transports"][-1]["end_time"]) or datetime.strptime(activity["transports"][-1]["end_time"], "%H:%M") > datetime.strptime(visit_start_time, "%H:%M"):
                activity["transports"] = collect_innercity_transport(city, start, end, start_time, env, people, trans_type="metro")
            if activity["transports"] == "No solution" or safe_parse_time(activity["transports"][-1]["end_time"]) or datetime.strptime(activity["transports"][-1]["end_time"], "%H:%M") > datetime.strptime(visit_start_time, "%H:%M"):
                activity["transports"] = collect_innercity_transport(city, start, end, start_time, env, people, trans_type="taxi")                                
    return data

def reduce_cost(data, env, upper_bound, flag=0, target_place = [], target_attraction_type = [], target_restaurant_type = [], city_pingyin=None):
    plan = data["itinerary"]
    people = data["people_number"]
    city = data["target_city"]
    activity_pool = []
    attraction_type_count = {}
    restaurant_type_count = {}
    attractions = pd.read_csv(f"./chinatravel/environment/database/attractions/{city_pingyin}/attractions.csv")
    restaurants = pd.read_csv(f"./chinatravel/environment/database/restaurants/{city_pingyin}/restaurants_{city_pingyin}.csv")
    for day in plan:
        idx = day["day"]
        activities = day.get("activities", [])
        for activity in activities:
            activity["day"] = idx
            attraction_type = "非景点"
            restaurant_type = "非餐饮"
            activity_pool.append(activity)

            if activity["type"] == "attraction":
                attraction_type = attractions.loc[attractions["name"]==activity["position"]]["type"].item()
            if attraction_type_count.get(attraction_type) is None:
                attraction_type_count[attraction_type] = 1
            else:
                attraction_type_count[attraction_type] += 1

            if activity["type"] in ("breakfast", "lunch", "dinner"):
                restaurant_type = restaurants.loc[restaurants["name"]==activity["position"]]["cuisine"].item()
            if restaurant_type_count.get(restaurant_type) is None:
                restaurant_type_count[restaurant_type] = 1
            else:
                restaurant_type_count[restaurant_type] += 1

            activity["attraction_type"] = attraction_type
            activity["restaurant_type"] = restaurant_type

    skipped_indices = []
    print(attraction_type_count)
    while sum_costs(activity_pool, flag) > upper_bound:
        print(sum_costs(activity_pool, flag), upper_bound, attraction_type_count)
        max_index = max(
            (i for i in range(len(activity_pool)) 
             if i != 0   and 
             (i not in skipped_indices) and ("position" not in activity_pool[i] or activity_pool[i]["position"] not in target_place) and 
             (flag != 3 or activity_pool[i]["type"] == 'attraction') and
             (activity_pool[i]["attraction_type"] == "非景点" or len(target_attraction_type) == 0 or (activity_pool[i]["attraction_type"] in target_attraction_type and attraction_type_count[activity_pool[i]["attraction_type"]] > 1)) and
             (activity_pool[i]["restaurant_type"] == "非餐饮" or len(target_restaurant_type) == 0 or (activity_pool[i]["restaurant_type"] in target_restaurant_type and restaurant_type_count[activity_pool[i]["restaurant_type"]] > 1))),  
            key=lambda i: sum_costs(activity_pool[i], flag)
        )
        if activity_pool[max_index]["type"] in ('airplane', 'train', 'accommodation'):
            max_index -= 1
            if not (max_index != 0  and (max_index not in skipped_indices) and ("position" not in activity_pool[max_index] or activity_pool[max_index]["position"] not in target_place) and (flag != 3 or activity_pool[max_index]["type"] == 'attraction') and (activity_pool[max_index]["attraction_type"] == "非景点" or len(target_attraction_type) == 0 or (activity_pool[max_index]["attraction_type"] in target_attraction_type and attraction_type_count[activity_pool[max_index]["attraction_type"]] > 1)) and (activity_pool[max_index]["restaurant_type"] == "非餐饮" or len(target_restaurant_type) == 0 or (activity_pool[max_index]["restaurant_type"] in target_restaurant_type and restaurant_type_count[activity_pool[max_index]["restaurant_type"]] > 1))):
                skipped_indices.append(max_index + 1)
                continue

        if "position" not in activity_pool[max_index - 1]:
            new_start = activity_pool[max_index - 1]["end"]
        else:
            new_start = activity_pool[max_index - 1]["position"]

        if "position" not in activity_pool[max_index + 1]:
            new_end = activity_pool[max_index + 1]["start"]
        else:
            new_end = activity_pool[max_index + 1]["position"]
        new_start_time = activity_pool[max_index]["transports"][0]["start_time"]
        if len(activity_pool[max_index]["transports"]) == 1:
            new_trans_type = activity_pool[max_index]["transports"][0]["mode"]
        else:
            new_trans_type = "metro"
        new_transports = collect_innercity_transport(city, new_start, new_end, new_start_time, env, people, new_trans_type)
        if new_transports == "No solution":
            skipped_indices.append(max_index)
            continue
        activity_pool[max_index + 1]["transports"] = new_transports
        attraction_type_count[activity_pool[max_index]["attraction_type"]] -= 1
        restaurant_type_count[activity_pool[max_index]["restaurant_type"]] -= 1
        skipped_indices = [i - 1 if i > max_index else i for i in skipped_indices]
        removes = activity_pool.pop(max_index)

        if flag == 2:
            for revised_activity in activity_pool:
                if (revised_activity["type"] in ('airplane', 'train')):
                    continue
                for day in plan:
                    idx = day["day"]
                    activities = day.get("activities", [])
                    for activity in activities:
                        if (activity["type"] not in ('airplane', 'train')) and (revised_activity["day"] == idx and activity["position"] == revised_activity["position"]):
                            activity["transports"] = revised_activity["transports"]
            
            for day in plan:
                idx = day["day"]
                activities = day.get("activities", [])
                new_activities = []
                for activity in activities:
                    if activity["type"] in ('airplane','train'):
                        new_activities.append(activity)
                        continue
                    found = any(
                        revised_activity["type"] not in ('airplane','train') and
                        (revised_activity["day"] == idx and activity["position"] == revised_activity["position"])
                        for revised_activity in activity_pool
                    )
                    if found:
                        new_activities.append(activity)
                day["activities"] = new_activities

            data = change_transport(data, env)
            activity_pool = []
            plan = data["itinerary"]
            for day in plan:
                activities = day.get("activities", [])
                for activity in activities:
                    activity_pool.append(activity)
    
    for revised_activity in activity_pool:
        if (revised_activity["type"] in ('airplane', 'train')):
            continue
        for day in plan:
            activities = day.get("activities", [])
            for activity in activities:
                if (activity["type"] not in ('airplane', 'train')) and (revised_activity["day"] == idx and activity["position"] == revised_activity["position"]):
                    activity["transports"] = revised_activity["transports"]
    
    for day in plan:
        idx = day["day"]
        activities = day.get("activities", [])
        new_activities = []
        for activity in activities:
            if activity["type"] in ('airplane','train'):
                new_activities.append(activity)
                continue
            found = any(
                revised_activity["type"] not in ('airplane','train') and
                (revised_activity["day"] == idx and activity["position"] == revised_activity["position"])
                for revised_activity in activity_pool
            )
            if found:
                new_activities.append(activity)
        day["activities"] = new_activities
    
    for day in plan:
        activities = day.get("activities", [])
        for activity in activities:
            activity.pop("day")
            activity.pop("attraction_type")
            activity.pop("restaurant_type")            
    return data

def shift_time_interval(start_time_old, end_time_old, time_new, flag = 0):
    fmt = "%H:%M"
    t_start_old = datetime.strptime(start_time_old, fmt)
    t_end_old = datetime.strptime(end_time_old, fmt)
    
    duration = t_end_old - t_start_old
    
    if flag == 0:
        t_start_new = datetime.strptime(time_new, fmt)
        t_end_new = t_start_new + duration
        
        return time_new, t_end_new.strftime(fmt)
    else:
        t_end_new = datetime.strptime(time_new, fmt)
        t_start_new = t_end_new - duration
        return t_start_new.strftime(fmt), time_new

def Interpolation_place(data, target_place, target_type, city_pingyin, target_list):
    plan = data["itinerary"]
    people = data["people_number"]
    city = data["target_city"]
    original_data = copy.deepcopy(data)
    already_flag = False
    for day in plan:
        for act in day.get("activities", []):
            if act.get("position") == target_place:
                already_flag = True
                break
        if already_flag:
            break
    if already_flag:
        return original_data
    if target_type == "restaurants":
        restaurants = pd.read_csv(f"./chinatravel/environment/database/{target_type}/{city_pingyin}/restaurants_{city_pingyin}.csv")
        target_data = restaurants.loc[restaurants["name"] == target_place]
        print(target_data)
    else:
        attractions = pd.read_csv(f"./chinatravel/environment/database/{target_type}/{city_pingyin}/attractions.csv")
        target_data = attractions.loc[attractions["name"] == target_place]
    range_start = target_data["opentime"].item()
    range_end = target_data["endtime"].item()
    for day in plan:
        activities = day.get("activities", [])
        for idx, activity in enumerate(activities):
            if (target_type == "restaurants" and activity["type"] in ('breakfast', 'lunch', 'dinner')) or (target_type == "attractions" and activity["type"] == "attraction"):
                position = activity["position"]
                type = activity["type"]
                transports = activity["transports"]
                start_time = activity["start_time"]
                end_time = activity["end_time"]
                if target_type == "attractions":
                    min_time = target_data["recommendmintime"].item() * 60
                else:
                    min_time = 1
                if not is_within_time_range(start_time, add_minutes(start_time, min_time), range_start, range_end):
                    continue
                if target_type == "attractions" and target_data["recommendmintime"].item() > (datetime.strptime(end_time, "%H:%M") - datetime.strptime(start_time, "%H:%M")).total_seconds() / 3600:
                    continue
                if position in target_list:
                    continue
                
                new_trans_1 = collect_innercity_transport(city, transports[0]["start"], target_place, transports[0]["start_time"], env, people, "taxi")
                new_trans_2 = collect_innercity_transport(city, target_place, activities[idx + 1]["transports"][-1]["end"], add_minutes(start_time, min_time), env, people, "taxi")
                if datetime.strptime(new_trans_1[-1]["end_time"], "%H:%M") > datetime.strptime(start_time, "%H:%M") or datetime.strptime(new_trans_2[-1]["end_time"], "%H:%M") > datetime.strptime(activities[idx + 1]["start_time"], "%H:%M"):
                    continue
                else:
                    activity["position"] = target_place
                    activity["transports"] = new_trans_1
                    activity["price"] = target_data["price"].item()
                    activity["cost"] = target_data["price"].item() * people
                    activity["tickets"] = people
                    activity["end_time"] = add_minutes(start_time, min_time)                    
                    activities[idx + 1]["transports"] = new_trans_2
                    return data
                
    print("Unable to find an individual replacement plan; preparing to remove attractions or dining options to satisfy the constraints")

    for day_idx, day in enumerate(plan):
        activities = day.get("activities", [])
        for idx, activity in enumerate(activities):
            if (target_type == "restaurants" and activity["type"] in ('breakfast', 'lunch', 'dinner')) or (target_type == "attractions" and activity["type"] == "attraction"):
                position = activity["position"]
                type = activity["type"]
                transports = activity["transports"]
                start_time = activity["start_time"]
                end_time = activity["end_time"]
                if target_type == "attractions":
                    min_time = target_data["recommendmintime"].item() * 60
                else:
                    min_time = 1
                if not is_within_time_range(start_time, end_time, range_start, range_end):
                    continue
                if target_type == "attractions" and target_data["recommendmintime"].item() > (datetime.strptime(end_time, "%H:%M") - datetime.strptime(start_time, "%H:%M")).total_seconds() / 3600:
                    continue
                if position in target_list:
                    continue
                
                new_trans_1 = collect_innercity_transport(city, transports[0]["start"], target_place, transports[0]["start_time"], env, people, "taxi")
                new_trans_2 = collect_innercity_transport(city, target_place, activities[idx + 1]["transports"][-1]["end"], add_minutes(start_time, min_time), env, people, "taxi")

                while datetime.strptime(new_trans_1[-1]["end_time"], "%H:%M") > datetime.strptime(start_time, "%H:%M"):
                    del activities[idx - 1]
                    idx -= 1
                    new_trans_1 = collect_innercity_transport(city, activities[idx - 1]["transports"][-1]["end"], target_place, activities[idx - 1]["end_time"], env, people, "taxi")

                while datetime.strptime(new_trans_2[-1]["end_time"], "%H:%M") > datetime.strptime(activities[idx + 1]["start_time"], "%H:%M"):
                    del activities[idx + 1]
                    new_trans_2 = collect_innercity_transport(city, target_place, activities[idx + 1]["transports"][-1]["end"], add_minutes(start_time, min_time), env, people, "taxi")                
                
                activity["position"] = target_place
                activity["transports"] = new_trans_1
                activity["price"] = target_data["price"].item()
                activity["cost"] = target_data["price"].item() * people
                activity["tickets"] = people  
                activity["end_time"] = add_minutes(start_time, min_time)                  
                activities[idx + 1]["transports"] = new_trans_2
                return data
    
    print("Deleting formations of the corresponding type cannot satisfy the constraints; will proceed to delete across types")
    
    breakfast_time_period = ("06:00", "09:00")
    lunch_time_period = ("11:00", "14:00")
    dinner_time_period = ("18:00", "20:00")
    for day_idx, day in enumerate(plan):
        activities = day.get("activities", [])
        breakfast_flag = True
        lunch_flag = True
        dinner_flag = True
        for idx, activity in enumerate(activities):
            if activity["type"] == "breakfast":
                breakfast_flag = False
            if activity["type"] == "lunch":
                lunch_flag = False
            if activity["type"] == "dinner":
                dinner_flag = False
            
        for idx, activity in enumerate(activities): 
            if target_type == "restaurants" and activity["type"] not in ("train", "airplane", "accommodation"):
                position = activity["position"]
                type = activity["type"]
                transports = activity["transports"]
                start_time = activity["transports"][-1]["end_time"]
                end_time = activity["end_time"]
                min_time = 1
                if not is_within_time_range(start_time, add_minutes(start_time, min_time), range_start, range_end):
                    continue
                if position in target_list:
                    continue
                
                if breakfast_flag and is_within_time_range(start_time, add_minutes(start_time, min_time), breakfast_time_period[0], breakfast_time_period[1]):
                    activity["type"] = "breakfast"
                elif lunch_flag and is_within_time_range(start_time, add_minutes(start_time, min_time), lunch_time_period[0], lunch_time_period[1]):
                    activity["type"] = "lunch"
                elif dinner_flag and is_within_time_range(start_time, add_minutes(start_time, min_time), dinner_time_period[0], dinner_time_period[1]):
                    activity["type"] = "dinner"
                elif datetime.strptime(start_time, "%H:%M") < datetime.strptime(breakfast_time_period[0], "%H:%M") and datetime.strptime(activity["start_time"], "%H:%M") > datetime.strptime(breakfast_time_period[0], "%H:%M"):
                    activity["type"] = "breakfast"
                    start_time = breakfast_time_period[0]
                elif datetime.strptime(start_time, "%H:%M") < datetime.strptime(lunch_time_period[0], "%H:%M") and datetime.strptime(activity["start_time"], "%H:%M") > datetime.strptime(lunch_time_period[0], "%H:%M"):
                    activity["type"] = "lunch"
                    start_time = lunch_time_period[0]
                elif datetime.strptime(start_time, "%H:%M") < datetime.strptime(dinner_time_period[0], "%H:%M") and datetime.strptime(activity["start_time"], "%H:%M") > datetime.strptime(dinner_time_period[0], "%H:%M"):
                    activity["type"] = "dinner"
                    start_time = dinner_time_period[0]                
                else:
                    continue

                new_trans_1 = collect_innercity_transport(city, transports[0]["start"], target_place, transports[0]["start_time"], env, people, "taxi")
                new_trans_2 = collect_innercity_transport(city, target_place, activities[idx + 1]["transports"][-1]["end"], add_minutes(start_time, min_time), env, people, "taxi")

                while datetime.strptime(new_trans_1[-1]["end_time"], "%H:%M") > datetime.strptime(start_time, "%H:%M"):
                    del activities[idx - 1]
                    idx -= 1
                    new_trans_1 = collect_innercity_transport(city, activities[idx - 1]["transports"][-1]["end"], target_place, activities[idx - 1]["end_time"], env, people, "taxi")

                while datetime.strptime(new_trans_2[-1]["end_time"], "%H:%M") > datetime.strptime(activities[idx + 1]["start_time"], "%H:%M"):
                    del activities[idx + 1]
                    new_trans_2 = collect_innercity_transport(city, target_place, activities[idx + 1]["transports"][-1]["end"], add_minutes(start_time, min_time), env, people, "taxi")                
                
                activity["position"] = target_place
                activity["transports"] = new_trans_1
                activity["price"] = target_data["price"].item()
                activity["cost"] = target_data["price"].item() * people
                activity["tickets"] = people  
                activity["start_time"] = start_time
                activity["end_time"] = add_minutes(start_time, min_time)                  
                activities[idx + 1]["transports"] = new_trans_2
                return data 
    print("No solution found, returning original data")
    return original_data

def early_visit(data, env, target_position, target_time, duration=None):
    updated_data = copy.deepcopy(data)
    plan = updated_data["itinerary"]
    people = updated_data["people_number"]
    city = updated_data["target_city"]
    original_data = copy.deepcopy(data)
    for day_idx, day in enumerate(plan):
        activities = day.get("activities", [])
        for idx, activity in enumerate(activities):
            if activity["type"] in ('airplane', 'train', 'accommodation'):
                continue
            if activity.get('position') == target_position:
                old_start_time = activity["start_time"]
                while idx > 0 and datetime.strptime(old_start_time, "%H:%M") > datetime.strptime(target_time, "%H:%M"):
                    if activities[idx-1]["type"] in ('airplane', 'train', 'accommodation'):
                        break
                    print("idx", idx)
                    print(activities[idx - 1])
                    trans_new_start_time = activities[idx - 1]["transports"][0]["start_time"]
                    del activities[idx - 1]
                    idx -= 1
                    if idx > 0:
                        new_start = activities[idx - 1].get('position') or activities[idx - 1].get('end')
                        new_transports = collect_innercity_transport(city, new_start, target_position, trans_new_start_time, env, people, "taxi")
                        activities[idx]["transports"] = new_transports
                        old_start_time = activities[idx]["transports"][-1]["end_time"]
                    else:
                        new_start = plan[day_idx - 1]["activities"][-1].get('position')
                        new_transports = collect_innercity_transport(city, new_start, target_position, trans_new_start_time, env, people, "taxi")
                        activities[idx]["transports"] = new_transports
                        old_start_time = activities[idx]["transports"][-1]["end_time"]
                activity["start_time"], activity["end_time"] = shift_time_interval(activity["start_time"], activity["end_time"], target_time)
                if duration:
                    end_time_obj = datetime.strptime(activity["end_time"], "%H:%M")
                    target_end_time = datetime.strptime(target_time, "%H:%M") + timedelta(minutes=duration)
                    if end_time_obj < target_end_time:
                        activity["end_time"] = target_end_time.strftime("%H:%M")
                if len(activities[idx + 1]["transports"]) == 1:
                    activities[idx + 1]["transports"] = collect_innercity_transport(
                        city, 
                        activities[idx + 1]["transports"][0]["start"], 
                        activities[idx + 1]["transports"][0]["end"], 
                        activity["end_time"], 
                        env, 
                        people, 
                        activities[idx + 1]["transports"][0]["mode"]
                    )
                else:
                    activities[idx + 1]["transports"] = collect_innercity_transport(
                        city, 
                        activities[idx + 1]["transports"][0]["start"], 
                        activities[idx + 1]["transports"][-1]["end"], 
                        activity["end_time"], 
                        env, 
                        people, 
                        "metro"
                    )
                return updated_data
    return original_data
                       
def late_visit(data, env, target_position, target_time, flag = 0):
    updated_data = copy.deepcopy(data)
    plan = updated_data["itinerary"]
    people = updated_data["people_number"]
    city = updated_data["target_city"]
    original_data = copy.deepcopy(data)
    for day in plan:
        activities = day.get("activities", [])
        for idx, activity in enumerate(activities):
            if activity["type"] in ('airplane', 'train', 'accommodation'):
                continue
            if activity.get('position') == target_position:
                old_end_time = activity["end_time"]
                if len(activities[idx + 1]["transports"]) == 1:
                    new_trans = collect_innercity_transport(city, target_position, activities[idx + 1]["transports"][0]["end"], target_time, env, people, activities[idx + 1]["transports"][0]["mode"])
                else:
                    new_trans = collect_innercity_transport(city, target_position, activities[idx + 1]["transports"][-1]["end"], target_time, env, people, "metro")
                if datetime.strptime(new_trans[-1]["end_time"], "%H:%M") <= datetime.strptime(activities[idx + 1]["start_time"], "%H:%M"):
                    activities[idx + 1]["transports"] = new_trans
                    if flag == 1:
                        activity["end_time"] = target_time
                    else:
                        activity["start_time"], activity["end_time"] = shift_time_interval(activity["start_time"], activity["end_time"], target_time, flag=1)
                    return updated_data
                else:
                    while idx < len(activities) and datetime.strptime(old_end_time, "%H:%M") < datetime.strptime(target_time, "%H:%M"):
                        del activities[idx + 1]

                        if len(activities[idx + 1]["transports"]) == 1:
                            new_trans = collect_innercity_transport(city, target_position, activities[idx + 1]["transports"][0]["end"], target_time, env, people, activities[idx + 1]["transports"][0]["mode"])
                        else:
                            new_trans = collect_innercity_transport(city, target_position, activities[idx + 1]["transports"][-1]["end"], target_time, env, people, "metro")

                        if datetime.strptime(new_trans[-1]["end_time"], "%H:%M") <= datetime.strptime(activities[idx + 1]["start_time"], "%H:%M"):
                            activities[idx + 1]["transports"] = new_trans
                            if flag == 1:
                                activity["end_time"] = target_time
                            else:
                                activity["start_time"], activity["end_time"] = shift_time_interval(activity["start_time"], activity["end_time"], target_time, flag=1)
                            return updated_data
    return original_data


def is_within_time_range(start_str, end_str, range_start, range_end):
    fmt = "%H:%M"
    start = datetime.strptime(start_str, fmt)
    end = datetime.strptime(end_str, fmt)
    r_start = datetime.strptime(range_start, fmt)
    r_end = datetime.strptime(range_end, fmt)
    
    return r_start <= start and end <= r_end

def add_minutes(time_str, minutes):
    base_time = datetime.strptime(time_str, "%H:%M")
    new_time = base_time + timedelta(minutes=minutes)
    return new_time.strftime("%H:%M")
            
env = WorldEnv()

def collect_innercity_transport_new(city, start, end, start_time, env, people_number, trans_type="taxi"):
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


def change_transport_new(planned_itinerary, all_constraint):
    for day in planned_itinerary['itinerary']:
        new_activities = []
        change_flag = False
        post_activity = None
        for activity in day['activities']:
            if change_flag:
                post_activity = activity
            if activity["transports"] == [] or any(t['mode'] in all_constraint for t in activity["transports"]) and not change_flag:
                new_activities.append(activity)
            else:
                change_flag = True
            if change_flag and post_activity is not None:
                transport = collect_innercity_transport_new(city=planned_itinerary["target_city"], start=pre_activity["position"], end=activity["position"], start_time=pre_activity["end_time"], env=WorldEnv(), people_number=planned_itinerary["people_number"], trans_type=all_constraint[0])
                if transport == "No solution":
                    continue
                formatted_activity = {
                    "position": activity["position"],
                    "type": activity["type"],
                    "transports": transport,
                    "price": activity["price"],
                    "cost": activity["cost"],
                    "tickets": activity["tickets"],
                    "start_time": activity["start_time"],
                    "end_time": activity["end_time"],
                }
                new_activities.append(formatted_activity)
                change_flag = False
                post_activity = None
            if not change_flag:
                pre_activity = activity 
        day["activities"] = new_activities
    return planned_itinerary
