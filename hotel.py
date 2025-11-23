from datetime import time, datetime, timedelta
from typing import List, Dict, Optional, Set
from pypinyin import lazy_pinyin
import pandas as pd
import math, json, sys
import csv, random

project_root_path = "./chinatravel/"
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
project_root_path = "./"
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
from environment.world_env import WorldEnv
from agent.tpc_agent.attraction import load_attraction
from agent.tpc_agent.format import transport_result
import difflib

class HotelPlanner:
    def __init__(self, itinerary, hotel_db, total_budget, must_include, must_exclude, type_prefer, type_avoid,
                 people_count, circle_distance, transport_name, target_city, numbed, count, avgbudget, env, query, days):
        self.itinerary = itinerary
        print("itinerary:", itinerary)
        if total_budget == 0:
            self.total_budget = 100000
        else:
            self.total_budget = total_budget
        self.must_include = must_include
        self.must_exclude = must_exclude
        self.type_prefer = type_prefer
        self.type_avoid = type_avoid
        self.circle_distance = circle_distance
        self.remaining_budget = total_budget
        self.people_count = people_count
        self.assigned_hotels = set()
        self.hotel_db_all = hotel_db
        self.transport_name = transport_name
        self.target_city = target_city
        self.numbed = numbed
        self.env = env
        self.query = query
        self.count = count
        self.avgbudget = avgbudget
        self.days = days
        
        self.activities = None

        self.hotel_db = self.hotel_type(hotel_db, type_prefer, type_avoid, numbed)
        if self.hotel_db == [] or self.hotel_db == None:
            self.hotel_db = hotel_db
        self.poi_db = pd.read_csv(f"./chinatravel/environment/database/attractions/{''.join(lazy_pinyin(self.target_city))}/attractions.csv", encoding="utf-8")
        self.poi_all_db = json.load(open(f"./chinatravel/environment/database/poi/{''.join(lazy_pinyin(self.target_city))}/poi.json", "r", encoding="utf-8"))
        city_pinyin = ''.join(lazy_pinyin(self.target_city))
        self.restaurant_db = pd.read_csv(f"./chinatravel/environment/database/restaurants/{city_pinyin}/restaurants_{city_pinyin}.csv", encoding="utf-8")
        self.hotel_db_all = hotel_db

    def hotel_type(self, hotel_db, type_prefer, type_avoid, numbed):
        print()
        if self.days != 1:
            budget = self.total_budget / self.people_count / (self.days - 1)
        filtered_results = []
        if type_prefer != [] and numbed != None:
            for hotel in hotel_db:
                must_go = hotel["featurehoteltype"] in type_prefer and int(hotel["numbed"]) == int(numbed)
                if must_go and (float(hotel["price"]) / float(hotel["numbed"])) < budget:
                    filtered_results.append(hotel)  
                    if filtered_results == []:
                        for hotel in hotel_db:
                            must_go = hotel["featurehoteltype"] in type_prefer and int(hotel["numbed"]) == int(numbed)
                            if must_go:
                                filtered_results.append(hotel)  
            return filtered_results
        elif type_prefer != []:
            for hotel in hotel_db:
                must_go = hotel["featurehoteltype"] in type_prefer
                if must_go:
                    filtered_results.append(hotel)  
            return filtered_results
        elif type_avoid != [] and numbed != None:
            for hotel in hotel_db:
                must_no_go = hotel["featurehoteltype"] not in type_avoid and int(hotel["numbed"]) == int(numbed)
                if must_no_go:
                    filtered_results.append(hotel)  
            return filtered_results
        elif type_avoid != []:
            for hotel in hotel_db:
                must_no_go = hotel["featurehoteltype"] not in type_avoid
                if must_no_go:
                    filtered_results.append(hotel)  
            return filtered_results
        elif numbed != None:
            for hotel in hotel_db:
                if int(hotel["numbed"]) == int(numbed):
                    filtered_results.append(hotel)  
            return filtered_results
        else:
            return hotel_db
    
    def plan_hotels(self):
        for hotel_name in self.must_include:
            activities = self._assign_must_include_hotel(hotel_name)
        total_hotels = self._calculate_total_hotels_needed(self.itinerary)
        remaining_hotels = total_hotels - len(self.assigned_hotels)
        if remaining_hotels > 0:
            avg_budget_per_hotel = self.remaining_budget / remaining_hotels
            print("_assign_regular_hotels")
            self._assign_regular_hotels(avg_budget_per_hotel)
        if remaining_hotels < 0:
            print("Over budget, will handle later")
            avg_budget_per_hotel = 1000.0 / remaining_hotels
            print("_assign_regular_hotels")
            self._assign_regular_hotels(avg_budget_per_hotel)
        return self.itinerary

    def arrange_must_hotels(self, i, activities, avg_budget_per_hotel):
        nearby_restaurants = []
        max_distance = 2
        poi_name = self.circle_distance["name"]
        poi_distance = self.circle_distance["distance"]
        poi = self.poi_db.loc[self.poi_db["name"] == poi_name]
        target_latitude, target_longitude = float(poi['lon']), float(poi['lat'])
        new_hotel_db = []
        for hotel in self.hotel_db:
            distance = self.haversine(float(target_latitude), float(target_longitude), float(hotel["lon"]), float(hotel["lat"]))
            if distance < poi_distance:
                new_hotel_db.append(hotel)
        if new_hotel_db == []:
            for hotel in self.hotel_db:
                distance = self.haversine(float(target_latitude), float(target_longitude), float(hotel["lon"]), float(hotel["lat"]))
                new_hotel_db.append(hotel)
        if activities[-1]["type"] == "dinner":
            poi_last = self.poi_db.loc[self.poi_db["name"] == activities[-2]["position"]]
            lon = poi['lon']
            lat = poi['lat']
        else:  
            try:
                poi_last = self.poi_db.loc[self.poi_db["name"] == activities[-1]["position"]]
                lon = poi['lon']
                lat = poi['lat']
            except:
                with open(f"./chinatravel/environment/database/poi/{''.join(lazy_pinyin(self.target_city))}/poi.json", "r", encoding="utf-8") as file:
                    poi_csv = json.load(file) 
                for poi in poi_csv:
                    if poi.get('name') == activities[-1]["end"]:
                        poi = poi.copy()
                        break
                lat, lon = poi["position"]
                poi_last = {'lat': lat, 'lon': lon}
        for hotel in new_hotel_db:
            distance = self.haversine(float(lon), float(lat), float(hotel['lon']), float(hotel['lat']))
            if distance <= max_distance and (float(avg_budget_per_hotel) / float(math.ceil(float(self.people_count)/float(hotel["numbed"])))) > float(hotel['price']):
                return hotel
        
        while nearby_restaurants == []:
            max_distance = max_distance + 2
            for hotel in new_hotel_db:
                distance = self.haversine(float(poi_last['lon']), float(poi_last['lat']), float(hotel['lon']), float(hotel['lat']))
                if distance <= max_distance and (float(avg_budget_per_hotel) / float(math.ceil(float(self.people_count)/float(hotel["numbed"])))) > float(hotel['price']):
                    return hotel
            if max_distance > 35:
                return None
    
    
    def _assign_regular_hotels(self, avg_budget_per_hotel):
        print(self.itinerary)
        for i in range(len(self.itinerary["itinerary"]) - 1):
            activities = self.itinerary["itinerary"][i]["activities"]
            current_hotels = [a for a in activities if a.get("type") == "accommodation"]
            if self.circle_distance != {}:
                if self.circle_distance["distance"] == 0 or self.circle_distance["distance"] is None:
                    self.circle_distance = {}
            if current_hotels:
                break
            elif self.circle_distance != {} and not isinstance(self.circle_distance["distance"], type(None)):
                print("activite-1:",activities[-1])
                if activities[-1]["type"] == "train" or activities[-1]["type"] == "airplain":
                    hotel = self.arrange_must_hotels(i, activities, avg_budget_per_hotel)
                    distance = transport_result(self.transport_name, self.target_city, activities[-1]["end"], hotel["name"], activities[-1]["end_time"], self.env, self.people_count)
                    self._insert_activity_sorted(i + 1, distance)
                else:   
                    hotel = self.arrange_must_hotels(i, activities, avg_budget_per_hotel)
                    print("hotel:", hotel)
                    distance = transport_result(self.transport_name, self.target_city, activities[-1]["position"], hotel["name"], activities[-1]["end_time"], self.env, self.people_count)
                    self._insert_activity_sorted(i + 1, distance)
            else:
                try:
                    hotel = self.arrange_hotel(i, activities, avg_budget_per_hotel)
                    print("hotel:", hotel)
                    print(activities[-1]["position"])
                    print(activities[-1]["end_time"])
                    distance = transport_result(self.transport_name, self.target_city, activities[-1]["position"], hotel["name"], activities[-1]["end_time"], self.env, self.people_count)
                    self._insert_activity_sorted(i + 1, distance)
                except:
                    print(i, activities, avg_budget_per_hotel)
                    hotel = self.arrange_hotel(i, activities, avg_budget_per_hotel)
                    distance = transport_result(self.transport_name, self.target_city, activities[-1]["end"], hotel["name"], activities[-1]["end_time"], self.env, self.people_count)
                    self._insert_activity_sorted(i + 1, distance)
    def arrange_hotel(self, i, activities, avg_budget_per_hotel):
        max_distance = 2
        nearby_restaurants = []
        if activities[-1]["type"] == "dinner":
            try:
                poi = self.poi_db.loc[self.poi_db["name"] == activities[-2]["position"]]
                lon = poi['lon'].iloc[0]
                lat = poi['lat'].iloc[0]
            except:
                try:
                    poi = self.poi_db.loc[self.poi_db["name"] == activities[-3]["position"]]
                    lon = poi['lon'].iloc[0]
                    lat = poi['lat'].iloc[0]
                except:
                    for i in range(len(self.poi_all_db)):
                        if self.poi_all_db[i]["name"] == activities[-1]["position"]:
                            poi = self.poi_all_db[i]
                            lon = poi["position"][1]
                            lat = poi["position"][0]
        else:
            try:
                poi = self.poi_db.loc[self.poi_db["name"] == activities[-1]["position"]]
                lon = poi['lon'].iloc[0]
                lat = poi['lat'].iloc[0]
            except:
                with open(f"./chinatravel/environment/database/poi/{''.join(lazy_pinyin(self.target_city))}/poi.json", "r", encoding="utf-8") as file:
                    poi_csv = json.load(file) 
                try:
                    for poi in poi_csv:
                        if poi.get('name') == activities[-1]["end"]:
                            poi = poi.copy()
                            lat, lon = poi["position"]
                            break
                except:
                    poi = self.poi_db.loc[self.poi_db["name"] == activities[-2]["position"]]
                    lon = poi['lon'].iloc[0]
                    lat = poi['lat'].iloc[0]
        for hotel in self.hotel_db:
            distance = self.haversine(float(lon), float(lat), float(hotel['lon']), float(hotel['lat']))
            min_distance = 0
            if "metro" in self.transport_name:
                min_distance = 5
                max_distance = 10
            if distance <= max_distance and min_distance <= distance and (float(avg_budget_per_hotel) / float(math.ceil(float(self.people_count)/float(hotel["numbed"])))) > float(hotel['price']):
                return hotel
        min_budget = 1000
        while nearby_restaurants == []:
            max_distance = max_distance + 2
            for hotel in self.hotel_db:
                distance = self.haversine(float(poi['lon']), float(poi['lat']), float(hotel['lon']), float(hotel['lat']))
                hotel["distance"] = distance
                if distance <= max_distance and (float(avg_budget_per_hotel) / float(math.ceil(float(self.people_count)/float(hotel["numbed"])))) > float(hotel['price']):
                    return hotel
                elif distance <= max_distance and float(hotel['price']) < min_budget:
                    min_budget = float(hotel['price'])
                    min_budget_hotel = hotel
            if max_distance > 25:
                try:
                    return min_budget_hotel
                except:
                    try:
                        return hotel
                    except:
                        for hotel in self.hotel_db_all:
                            distance = self.haversine(float(lon), float(lat), float(hotel['lon']), float(hotel['lat']))
                            if distance < max_distance:
                                return hotel

    def remove_restaurant(self, restaurants, restaurant_name):
        filtered_restaurants = [restaurant for restaurant in restaurants if restaurant['name'] != restaurant_name]
        return filtered_restaurants            
            
    def _calculate_total_hotels_needed(self, itinerary):
        return self.days - 1

    def haversine(self, lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
        
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a)) 
        r = 6371
        return c * r
    
    def _find_closest_hotel_name(self, hotel_name: str):
        hotel_names = [hotel["name"] for hotel in self.hotel_db_all]
        closest_matches = difflib.get_close_matches(hotel_name, hotel_names, n=1, cutoff=0.5)
        print("closest_matches:", closest_matches)
        return closest_matches[0] if closest_matches else None
    
    def _assign_must_include_hotel(self, hotel_name: str):
        hotel = next((r for r in self.hotel_db_all if r["name"] == hotel_name), None)
        if not hotel:
            print(f"Required hotel ID '{hotel_name}' does not exist. "
                f"Attempting fuzzy search to find the closest hotel...")
            similar_hotel_name = self._find_closest_hotel_name(hotel_name)
            if similar_hotel_name:
                print(f"Found the closest hotel: '{similar_hotel_name}', "
                    f"using it as the new required hotel.")
                hotel = next((r for r in self.hotel_db_all if r['name'] == similar_hotel_name), None)
            else:
                raise ValueError(
                    f"Required hotel ID '{hotel_name}' does not exist, "
                    f"and no similar hotel name could be found."
                )

        if hotel["name"] in self.must_exclude:
            raise ValueError(f"Hotel '{hotel['name']}' appears in both the must-visit and must-not-visit lists")

        total_cost = float(hotel["price"]) * (math.ceil(int(self.people_count) / int(hotel["numbed"])))
        if total_cost > self.remaining_budget:
            print(
            f"Insufficient budget to arrange the required hotel '{hotel['name']}'; "
            f"requires {total_cost}, remaining {self.remaining_budget}. "
            f"Continuing arrangement and will handle later"
            )
        best_date, best_activity, best_transport = self._find_best_slot_for_hotel(hotel)  
        activities = self._insert_activity_sorted(best_date, best_transport)
        
        self.remaining_budget -= total_cost
        self.assigned_hotels.add(best_transport[0]["end"])
        print("success!!!!!!!!")
        return activities
    
    def _insert_activity_sorted(self, best_date, best_transport):
        activities = self.itinerary['itinerary'][best_date-1]
        innercity_transports = []
        matching_hotels = [hotel for hotel in self.hotel_db if hotel['name'] == best_transport[-1]["end"]]
        for i in range(len(best_transport)):
            if best_transport[i]["mode"] == "taxi":
                innercity_transports_new = {
                    "start": best_transport[i]["start"],
                    "end": best_transport[i]["end"],
                    "mode": best_transport[i]["mode"],
                    "start_time": best_transport[i]["start_time"],
                    "end_time":  best_transport[i]["end_time"],
                    "price": best_transport[i]["price"],
                    "cost": best_transport[i]["price"] * math.ceil(self.people_count/4),
                    "distance": best_transport[i]["distance"],
                    "cars": math.ceil(self.people_count/4)
                }
            else:
                    innercity_transports_new = {
                    "start": best_transport[i]["start"],
                    "end": best_transport[i]["end"],
                    "mode": best_transport[i]["mode"],
                    "start_time": best_transport[i]["start_time"],
                    "end_time":  best_transport[i]["end_time"],
                    "price": best_transport[i]["price"],
                    "cost": best_transport[i]["cost"],
                    "distance": best_transport[i]["distance"],
                    "tickets": self.people_count
                }
            innercity_transports.append(innercity_transports_new)
        if best_transport[-1]["end_time"] <= "24:00":
            if self.count == None:
                self.count = int(math.ceil(int(self.people_count) / int(matching_hotels[0]["numbed"])))
                total_hotels = self._calculate_total_hotels_needed(self.itinerary)
                remaining_hotels = total_hotels - len(self.assigned_hotels)
                if self.remaining_budget / remaining_hotels / self.people_count < 500:
                    self.count = 1 
            activity_i = {
                "position": best_transport[-1]["end"],
                "type": "accommodation",
                "price": float(matching_hotels[0]["price"]),
                "cost": float(matching_hotels[0]["price"]) * self.count,
                "start_time": best_transport[-1]["end_time"],
                "end_time": "24:00",
                "transports": innercity_transports,
                "rooms": self.count,
                "room_type": int(matching_hotels[0]["numbed"])
            }
            self.itinerary["itinerary"][best_date-1]["activities"].append(activity_i)
        else:
            if self.itinerary["itinerary"][best_date-1]["activities"][-1]["position"] not in self.attraction_query["attractions"]:
                self.itinerary["itinerary"][best_date-1]["activities"].pop()
            best_transport = transport_result(self.transport_name, self.target_city, self.itinerary["itinerary"][best_date-1]["activities"][-1]["position"], best_transport[-1]["end"], self.itinerary["itinerary"][best_date-1]["activities"][-1]["end_time"], self.env, self.people_count)
            innercity_transports = []
            for i in range(len(best_transport)):
                if best_transport[i]["mode"] == "taxi":
                    innercity_transports_new = {
                        "start": best_transport[i]["start"],
                        "end": best_transport[i]["end"],
                        "mode": best_transport[i]["mode"],
                        "start_time": best_transport[i]["start_time"],
                        "end_time":  best_transport[i]["end_time"],
                        "price": best_transport[i]["price"],
                        "cost": best_transport[i]["price"] * math.ceil(self.people_count/4),
                        "distance": best_transport[i]["distance"],
                        "cars": math.ceil(self.people_count/4)
                    }
                else:
                    innercity_transports_new = {
                        "start": best_transport[i]["start"],
                        "end": best_transport[i]["end"],
                        "mode": best_transport[i]["mode"],
                        "start_time": best_transport[i]["start_time"],
                        "end_time":  best_transport[i]["end_time"],
                        "price": best_transport[i]["price"],
                        "cost": best_transport[i]["cost"],
                        "distance": best_transport[i]["distance"],
                        "tickets": self.people_count
                    }
                innercity_transports.append(innercity_transports_new)
            if self.count == None:
                self.count = int(math.ceil(int(self.people_count) / int(matching_hotels[0]["numbed"])))
            activity_i = {
                "position": best_transport[-1]["end"],
                "type": "accommodation",
                "price": float(matching_hotels[0]["price"]),
                "cost": float(matching_hotels[0]["price"]) * self.count,
                "start_time": best_transport[-1]["end_time"],
                "end_time": "24:00",
                "transports": innercity_transports,
                "rooms": self.count,
                "room_type": int(matching_hotels[0]["numbed"])
            }
            self.itinerary["itinerary"][best_date-1]["activities"].append(activity_i)
        return activities
        
    def _create_meal_activity(self, restaurant: Dict, meal_slot: str, nearby_activity: Dict) -> Dict:
        if meal_slot == "lunch":
            start_time = time(11, 0)
            end_time = time(14, 00)
        elif meal_slot == "dinner":
            start_time = time(17, 00)
            end_time = time(20, 00)
        else:
            start_time = time(6, 00)
            end_time = time(9, 00)
        
        distance = self._calculate_distance(restaurant["location"], nearby_activity["location"])
        
        return {
            "name": f"{restaurant['name']}",
            "location": restaurant["location"],
            "type": "meal",
            "cuisine_type": restaurant["cuisine_type"],
            "recommended_food": restaurant.get("recommended_food", []),
            "price": restaurant["price"],
            "cost": restaurant["price"] * self.people_count,
            "people_count": self.people_count,
            "arrival_time": start_time.strftime("%H:%M"),
            "departure_time": end_time.strftime("%H:%M"),
            "travel_time": 1800,
            "cost_time": 3600,
            "meal_slot": meal_slot,
            "is_fixed": restaurant["id"] in self.must_include,
            "nearby_activity": nearby_activity["name"],
            "walking_distance": distance,
            "traffic_type": "walk"
        }
    
    def _find_best_slot_for_hotel(self, hotel: Dict):
        best_date = None
        best_activity = None
        best_transport = None
        best_score = float('inf')  
        
        for day in range(len(self.itinerary['itinerary'])-1):
            activities = self.itinerary['itinerary'][day]
            
            if not activities:
                continue
            
            last_activity = activities["activities"][-1]

            try:
                distance = transport_result(self.transport_name, self.target_city, last_activity["position"], hotel["name"], last_activity["end_time"], self.env, self.people_count)
            except:
                distance = transport_result(self.transport_name, self.target_city, last_activity["end"], hotel["name"], last_activity["end_time"], self.env, self.people_count)
            if distance[0]["distance"] < best_score:
                best_score = distance[0]["distance"]
                best_date = day + 1
                best_activity = last_activity
                best_transport = distance
        if best_date is None:
            raise ValueError(f"Unable to find a suitable time slot for hotel '{hotel['name']}'")
        return best_date, best_activity, best_transport
    
    def _calculate_time_slot_score(self, restaurant: Dict, activity: Dict, meal_slot: str, distance: float) -> float:
        score = 0
        
        if meal_slot == "lunch":
            if restaurant["serves_lunch"]:
                score += 40
        elif meal_slot == "dinner":
            if restaurant["serves_dinner"]:
                score += 40
        else:
            if restaurant["serves_breakfast"]:
                score += 40
                
        normalized_distance = min(distance / self.max_walking_distance, 1.0)
        score += 40 * (1 - normalized_distance)
            
        act_time = datetime.strptime(activity["arrival_time"], "%H:%M").time()
        if meal_slot == "lunch":
            if time(10, 0) <= act_time <= time(12, 0):
                score += 20
        else:
            if time(15, 0) <= act_time <= time(18, 0):
                score += 20
                
        return score
    
def csv_to_hotel_db(csv_filepath):
    hotel_db = []
    
    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            hotel = {
                "id": row['id'],
                "name": row['name'],
                "hotelname_en": row['hotelname_en'],
                "featurehoteltype": row['featurehoteltype'],
                "lat": row['lat'],
                "lon": row['lon'],
                "price": row['price'],
                "numbed": row['numbed']     
            }
            
            hotel_db.append(hotel)
    
    return hotel_db
