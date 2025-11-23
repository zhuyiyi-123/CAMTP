from datetime import time, datetime, timedelta
from typing import List, Dict, Optional, Set
import pandas as pd
import math, json
import csv, random

class RestaurantPlanner:
    def __init__(self, itinerary, restaurants_db, total_budget, must_include, restaurant_time,
                 must_exclude: Optional[List[str]] = None, cuisine_avoid: Optional[Set[str]] = None, cuisine_prefer: Optional[Set[str]] = None,
                 people_count: int = 1, max_walking_distance: float = 50.0):
        self.itinerary = itinerary
        self.total_budget = total_budget
        self.remaining_budget = total_budget
        self.people_count = people_count
        self.assigned_restaurants = set()
        self.max_walking_distance = max_walking_distance
        self.must_include = must_include
        self.must_exclude = must_exclude
        self.activities = None
        self.restaurant_time = restaurant_time

        self.restaurants_db = self.cuisine_type(restaurants_db, cuisine_prefer, cuisine_avoid)

    def process_restaurants_db(self, restaurants_db, cuisine_prefer=None, cuisine_avoid=None):
        filtered_restaurants = []

        for restaurant in restaurants_db:
            cuisine_type = restaurant.get("cuisine_type", "")

            if cuisine_prefer and cuisine_type not in cuisine_prefer:
                continue

            if cuisine_avoid and cuisine_type in cuisine_avoid:
                continue

            filtered_restaurants.append(restaurant)

        for restaurant in filtered_restaurants:
            opentime = restaurant.get("opentime")
            endtime = restaurant.get("endtime")

            if isinstance(opentime, str):
                opentime = time(*map(int, opentime.split(':')))
                restaurant["opentime"] = opentime
            if isinstance(endtime, str):
                endtime = time(*map(int, endtime.split(':')))
                restaurant["endtime"] = endtime

            restaurant["serves_breakfast"] = opentime.hour < 9
            restaurant["serves_lunch"] = 10 < opentime.hour < 14 
            restaurant["serves_dinner"] = (opentime.hour >= 14 and endtime.hour > 19) or (opentime.hour >= 14 and endtime.hour<=7)

        return filtered_restaurants
    
    def cuisine_type(self, restaurants_db, cuisine_prefer, cuisine_avoid):
        filtered_results = []
        if cuisine_prefer != []:
            for restaurant in restaurants_db:
                must_go = restaurant["cuisine_type"] in cuisine_prefer
                if must_go:
                    filtered_results.append(restaurant)  
            return filtered_results
        elif cuisine_avoid != []:
            for restaurant in restaurants_db:
                must_no_go = restaurant["cuisine_type"] not in cuisine_avoid
                if must_no_go:
                    filtered_results.append(restaurant)  
            return filtered_results
        else:
            return restaurants_db
    
    def plan_meals(self):
        for restaurant_name in self.must_include:
            activities = self._assign_must_include_restaurant(restaurant_name)
        total_meals = self._calculate_total_meals_needed(self.itinerary)
        remaining_meals = total_meals - len(self.assigned_restaurants)
        print(remaining_meals)
        if remaining_meals > 0:
            avg_budget_per_meal = self.remaining_budget / remaining_meals
            print("avg_budget_per_meal:", avg_budget_per_meal)
            self._assign_regular_meals(avg_budget_per_meal)
        if remaining_meals < 0:
            print("Insufficient budget, will handle later")
            avg_budget_per_meal = 200.0 / remaining_meals
            print("avg_budget_per_meal:", avg_budget_per_meal)
            self._assign_regular_meals(avg_budget_per_meal)           
        return self.itinerary
    
    def _assign_regular_meals(self, avg_budget_per_meal):
        for date, activities in self.itinerary.items():
            current_meals = [a for a in activities if a.get("type") == "meal"]
            meal_slots = {m["meal_slot"] for m in current_meals}
            for slot in ["breakfast", "lunch", "dinner"]:
                if slot not in meal_slots:
                    self.arrange_meal(date, slot, activities, avg_budget_per_meal)
    
    def parse_time(self, time_str):
        return datetime.strptime(time_str, '%H:%M')
    
    def arrange_meal(self, date, slot, activities, avg_budget_per_meal):
        slot_ranges = {
            'breakfast': ('06:00', '08:59'),
            'lunch': ('11:00', '13:59'),
            'dinner': ('17:00', '19:59')
        }
        start_time, end_time = map(self.parse_time, slot_ranges[slot])
        for activity in activities:
            departure_time = self.parse_time(activity['departure_time'])
            arrival_time = self.parse_time(activity['arrival_time'])
            if start_time <= departure_time <= end_time:
                nearby_restaurants = self.find_nearby_restaurants(activity["location"], self.restaurants_db, avg_budget_per_meal, slot=slot)
                if nearby_restaurants is not None:
                    self.restaurants_db = self.remove_restaurant(self.restaurants_db, nearby_restaurants["name"])
                    meal_activity = self._create_meal_activity(nearby_restaurants, slot, activity)
                    self.remaining_budget = self.remaining_budget - meal_activity["cost"]
                    activities = self._insert_activity_sorted(date, meal_activity)
                    return activities
            elif slot=="breakfast" and arrival_time> end_time:
                nearby_restaurants = self.find_nearby_restaurants(activity["location"], self.restaurants_db, avg_budget_per_meal, slot=slot)
                if nearby_restaurants is not None:
                    self.restaurants_db = self.remove_restaurant(self.restaurants_db, nearby_restaurants["name"])
                    meal_activity = self._create_meal_activity(nearby_restaurants, slot, activity)
                    self.remaining_budget = self.remaining_budget - meal_activity["cost"]
                    activities = self._insert_activity_sorted(date, meal_activity)
                    return activities
                else:
                    return None

    
    def remove_restaurant(self, restaurants, restaurant_name=None):
        filtered_restaurants = [restaurant for restaurant in restaurants if restaurant['name'] != restaurant_name]
        return filtered_restaurants
    
    

    def find_nearby_restaurants(self, scenic_location, restaurants, avg_budget_per_meal, max_distance=2, slot="breakfast"):
        nearby_restaurants = []
        scenic_lon, scenic_lat = scenic_location
        meal_time_mapping = {
            'breakfast': 'serves_breakfast',
            'lunch': 'serves_lunch',
            'dinner': 'serves_dinner'
        }

        for restaurant in restaurants:
            distance = self.haversine(scenic_lon, scenic_lat, restaurant['location'][0], restaurant['location'][1])
            if distance <= max_distance and avg_budget_per_meal / self.people_count > restaurant['price'] and restaurant[meal_time_mapping[slot]]:
                return restaurant
        while nearby_restaurants == []:
            max_distance = max_distance + 2
            for restaurant in restaurants:
                distance = self.haversine(scenic_lon, scenic_lat, restaurant['location'][0], restaurant['location'][1])
                if distance <= max_distance and avg_budget_per_meal / self.people_count > restaurant['price'] and restaurant[meal_time_mapping[slot]]:
                    return restaurant
            if max_distance > 20:
                return None
                
            
    def _calculate_total_meals_needed(self, itinerary):
        total_meals = 0
        num_days = len(itinerary)
        last_day = 0
        
        for i, day in enumerate(itinerary):
            activity = itinerary[day]
            is_first_day = (i == 0)
            is_last_day = (i == num_days - 1)
            if activity == []:
                first_day = 0
            elif is_first_day:
                first_arrival = datetime.strptime(activity[0]["arrival_time"], "%H:%M").time()
                if first_arrival < time(9, 0):
                    first_day = 3
                elif first_arrival < time(14, 0):
                    first_day = 2
                elif first_arrival < time(20, 0):
                    first_day = 1
                else:
                    first_day = 0
            elif is_last_day:
                last_departure = datetime.strptime(activity[-1]["departure_time"], "%H:%M").time()
                if last_departure < time(6, 0):
                    last_day = 0
                elif last_departure < time(11, 0):
                    last_day = 1
                elif last_departure < time(17, 0):
                    last_day = 2
                else:
                    last_day = 3
        return first_day + last_day + (num_days - 2) * 3

    def haversine(self, lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
        
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a)) 
        r = 6371
        return c * r

    
    def _assign_must_include_restaurant(self, restaurant_name: str):
        restaurant = next((r for r in self.restaurants_db if r["name"] == restaurant_name), None)
        if not restaurant:
            return None
        
        if restaurant["name"] in self.must_exclude:
            raise ValueError(f"Restaurant '{restaurant['name']}' appears in both the must-visit and must-not-visit lists")
        
        total_cost = restaurant["price"] * self.people_count
        
        if total_cost > self.remaining_budget:
            print(f"Insufficient budget to arrange the must-visit restaurant '{restaurant['name']}'; "
                f"requires {total_cost}, remaining {self.remaining_budget}. Will handle later")
            return None

        best_date, best_slot, nearby_activity = self._find_best_slot_for_restaurant(restaurant)
                
        meal_activity = self._create_meal_activity(restaurant, best_slot, nearby_activity)
        
        best_date, best_slot, nearby_activity = self._find_best_slot_for_restaurant(restaurant)
                
        meal_activity = self._create_meal_activity(restaurant, best_slot, nearby_activity)
        
        activities = self._insert_activity_sorted(best_date, meal_activity)
        
        self.restaurants_db = self.remove_restaurant(self.restaurants_db, restaurant_name)
        
        
        self.remaining_budget -= total_cost
        self.assigned_restaurants.add(restaurant["id"])
        return activities
    
    def _insert_activity_sorted(self, date: str, new_activity: Dict):
        activities = self.itinerary[date]
        new_time = datetime.strptime(new_activity["arrival_time"], "%H:%M").time()
        
        for i, activity in enumerate(activities):
            curr_time = datetime.strptime(activity["arrival_time"], "%H:%M").time()
            if new_time < curr_time:
                activities.insert(i, new_activity)
                return activities
        
        activities.append(new_activity)
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
        if self.restaurant_time["time"] is not None:
            cost_time = self.restaurant_time["time"] * 60
        else:
            cost_time = 3600
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
            "cost_time": cost_time,
            "meal_slot": meal_slot,
            "is_fixed": restaurant["id"] in self.must_include,
            "nearby_activity": nearby_activity["name"],
            "walking_distance": distance,
            "traffic_type": "walk"
        }
    
        
    def _find_best_slot_for_restaurant(self, restaurant: Dict):
        best_date = None
        best_slot = None
        best_activity = None
        best_score = -1
        morning_score = -2
        lunch_score = -2
        dinner_score = -2
        breakfast_start = datetime.strptime("06:00", "%H:%M")
        breakfast_end = datetime.strptime("09:00", "%H:%M")
        lunch_start = datetime.strptime("11:00", "%H:%M")
        lunch_end = datetime.strptime("14:00", "%H:%M")
        dinner_start = datetime.strptime("17:00", "%H:%M")
        dinner_end = datetime.strptime("20:00", "%H:%M")
        tag = None

        
        for date, activities in self.itinerary.items():
            if any(a.get("type") == "meal" and a.get("name", "").startswith(restaurant["name"]) for a in activities):
                continue
            
            candidate_activities = [a for a in activities if a.get("type") != "meal"]
            for activity in candidate_activities:
                if isinstance(self.restaurant_time["arrival"], str):
                    self.restaurant_time["arrival"] = datetime.strptime(self.restaurant_time["arrival"], "%H:%M")
                distance = self._calculate_distance(restaurant["location"], activity["location"])
                if distance > self.max_walking_distance:
                    continue
                if self.restaurant_time["arrival"] is None:
                    tag = None
                elif breakfast_start <= self.restaurant_time["arrival"] <= breakfast_end:
                    tag = "breakfast"
                elif lunch_start <= self.restaurant_time["arrival"] <= lunch_end:
                    tag = "lunch"
                elif dinner_start <= self.restaurant_time["arrival"] <= dinner_end:
                    tag = "dinner"
                
                if tag == None:       
                    morning_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="breakfast",
                        distance=distance,
                        time=None
                    )
                    lunch_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="lunch",
                        distance=distance,
                        time=None
                    )
                    dinner_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="dinner",
                        distance=distance,
                        time=None
                    )
                elif tag=="breakfast":
                    morning_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="breakfast",
                        distance=distance, 
                        time=self.restaurant_time["arrival"]
                    )
                elif tag=="lunch":
                    lunch_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="lunch",
                        distance=distance,
                        time=self.restaurant_time["arrival"]
                    )
                else:
                    dinner_score = self._calculate_time_slot_score(
                        restaurant=restaurant,
                        activity=activity,
                        meal_slot="dinner",
                        distance=distance,
                        time=self.restaurant_time["arrival"]
                    )
                if morning_score > best_score:
                    best_score = morning_score
                    best_date = date
                    best_slot = "breakfast"
                    best_activity = activity

                if lunch_score > best_score:
                    best_score = lunch_score
                    best_date = date
                    best_slot = "lunch"
                    best_activity = activity
                    
                if dinner_score > best_score:
                    best_score = dinner_score
                    best_date = date
                    best_slot = "dinner"
                    best_activity = activity

        
        if best_date is None:
            raise ValueError(f"Unable to find a suitable time slot for restaurant '{restaurant['name']}'")

        return best_date, best_slot, best_activity
    
    def _calculate_distance(self, loc1: List[float], loc2: List[float]) -> float:
        lat1, lon1 = loc1[1], loc1[0]
        lat2, lon2 = loc2[1], loc2[0]
        
        dx = (lon2 - lon1) * 111 * math.cos(math.radians((lat1 + lat2)/2))
        dy = (lat2 - lat1) * 111
        return math.sqrt(dx**2 + dy**2)
    
    def _calculate_time_slot_score(self, restaurant: Dict, activity: Dict, meal_slot: str, distance: float, time: str) -> float:
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
            
        act_time = datetime.strptime(activity["arrival_time"], "%H:%M")
        if time is not None:
            if time - timedelta(hours=2) <= act_time <= time:
                score += 20
        else:
            if meal_slot == "lunch":
                if datetime.strptime("10:00", "%H:%M") <= act_time <= datetime.strptime("14:00", "%H:%M"):
                    score += 20
            elif meal_slot == "dinner":
                if datetime.strptime("16:00", "%H:%M") <= act_time <= datetime.strptime("20:00", "%H:%M"):
                    score += 20
            else:
                if datetime.strptime("06:00", "%H:%M") <= act_time <= datetime.strptime("09:00", "%H:%M"):
                    score += 20  
        return score
    


def csv_to_restaurants_db(csv_filepath):
    restaurants_db = []
    
    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            opentime = time(*map(int, row['opentime'].split(':')))
            if row['endtime'] == "24:00":
                row['endtime'] = "23:59"
            endtime = time(*map(int, row['endtime'].split(':')))

            opentime_hour = opentime.hour
            endtime_hour = endtime.hour

            serves_breakfast = opentime_hour < 9  
            serves_lunch = opentime_hour < 14     
            serves_dinner = endtime_hour >= 20     
            
            restaurant = {
                "id": row['id'],
                "name": row['name'],
                "location": [float(row['lon']), float(row['lat'])],
                "opentime": opentime,
                "endtime": endtime,
                "price": float(row['price']),
                "cuisine_type": row['cuisine'],
                "recommended_food": row['recommendedfood'].split(',') if row['recommendedfood'] else [],
                "serves_breakfast": serves_breakfast,  
                "serves_lunch": serves_lunch,         
                "serves_dinner": serves_dinner,       
            }
            
            restaurants_db.append(restaurant)
    
    return restaurants_db