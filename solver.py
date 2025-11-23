import os
import ortools
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import json
import numpy as np
from datetime import datetime

def load_input_files(input_path, filename):
    os.makedirs(input_path, exist_ok=True)
    input_file = os.path.join(input_path, filename)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for scenic_list in data["scenic_list"]:
        attraction_name = scenic_list["id"]
    
    return data

def test_travel_planning(data1, output_path, filename):
    os.makedirs(output_path, exist_ok=True)
    file_path = os.path.join(output_path, filename)
    
    days = len(data1["user_preference"]["scheduling"])
    id_to_index = {}
    index_counter = 1

    def create_expanded_time_matrix(json_data):
        scenic_list = json_data["scenic_list"]
        n = len(scenic_list)

        id_to_index = {}
        index_to_name = {}

        for idx, scenic in enumerate(scenic_list, 1):
            scenic_id = scenic["id"]
            id_to_index[scenic_id] = idx
            index_to_name[idx] = scenic["name"]

        expanded_matrix = np.zeros((n + 1, n + 1), dtype=int)

        existing_pairs = set()
        for traffic in json_data["scenic_traffic_list"]:
            id1, id2 = traffic["scenic_pair"]
            existing_pairs.add((id1, id2))
            existing_pairs.add((id2, id1))

        for traffic in json_data["scenic_traffic_list"]:
            id1, id2 = traffic["scenic_pair"]
            cost_time = traffic["traffic_info"][0]["cost_time"] / 60

            idx1 = id_to_index.get(id1)
            idx2 = id_to_index.get(id2)

            if idx1 is not None and idx2 is not None:
                expanded_matrix[idx1][idx2] = cost_time
                expanded_matrix[idx2][idx1] = cost_time
            else:
                print(f"Warning: Unable to find index for attraction ID {id1} or {id2}")

        missing_pairs_count = 0
        for i, scenic1 in enumerate(scenic_list):
            id1 = scenic1["id"]
            idx1 = id_to_index[id1]

            for j, scenic2 in enumerate(scenic_list):
                if i != j:
                    id2 = scenic2["id"]
                    idx2 = id_to_index[id2]

                    if (id1, id2) not in existing_pairs:
                        if expanded_matrix[idx1][idx2] == 0:
                            expanded_matrix[idx1][idx2] = 9999999
                            missing_pairs_count += 1

        return expanded_matrix, id_to_index, index_to_name

    def print_expanded_matrix(matrix):
        for i in range(matrix.shape[0]):
            row = matrix[i]
            row_str = ", ".join(str(int(x)) for x in row)
            suffix = "," if i < matrix.shape[0] - 1 else ""

    real_time_matrix, id_to_index, index_to_name = create_expanded_time_matrix(data1)
    n = len(data1["scenic_list"])
    for scenic_id, idx in id_to_index.items():
        print(f"{scenic_id} → {idx} ({index_to_name[idx]})")
    print_expanded_matrix(real_time_matrix)

    def convert_time_to_seconds(time_str):
        try:
            if time_str == "24:00":
                return 24 * 60
            elif time_str == "00:00":
                return 0
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.hour * 60 + time_obj.minute
        except ValueError:
            print(f"Warning: Unable to parse time '{time_str}', using default value 0")
            return 0

    def extract_time_windows(json_data):
        time_windows = []
        time_windows.append((0, 1440))
        for scenic in json_data["scenic_list"]:
            scenic_time = scenic.get("scenic_time", {})
            if not scenic_time:
                time_windows.append((0, 0))
                continue
            first_date = next(iter(scenic_time.values()))
            opening_sec = convert_time_to_seconds(first_date["opening_time"])
            closing_sec = convert_time_to_seconds(first_date["closing_time"])
            if closing_sec == 0 and opening_sec != 0:
                closing_sec = 24 * 60
            time_windows.append((opening_sec, closing_sec))
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:    
                if user_constraints["type"] == "arrival_time":
                    attraction_id = user_constraints["ids"][0]
                    attraction_idx = id_to_index[attraction_id]
                    new_arr = convert_time_to_seconds(user_constraints["value"][0])
                    new_dep = convert_time_to_seconds(user_constraints["value"][1])
                    new_time_windows = (new_arr, new_dep)
                    time_windows[attraction_idx] = new_time_windows
        return time_windows

    real_time_windows = extract_time_windows(data1)

    def extract_min_stay_time(json_data):
        min_stay_time = []
        min_stay_time.append(0)
        for scenic in json_data["scenic_list"]:
            min_time = int(scenic["travel_time"][0] / 60)
            min_stay_time.append(min_time)
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                if user_constraints["type"] == "stay_time":
                    attraction_id = user_constraints["ids"]
                    attraction_idx = id_to_index[attraction_id[0]]
                    new_min_stay_time = user_constraints["value"]
                    min_stay_time[attraction_idx] = int(new_min_stay_time[0] / 60)
        return min_stay_time

    def extract_max_stay_time(json_data):
        max_stay_time = []
        max_stay_time.append(0)
        for scenic in json_data["scenic_list"]:
            max_time = int(scenic["travel_time"][1] / 60)
            max_stay_time.append(max_time)
        return max_stay_time
    min_stay_time = extract_min_stay_time(data1)
    max_stay_time = extract_max_stay_time(data1)

    def extract_vehicle_time_windows(json_data):
        scheduling = json_data["user_preference"].get("scheduling", {})
        if not scheduling:
            print("Warning: Scheduling data not found")
            return []
        sorted_days = sorted(scheduling.items(), key=lambda x: x[0])
        vehicle_time_windows = []
        day_keys = []
        for day_key, day_schedule in sorted_days:
            departure_time = day_schedule["departure"]["time"]
            arrival_time = day_schedule["arrival"]["time"]
            departure_sec = convert_time_to_seconds(departure_time)
            arrival_sec = convert_time_to_seconds(arrival_time)
            if departure_sec > arrival_sec:
                arrival_sec += 24 * 3600
            vehicle_time_windows.append((departure_sec, arrival_sec))
            day_keys.append(day_key)
        return vehicle_time_windows, day_keys

    def collect_must_visit_attractions(json_data):
        must_visit_attractions = []
        for attractions in json_data["user_preference"]["required_scenic_ids"]:
            attractions_idx = id_to_index[attractions]
            must_visit_attractions.append(attractions_idx)
        return must_visit_attractions
    must_visit_attractions = collect_must_visit_attractions(data1)

    def collect_day_attraction_bniding(json_data):
        day_keys = sorted(data1["user_preference"]["scheduling"].keys())
        day_attraction_bniding = {}
        if json_data ["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                if user_constraints["type"] == "date":
                    attraction_id = user_constraints["ids"][0]
                    date = user_constraints["value"][0]
                    attractions_idx = id_to_index[attraction_id]
                    day = day_keys.index(date)
                    day_attraction_bniding[attractions_idx] = day

        return day_attraction_bniding

    day_attraction_bniding = collect_day_attraction_bniding(data1)

    def collect_must_visit_after(json_data):
        constant_visit_seq = []
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                visit_seq = []
                if user_constraints["type"] == "sequence":
                    before_attraction_id = user_constraints["ids"][0]
                    after_attraction_id = user_constraints["ids"][1]
                    before_attraction_idx = id_to_index[before_attraction_id]
                    after_attraction_idx = id_to_index[after_attraction_id]
                    visit_seq.append(before_attraction_idx)
                    visit_seq.append(after_attraction_idx)
                    constant_visit_seq.append(visit_seq)
        return constant_visit_seq

    visit_seq = collect_must_visit_after(data1)
    def collect_inclusion_attractions(json_data):
        inclusion_attractions = []
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                same_day_attraction = []
                if user_constraints["type"] == "inclusion":
                    attraction1 = user_constraints["ids"][0]
                    attraction2 = user_constraints["ids"][1]
                    attraction1_idx = id_to_index[attraction1]
                    attraction2_idx = id_to_index[attraction2]
                    same_day_attraction.append(attraction1_idx)
                    same_day_attraction.append(attraction2_idx)
                    inclusion_attractions.append(same_day_attraction)
        return inclusion_attractions

    inclusion_attractions = collect_inclusion_attractions(data1)

    def collect_exclusion_attractions(json_data):
        exclusion_attractions = []
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                different_day_attraction = []
                if user_constraints["type"] == "exclusion":
                    attraction1 = user_constraints["ids"][0]
                    attraction2 = user_constraints["ids"][1]
                    attraction1_idx = id_to_index[attraction1]
                    attraction2_idx = id_to_index[attraction2]
                    different_day_attraction.append(attraction1_idx)
                    different_day_attraction.append(attraction2_idx)
                    exclusion_attractions.append(different_day_attraction)
        return exclusion_attractions

    exclusion_attractions = collect_exclusion_attractions(data1)
    def collect_order_attractions(json_data):
        before_node = 0
        after_node = 0
        if json_data["constraints"] != []:
            for user_constraints in json_data["constraints"]:
                if user_constraints["type"] == "order":
                    before_node_id = user_constraints["ids"][0]
                    after_node_id = user_constraints["ids"][1]
                    before_node_idx = id_to_index[before_node_id]
                    after_node_idx = id_to_index[after_node_id]
                    before_node += before_node_idx
                    after_node += after_node_idx
                else:
                    before_node = 0
                    after_node = 0
        else:
            before_node = 0
            after_node = 0
        return before_node, after_node

    before_node, after_node = collect_order_attractions(data1)

    def collect_big_transport_go(json_data):
        big_transport_go = []
        for big_transport in json_data["scenic_list"]:
            if big_transport["type"] == "big_transport_go":
                big_transport_go.append(big_transport["id"])
            else:
                return big_transport_go

        return big_transport_go

    go_big_transport = collect_big_transport_go(data1)

    def collect_big_transport_back(json_data):
        big_transport_back = []
        for big_transport in json_data["scenic_list"]:
            if big_transport["type"] == "big_transport_back":
                big_transport_back.append(big_transport["id"])
            else:
                return big_transport_back

        return big_transport_back

    back_big_transport = collect_big_transport_back(data1)
    def create_data_model():
        data = {}
        data["mandatory_nodes"] = must_visit_attractions
        data["node_vehicle_bindings"] = day_attraction_bniding
        data["must_visit_node_groups_in_the_same_vehicle"] = inclusion_attractions
        data["must_visit_node_groups_in_different_vehicle"] = exclusion_attractions
        data["must_visit_after"] = visit_seq
        data["visit_in_order"] = {
            "preceding_node": before_node,
            "following_node": after_node,
            "min_vehicle_diff": 1
        }
        data["time_matrix"] = real_time_matrix
        data["time_windows"] = real_time_windows
        data["min_service_times"] = min_stay_time
        data["max_slack_times"] = max_stay_time
        data["vehicle_time_windows"] = vehicle_time_windows
        data["first_day_start_scenic"] = []
        data["last_day_end_scenic"] = []
        data["num_vehicles"] = days
        data["depot"] = 0
        return data

    def print_solution(data, manager, routing, solution):
        def minutes_to_time(minutes):
            hours = minutes // 60
            minutes_part = minutes % 60
            return f"{int(hours):02d}:{int(minutes_part):02d}"
        def get_attraction_info(node_index):
            for scenic in data1["scenic_list"]:
                if node_index == scenic["id"]:
                    return {
                        "name": scenic["name"],
                        "location": scenic["location"],
                        "type": scenic["type"],
                        "id": scenic["id"]
                    }
            return None
        def find_traffic_info(from_id, to_id):
            for traffic in data1["scenic_traffic_list"]:
                scenic_pair = set(traffic["scenic_pair"])
                if {from_id, to_id} == scenic_pair:
                    return {
                        "distance": traffic["traffic_info"][0]["distance"],
                        "cost_time": traffic["traffic_info"][0]["cost_time"],
                        "traffic_type": traffic["traffic_info"][0]["traffic_type"],
                        "edge_id": traffic["edge_id"]
                    }
            return None
        unvisited_nodes = []
        for node in range(manager.GetNumberOfNodes()):
            index = manager.NodeToIndex(node)
            if not routing.IsEnd(index) and solution.Value(routing.NextVar(index)) == index:
                unvisited_nodes.append(node)
        for node in data["mandatory_nodes"]:
            index = manager.NodeToIndex(node)
            if not routing.IsEnd(index) and solution.Value(routing.NextVar(index)) == index:
                print(f"Warning: Mandatory node {node} was not visited!")
            if node in data["node_vehicle_bindings"]:
                required_vehicle = data["node_vehicle_bindings"][node]
                vehicle_id = solution.Value(routing.VehicleVar(index))
                if vehicle_id != required_vehicle:
                    print(f"Error: Node {node} was visited by vehicle {vehicle_id} instead of vehicle {required_vehicle}!")
        time_dimension = routing.GetDimensionOrDie("Time")
        total_time = 0
        total_traffic_distance = 0
        total_traffic_time = 0
        standard_output = {}
        daily_total_travel_time = {}
        daily_total_traffic_distance = {}
        daily_total_traffic_time = {}
        local_day_keys = sorted(data1["user_preference"]["scheduling"].keys())

        for vehicle_id in range(data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            plan_output = f"Day {vehicle_id + 1}:\n"
            day_attractions = []
            prev_node_id = None
            prev_departure_time = None
            day_distance = 0
            day_cost_time = 0

            day_key = local_day_keys[vehicle_id]
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != data["depot"]:
                    attraction_info = get_attraction_info(data1["scenic_list"][node_index - 1]["id"])
                    if not attraction_info:
                        index = solution.Value(routing.NextVar(index))
                        continue
                    time_var = time_dimension.CumulVar(index)
                    min_stay_time_local = data["min_service_times"][node_index]
                    arrival_min = solution.Min(time_var)
                    departure_min = arrival_min + min_stay_time_local
                    actual_stay_time = min_stay_time_local
                    arrival_time = minutes_to_time(arrival_min)
                    departure_time = minutes_to_time(departure_min)
                    traffic_info = {}
                    traffic_info2 = {}
                    distance_value = 0
                    cost_time_value = 0
                    if prev_node_id:
                        traffic_data = find_traffic_info(prev_node_id, attraction_info["id"])
                        distance_value += traffic_data["distance"]
                        cost_time_value += traffic_data["cost_time"]
                        if traffic_data:
                            traffic_info = {
                                "distance": int(distance_value),
                                "cost_time": int(traffic_data["cost_time"]),
                            }
                            traffic_info2 = {
                                "traffic_type": traffic_data["traffic_type"],
                                "edge_id": traffic_data["edge_id"]
                            }
                        else:
                            traffic_info = {
                                "distance": 0,
                                "cost_time": 0,
                            }
                            traffic_info2 = {
                                "traffic_type": 0,
                                "edge_id": 0,
                            }
                        day_distance += distance_value
                        day_cost_time += int(cost_time_value)
                    else:
                        traffic_info = {
                            "distance": 0,
                            "cost_time": 0,
                        }
                        traffic_info2 = {
                            "traffic_type": 0,
                            "edge_id": 0,
                        }
                    travel_time_value = actual_stay_time * 60
                    attraction_data = {
                        "arrival_time": arrival_time,
                        **traffic_info,
                        "name": attraction_info["name"],
                        **traffic_info2,
                        "location": attraction_info["location"],
                        "id": attraction_info["id"],
                        "type": "scenic",
                        "travel_time": travel_time_value,
                        "departure_time": departure_time
                    }
                    day_attractions.append(attraction_data)
                    prev_node_id = attraction_info["id"]
                    prev_departure_time = departure_time
                    plan_output += (
                        f"{attraction_info['name']} (Arr: {arrival_time}, Dep: {departure_time}) -> "
                    )
                index = solution.Value(routing.NextVar(index))
            end_time_var = time_dimension.CumulVar(index)
            end_min = solution.Min(end_time_var)
            end_time = minutes_to_time(end_min)
            plan_output += f"Return: {end_time}\n"
            start_time_var = time_dimension.CumulVar(routing.Start(vehicle_id))
            start_min = solution.Min(start_time_var)
            day_total_min = end_min - start_min
            plan_output += f"Total day time: {minutes_to_time(day_total_min)}\n"
            total_time += day_total_min
            standard_output[day_key] = day_attractions
            daily_total_travel_time[day_key] = int(day_total_min * 60)
            daily_total_traffic_distance[day_key] = int(day_distance)
            daily_total_traffic_time[day_key] = day_cost_time
            total_traffic_distance += day_distance
            total_traffic_time += day_cost_time
        total_time_second = total_time * 60
        statistic = {
            "daily_total_traffic_distance": daily_total_traffic_distance,
            "total_traffic_distance": int(total_traffic_distance),
            "dropped_scenics": unvisited_nodes,
            "daily_total_traffic_time": daily_total_traffic_time,
            "total_travel_time": int(total_time_second),
            "diagnose": {
                "20250712": [
                    {
                        "reason": "行程时间太短，建议增加景点",
                        "code": 1
                    }
                ]
            },
            "degraded_strategy": {
                "code": -len(unvisited_nodes),
                "detail": ""
            },
            "total_traffic_time": total_traffic_time,
            "description": "2025年07月11日\n 你将在09:00到达东方明珠，到达后，你将在这里游玩120分钟，然后预计在11:00离开。与下个景点距离0.0公里，乘车花费15分钟，\n 你将在11:15到达外滩，到达后，你将在这里游玩120分钟，然后预计在13:15离开。与下个景点距离1.0公里，乘车花费21分钟，\n 你将在13:36到达豫园，到达后，你将在这里游玩60分钟，然后预计在14:36离开。与下个景点距离0.0公里，乘车花费9分钟，\n 你将在14:45到达黄浦江游览(十六铺码头)，到达后，你将在这里游玩180分钟，然后预计在17:45离开。与下个景点距离1公里，乘车花费10分钟，\n 你将在17:55到达上海中心大厦，到达后，你将在这里游玩180分钟，然后预计在20:55离开。与下个景点距离0公里，乘车花费0分钟，\n\n2025年07月12日\n 你将在09:00到达上海博物馆，到达后，你将在这里游玩60分钟，然后预计在10:00离开。与下个景点距离3公里，乘车花费24分钟，\n 你将在10:24到达黄浦江，到达后，你将在这里游玩120分钟，然后预计在12:24离开。与下个景点距离2公里，乘车花费27分钟，\n 你将在12:51到达上海海洋水族馆，到达后，你将在这里游玩150分钟，然后预计在15:21离开。与下个景点距离0公里，乘车花费0分钟，\n",
            "daily_total_travel_time": daily_total_travel_time,
            "recommend_accommodation": {
                "20250711": "shanghaizhongxindasha"
            }
        }
        return standard_output, statistic

    def main():
        """Solve the VRP with time windows."""
        data = create_data_model()
        manager = pywrapcp.RoutingIndexManager(
            len(data["time_matrix"]), data["num_vehicles"], data["depot"],
        )
        routing = pywrapcp.RoutingModel(manager)
        def time_callback(from_index, to_index):
            """Returns the travel time plus minimal stay time between nodes."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            travel_time = data["time_matrix"][from_node][to_node]
            return travel_time
        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        time = "Time"
        routing.AddDimension(
            transit_callback_index,
            1440,
            1440,
            False,
            time,
        )
        time_dimension = routing.GetDimensionOrDie(time)

        for location_idx, time_window in enumerate(data["time_windows"]):
            if location_idx == data["depot"]:
                continue
            index = manager.NodeToIndex(location_idx)
            latest_dep_time = time_window[1] - data["min_service_times"][location_idx]
            time_dimension.CumulVar(index).SetRange(time_window[0], latest_dep_time)
            slack_var = time_dimension.SlackVar(index)
            slack_var.SetRange(
                data["min_service_times"][location_idx],
                data["max_slack_times"][location_idx]
            )
            routing.AddVariableMinimizedByFinalizer(slack_var)
            for vehicle_id in range(data["num_vehicles"]):
                time_dimension.SetSpanUpperBoundForVehicle(
                    data["vehicle_time_windows"][vehicle_id][1] if vehicle_id < len(data["vehicle_time_windows"]) else 1440,
                    vehicle_id
                )
        depot_idx = data["depot"]
        
        for vehicle_id in range(data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            if vehicle_id < len(data["vehicle_time_windows"]):
                time_dimension.CumulVar(index).SetRange(
                    data["vehicle_time_windows"][vehicle_id][0],
                    data["vehicle_time_windows"][vehicle_id][1]
                )
            else:
                time_dimension.CumulVar(index).SetRange(
                    data["time_windows"][depot_idx][0], 
                    data["time_windows"][depot_idx][1]
                )
                
            index = routing.End(vehicle_id)
            if vehicle_id < len(data["vehicle_time_windows"]):
                time_dimension.CumulVar(index).SetRange(
                    data["vehicle_time_windows"][vehicle_id][0],
                    data["vehicle_time_windows"][vehicle_id][1]
                )
            else:
                time_dimension.CumulVar(index).SetRange(
                    data["time_windows"][depot_idx][0], 
                    data["time_windows"][depot_idx][1]
                )
        routing.AddConstantDimension(
            1,
            7,
            True,
            "Count"
        )
        for vehicle_id in range(data["num_vehicles"]):
            count_dimension = routing.GetDimensionOrDie("Count")
            count_var = count_dimension.CumulVar(routing.End(vehicle_id))
            routing.solver().Add(count_var >= 2)
            routing.solver().Add(count_var <= 6)
        for i in range(data["num_vehicles"]):
            routing.AddVariableMinimizedByFinalizer(
                time_dimension.CumulVar(routing.Start(i))
            )
            routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.End(i)))
        for group in data["must_visit_node_groups_in_the_same_vehicle"]:
            if len(group) > 1:
                first_node_idx = manager.NodeToIndex(group[0])
                for node in group[1:]:
                    node_idx = manager.NodeToIndex(node)
                    routing.solver().Add(
                        routing.VehicleVar(first_node_idx) == routing.VehicleVar(node_idx)
                    )
        for group in data["must_visit_node_groups_in_different_vehicle"]:
            if len(group) > 1:
                first_node_idx = manager.NodeToIndex(group[0])
                for node in group[1:]:
                    node_idx = manager.NodeToIndex(node)
                    routing.solver().Add(
                        routing.VehicleVar(first_node_idx) != routing.VehicleVar(node_idx)
                    )
        for group in data["must_visit_after"]:
            before_node_idx = manager.NodeToIndex(group[0])
            after_node_idx = manager.NodeToIndex(group[1])
            routing.solver().Add(routing.NextVar(before_node_idx) == after_node_idx)
        order = data["visit_in_order"]
        before_node_idx = manager.NodeToIndex(order["preceding_node"])
        after_node_idx = manager.NodeToIndex(order["following_node"])
        routing.solver().Add(routing.VehicleVar(before_node_idx) <= routing.VehicleVar(after_node_idx))
        if routing.VehicleVar(before_node_idx) == routing.VehicleVar(after_node_idx):
            routing.solver().Add(
                time_dimension.CumulVar(before_node_idx) <= time_dimension.CumulVar(after_node_idx)
            )
        else:
            routing.solver().Add(
                routing.VehicleVar(before_node_idx) <= routing.VehicleVar(after_node_idx) + order["min_vehicle_diff"]
            )

        if data["first_day_start_scenic"] != []:
            first_scenic_node = data["first_day_start_scenic"]
            vehicle_id = 0

            start_index = routing.Start(vehicle_id)
            scenic_index = manager.NodeToIndex(first_scenic_node)
            routing.solver().Add(routing.NextVar(start_index) == scenic_index)
            routing.solver().Add(routing.VehicleVar(scenic_index) == vehicle_id)
            routing.solver().Add(routing.ActiveVar(scenic_index) == 1)

        if data["last_day_end_scenic"] != []:
            last_scenic_node = data["last_day_end_scenic"]
            last_vehicle_id = data["num_vehicles"]

            end_index = routing.End(last_vehicle_id)
            scenic_index = manager.NodeToIndex(last_scenic_node)

            routing.solver().Add(routing.NextVar(scenic_index) == end_index)
            routing.solver().Add(routing.VehicleVar(scenic_index) == last_vehicle_id)
            routing.solver().Add(routing.ActiveVar(scenic_index) == 1)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.guided_local_search_lambda_coefficient = 0.1
        search_parameters.use_cp_sat = True
        search_parameters.use_depth_first_search = True
        
        search_parameters.time_limit.seconds = 120

        for node in data["mandatory_nodes"]:
            index = manager.NodeToIndex(node)
            routing.solver().Add(routing.ActiveVar(index) == 1)
            
            if node in data["node_vehicle_bindings"]:
                required_vehicle = data["node_vehicle_bindings"][node]
                for vehicle_id in range(data["num_vehicles"]):
                    if vehicle_id != required_vehicle:
                        routing.solver().Add(
                            routing.VehicleVar(index) != vehicle_id
                        )
                    else:
                        routing.solver().Add(
                            routing.VehicleVar(index) == vehicle_id
                        )

        penalty = 1000
        for node in range(1, len(data["time_matrix"])):
            if node not in data["mandatory_nodes"]:
                routing.AddDisjunction([manager.NodeToIndex(node)], penalty)
        solution = routing.SolveWithParameters(search_parameters)
        if solution:
            solution_detail, solution_statistic = print_solution(data, manager, routing, solution)
            return solution_detail, solution_statistic
        return None, None

    solution_detail, solution_statistic = main()
    
    if solution_detail is not None:
        json_output = []
        standard_dict = {
            "solution_statistic": solution_statistic,
            "solution_detail": solution_detail
        }
        json_output.append(standard_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=4, ensure_ascii=False)
        
        return json_output
    else:
        print("No solution found")
        return None