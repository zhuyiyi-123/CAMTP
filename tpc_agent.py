import sys
import os
sys.path.append("./../../../")
project_root_path = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
project_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
import time
import argparse
import pandas as pd
import json, ast
import numpy as np
from chinatravel.symbol_verification.hard_constraint import evaluate_constraints_py
project_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
current_path = os.path.dirname(os.path.abspath(__file__))
tmp = os.path.dirname(current_path)
sys.path.insert(0, tmp+"/tpc_agent")

from agent.tpc_agent.retrieval import BM25Retriever
from agent.tpc_agent.prompts import *
from agent.tpc_agent.bigtransport import intercity_transport_result
from agent.tpc_agent.attraction import load_attraction, cluster_scenic_spots, recommend_cluster
from agent.tpc_agent.constraint import Constraint_result
from agent.tpc_agent.solver import test_travel_planning
from agent.tpc_agent.restaurant import RestaurantPlanner, csv_to_restaurants_db
from agent.tpc_agent.hotel import HotelPlanner, csv_to_hotel_db
from agent.tpc_agent.fix_json import fix_final_json
from agent.tpc_agent.check import auto_fix_constraint
from environment.world_env import WorldEnv
from agent.base import AbstractAgent, BaseAgent
from agent.tpc_agent.format import convert_itinerary, final_format, fix_all_meal_times, fix_transport_times
from agent.tpc_agent.nl2dsl import run_NL2DSL

from pypinyin import lazy_pinyin

class TPCAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(name="TPC", **kwargs)
        self.env = WorldEnv()
        self.target_city_en = None
        self.curdir = os.path.dirname(os.path.realpath(__file__))
        self.retriever = BM25Retriever()
        self.query = None
    def fix_double_braces_json(self, json_string):
        if json_string.startswith('{{') and json_string.endswith('}}'):
            fixed_string = json_string[1:-1]
            return fixed_string
        return json_string
    def transport(self, nature_language, query):
        messages = [{"role": "user", "content": TRANSPORT_INSTRUCTION.format(nature_language)}]
        transport_query = self.backbone_llm(messages, one_line=False, json_mode=False).replace('None', 'null')
        transport_query = self.fix_double_braces_json(transport_query)
        transport_query = json.loads(transport_query.replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null"))
        print("transport_query:", transport_query)
        messages_init = [{"role": "user", "content": INIT_INSTRUCTION.format(nature_language)}]
        a = self.backbone_llm(messages_init, one_line=False, json_mode=False)
        try:
            json_load = json.loads(a.replace("&quot;", "\"").replace("```json", "").replace("```", ""))
        except:
            json_load = json.loads(a.replace("{{", "{").replace("}}", "}").replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null"))
        print(json_load)
        earliest_result, lastest_result = intercity_transport_result(transport_query, self.env, query, json_load)
        print("big_transport:", earliest_result, lastest_result)
        total_budget = 0.0
        if json_load["total_cost"] != None and json_load["must_inner_city_transportation"] == []:
            total_budget = float(json_load["total_cost"]) - earliest_result["Cost"] * query["people_number"] - lastest_result["Cost"] * query["people_number"]
            json_load["must_inner_city_transportation"] = ["metro"]
        elif query["people_number"] >= 5:
            json_load["must_inner_city_transportation"] = ["metro"]
        return earliest_result, lastest_result, json_load, total_budget
    
    def attraction(self, json_load, nature_language, total_budget, query, min_count):
        messages_att = [{"role": "user", "content": ATTRACTIONS_DRAW.format(nature_language)}]
        a = self.backbone_llm(messages_att, one_line=False, json_mode=False).replace('None', 'null')
        a = self.fix_double_braces_json(a)
        a = a.replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null")
        attraction_query = json.loads(a)
        attraction_query["must_attraction_name"] = self.retriever.retrieval("attractions", attraction_query["must_attraction_name"], query["target_city"])
        attraction_query["must_not_attraction_name"] = self.retriever.retrieval("attractions", attraction_query["must_not_attraction_name"], query["target_city"])
        print("attraction_query:", attraction_query)
        spots_data = load_attraction(json_load, self.target_city_en)
        if attraction_query["attraction_cost"] is None and total_budget==0.0:
            max_budget = None
        elif attraction_query["attraction_cost"] is not None and total_budget==0.0:
            max_budget = (int(attraction_query["attraction_cost"]) / (4 * query["days"])) * 1.2
        else:
            attraction_budget = total_budget * 0.2
            max_budget = attraction_budget / (4 * query["days"]) * 1.2
        clustered, spots = cluster_scenic_spots(spots_data, eps_km=5.0, min_samples=3, allowed_types=attraction_query["must_attraction_type"], unallowed_types=attraction_query["must_not_attraction_type"], max_budget=max_budget, must_attraction=attraction_query["must_attraction_name"], must_not_attraction=attraction_query["must_not_attraction_name"])
        recommended = recommend_cluster(clustered, spots, min_count=min_count, must_attraction=attraction_query["must_attraction_name"], must_not_attraction=attraction_query["must_not_attraction_name"])
        return recommended, attraction_query, spots_data

    def convert_spots_to_pinyin_ids(self, constraints_dict):
    
        def spots_to_pinyin_id(spots_list):
            pinyin_ids = []
            for spot in spots_list:
                pinyin_parts = lazy_pinyin(spot)
                pinyin_id = ''.join(pinyin_parts).lower()
                pinyin_ids.append(pinyin_id)
            return pinyin_ids
        
        for constraint_type, constraint_data in constraints_dict.items():
            if 'constraints' in constraint_data:
                for constraint in constraint_data['constraints']:
                    if 'spots' in constraint and constraint['spots']:
                        new_ids = spots_to_pinyin_id(constraint['spots'])
                        constraint['ids'] = new_ids
                        print(f"Conversion: {constraint['spots']} -> {new_ids}")

        return constraints_dict
    
    def constraint(self, json_load, recommended, nature_language, query, attraction_query, earliest_result, lastest_result):
        city_name = query["target_city"]
        constrainted = Constraint_result(self.backbone_llm)
        constraint, days, formatted_dates = constrainted.constraint_extraction(nature_language)
        constraint = self.convert_spots_to_pinyin_ids(constraint)
        spot_names = [spot['name'] for spot in recommended]
        result = constrainted.format_result(nature_language, constraint, days, spot_names, city_name, recommended, attraction_query, formatted_dates, earliest_result, lastest_result)
        final_result = constrainted.transform_data(result)
        solution = constrainted.constraint_time(final_result, recommended)
        result = constrainted.combined_metro(constrainted.format_id(solution, self.env, query, json_load))
        uid = query["uid"]
        data_path_list = os.path.join(self.curdir + f"/results/constraint/result_{uid}.json")
        with open(data_path_list, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        return result      

    def solvers(self, result, json_load, recommended, nature_language, query, attraction_query, earliest_result, lastest_result, total_budget):
        uid = query["uid"]
        result_solvers = test_travel_planning(result, self.curdir + "/results/solver_results", f"{uid}.json")
        n = 4
        if "diagnose" in result_solvers[0]["solution_statistic"]:
            for date, diagnose_list in result_solvers[0]["solution_statistic"]["diagnose"].items():
                for diagnose in diagnose_list:
                    if diagnose.get("reason") == "No itinerary planned for the day, possibly due to a late departure time. It is recommended to choose an earlier departure time or date":
                        print(f"Since there is no itinerary planned for {date}, it is recommended to choose an earlier departure time or date. Operation terminated early.")
                        return  True, result_solvers
        check = 0
        while result_solvers[0]["solution_detail"] == {} and check < 5:
            result = self.constraint(json_load, recommended, nature_language, query, attraction_query, earliest_result, lastest_result)
            result = self.backtracking(result)
            result_solvers = test_travel_planning(result, "./results/solver_results", f"{uid}.json")
            check += 1
        if result_solvers[0]["solution_detail"] == {}:
            result = {
                "itinerary": [result_solvers], 
                "elapsed_time(sec)": time.time() - self.start_clock, 
                }
            return False, result
        with open('./result_solvers.json', 'w', encoding='utf-8') as f:
            json.dump(result_solvers, f, ensure_ascii=False, indent=4)
        return True, result_solvers
    
    def restaurant(self, query, nature_language, result_solvers, start_citys, total_budget):
        messages = [{"role": "user", "content": RESTAURANTS_DRAW.format(nature_language)}]
        print("restaurant:", self.backbone_llm(messages, one_line=False, json_mode=False))
        restaurant_query = json.loads(self.backbone_llm(messages, one_line=False, json_mode=False).replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null"))
        restaurant_query["must_restaurant_name"] = self.retriever.retrieval("restaurants", restaurant_query["must_restaurant_name"], query["target_city"])
        restaurant_query["must_not_restaurant_name"] = self.retriever.retrieval("restaurants", restaurant_query["must_not_restaurant_name"], query["target_city"])
        
        print("restaurant_query:", restaurant_query)
        restaurants_db = csv_to_restaurants_db(f"./chinatravel/environment/database/restaurants/{self.target_city_en}/restaurants_{self.target_city_en}.csv")
        if restaurant_query['restaurant_cost'] == 0.00 and total_budget == 0.0:
            restaurant_query['restaurant_cost'] = 50000.0
        elif restaurant_query['restaurant_cost'] == 0.00 and total_budget != 0.0:
            restaurant_query['restaurant_cost'] = total_budget * 0.5
        print("restaruantbudget:", restaurant_query['restaurant_cost'])
        planner = RestaurantPlanner(
            itinerary=result_solvers[0]["solution_detail"],
            restaurants_db=restaurants_db,
            total_budget=restaurant_query['restaurant_cost'],
            must_include=restaurant_query['must_restaurant_name'],
            must_exclude=restaurant_query['must_not_restaurant_name'],
            cuisine_avoid=restaurant_query['must_not_restaurant_type'],
            cuisine_prefer=restaurant_query['must_restaurant_type'],
            people_count=query['people_number'],
            restaurant_time=restaurant_query['restaurant_stay_time']
        )
        planned_itinerary = planner.plan_meals()
        with open(self.curdir + f'/results/result_restaurant/{query["uid"]}.json', 'w', encoding='utf-8') as f:
            json.dump(planned_itinerary, f, ensure_ascii=False, indent=4)
        return planned_itinerary, restaurants_db, restaurant_query

    def hotel(self, json_load, attraction_query, nature_language, format, total_budget=0.0):
        hotel_query = {"must_accommodation_type":[], "must_not_accommodation_type":[], "accommodation_cost": 50000.0, "must_accommodation_name": [], "must_not_accommodation_name": [], "nearby_attractions": {}, "numbed": None, "count": None, "avgbudget": None}
        if self.query["days"] != 1:
            try:
                messages = [{"role": "user", "content": HOTEL_DRAW.format(nature_language)}]
                hotel_query = self.backbone_llm(messages, one_line=False, json_mode=False).replace('None', 'null')
                hotel_query = self.fix_double_braces_json(hotel_query)
                hotel_query = json.loads(hotel_query.replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null"))
            except:
                messages = [{"role": "user", "content": HOTEL_DRAW.format(nature_language)}]
                a = self.backbone_llm(messages, one_line=False, json_mode=False)
                hotel_query = json.loads(a.replace("&quot;", "\"").replace("```json", "").replace("```", "").replace("None", "null"))
            print("hotel_query:", hotel_query)
            hotel_query["must_accommodation_name"] = self.retriever.retrieval("accommodations", hotel_query["must_accommodation_name"], self.query["target_city"])
            hotel_query["must_not_accommodation_name"] = self.retriever.retrieval("accommodations", hotel_query["must_not_accommodation_name"], self.query["target_city"])
         
            print("hotel_query:", hotel_query)
            hotel_budget = 0
            if total_budget != 0.0 and hotel_query["accommodation_cost"]==50000.0:
                hotel_budget = float(total_budget) * 0.3
            else:
                hotel_budget = hotel_query["accommodation_cost"]
            print("qw:", total_budget, hotel_query["accommodation_cost"], hotel_budget)
            if '家庭房' in hotel_query["must_accommodation_type"] and hotel_query["numbed"]==None:
                hotel_query["numbed"] = self.query["people_number"]
            planner = HotelPlanner(
                itinerary=format,
                hotel_db=csv_to_hotel_db(f"./chinatravel/environment/database/accommodations/{self.target_city_en}/accommodations.csv"),
                total_budget=hotel_budget,
                must_include=hotel_query["must_accommodation_name"],
                must_exclude=hotel_query["must_not_accommodation_name"],
                type_prefer=hotel_query["must_accommodation_type"],
                type_avoid=hotel_query["must_not_accommodation_type"],
                people_count=int(self.query["people_number"]),
                circle_distance = hotel_query["nearby_attractions"],
                transport_name=json_load["must_inner_city_transportation"],
                target_city = self.query["target_city"], 
                numbed = hotel_query["numbed"],
                count=hotel_query["count"],
                avgbudget=hotel_query["avgbudget"],
                env = WorldEnv(),
                query=attraction_query, 
                days=self.query["days"]
            )
            planned_itinerary = planner.plan_hotels()
        else:
            planned_itinerary = format
        with open(self.curdir+f'/results/hotel/{self.query["uid"]}.json', 'w', encoding='utf-8') as f:
            json.dump(format, f, ensure_ascii=False, indent=4)
        return planned_itinerary, hotel_query
    
    def check_fix(self, query, planned_itinerary, nature_language, json_load, hotel_query, attraction_query, restaurant_query):
        logical_result = evaluate_constraints_py(self.query["hard_logic_py"], planned_itinerary, verbose=True)
        i = 0
        false_constraint = []
        for constraint in self.query["hard_logic_py"]:
            if not logical_result[i]:
                false_constraint.append(constraint)
            i += 1
        result = auto_fix_constraint(false_constraint)
        with open(self.curdir+f'/results/final/result_format_final.json', 'w', encoding='utf-8') as f:
            json.dump(planned_itinerary, f, ensure_ascii=False, indent=4)
        cnt = 0           
        while result != []:
            planned_itinerary = fix_final_json(result, self.backbone_llm, nature_language, planned_itinerary, self.query, self.env, json_load["must_inner_city_transportation"], self.target_city_en, hotel_query=hotel_query, json_load=json_load, attraction_query=attraction_query, restaurant_query=restaurant_query)
            logical_result = evaluate_constraints_py(self.query["hard_logic_py"], planned_itinerary, verbose=True)
            i = 0
            false_constraint = []
            for constraint in self.query["hard_logic_py"]:
                if not logical_result[i]:
                    false_constraint.append(constraint)
                i += 1
            result = auto_fix_constraint(false_constraint)
            cnt+=1
            if cnt == 5:
                return False, planned_itinerary
        return True, planned_itinerary

    def run_test(self, query, prob_idx, oralce_translation=False):
        self.query = run_NL2DSL(query, self.backbone_llm)
        print(self.query)
        nature_language = query["nature_language"]
        messages = [{"role": "user", "content": REWRITE_REQUEST.format(nature_language)}]
        nature_language = self.backbone_llm(messages, one_line=False, json_mode=False)
        self.target_city_en = ''.join(lazy_pinyin(query["target_city"]))
        
        earliest_result, lastest_result, json_load, total_budget = self.transport(nature_language, query)
        recommended, attraction_query, spots_data = self.attraction(json_load, nature_language, total_budget, query, 4 * query["days"])
        result = self.constraint(json_load, recommended, nature_language, query, attraction_query, earliest_result, lastest_result)
        judge, result = self.solvers(result, json_load, recommended, nature_language, query, attraction_query, earliest_result, lastest_result, total_budget)
        if not judge:
            result = {
                "itinerary": [result], 
                "elapsed_time(sec)": time.time() - self.start_clock, 
            }
            return judge, result
        planned_itinerary, restaurants_db, restaurant_query = self.restaurant(query, nature_language, result, self.target_city_en, total_budget)
        format = convert_itinerary(planned_itinerary, people_number=int(query["people_number"]), start_city=query["start_city"], target_city=query["target_city"], earliest_result=earliest_result, lastest_result=lastest_result, env=self.env, transport_name=json_load["must_inner_city_transportation"], days=int(json_load["days"]), restaurant_db=restaurants_db, attraction_db=spots_data, restaurant_query=restaurant_query, attraction_query=attraction_query)
        with open(self.curdir+f'/results/covert/{query["uid"]}.json', 'w', encoding='utf-8') as f:
            json.dump(format, f, ensure_ascii=False, indent=4)
        planned_itinerary,hotel_query = self.hotel(json_load, attraction_query, nature_language, format, total_budget)

        planned_itinerary = final_format(planned_itinerary, self.env, transport_name=json_load["must_inner_city_transportation"], target_city=query["target_city"], people_number=query["people_number"], restaurants_db=restaurants_db)
        with open(self.curdir+f'/results/final_result/{query["uid"]}.json', 'w', encoding='utf-8') as f:
            json.dump(planned_itinerary, f, ensure_ascii=False, indent=4)
        flag, planned_itinerary = self.check_fix(query, planned_itinerary, nature_language, json_load, hotel_query, attraction_query, restaurant_query)
        self.reset_clock()

        result = {
            "itinerary": [planned_itinerary], 
            "elapsed_time(sec)": time.time() - self.start_clock, 
            }
        
        return flag, result
        
    def run(self, query, prob_idx, oralce_translation=False):
        retry_count = 0
        success = False
        result = {
            "itinerary": [], 
            "elapsed_time(sec)": time.time() - self.start_clock, 
        }
        while retry_count <= 3:
            try:
                success, result = self.run_test(query, prob_idx, oralce_translation)
                if success:
                    return success, result
                else:
                    retry_count += 1
                    continue
            except Exception as e:
                retry_count += 1
                if retry_count > 3:
                    break
                continue
        return success, result