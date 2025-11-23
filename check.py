import json, sys, argparse, re
from chinatravel.data.load_datasets import load_query

def contains_chinese(text):
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return bool(chinese_pattern.search(text))
def auto_fix_constraint(user_constraints):
    print("---------------------------------------------------")
    constraint_result = []
    for constraint in user_constraints:
        if "total_cost+=activity_cost" in constraint and "total_cost += innercity_transport_cost" in constraint and "result=(total_cost" in constraint:
            number_pattern = r"result=\(total_cost<=\s*(\d+)\)"
            match = re.search(number_pattern, constraint)
            if match:
                number_value = match.group(1)
            result = {"total_budget": number_value}
            constraint_result.append(result)

        if "attraction" in constraint and "attraction_name_set.add(activity_position(activity))" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_attraction": places_list}
            constraint_result.append(result)
        if "attraction" in constraint and "attraction_name_set.add(activity_position(activity))" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_attraction": places_list}
            constraint_result.append(result)
        if "attraction_cost" in constraint and "attraction_cost+=activity_cost(activity)" in constraint:
            match = re.search(r'([<>]=?)\s*(\d+)', constraint)
            if match:
                operator = match.group(1)
                value = int(match.group(2))
            result = {"attraction_cost": value, "attraction_cost_operator": operator}
            constraint_result.append(result)

        if "attraction_type_set.add(" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_attraction_type": places_list}
            constraint_result.append(result)

        if "attraction_type_set.add(" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_attraction_type": places_list}
            constraint_result.append(result)

        if "if activity_position(activity)==" in constraint and "if activity_time(activity)" in constraint:
            match = re.search(r'([<>]=?)\s*(\d+)', constraint)
            print("match:", match)
            if match:
                operator = match.group(1)
                value = int(match.group(2))
            result = {"activity_stop_time": value, "activity_stop_time_operator": operator}
            constraint_result.append(result)

        if "if activity_type(activity)=='accommodation" in constraint and "accommodation_name_set.add(" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_hotel": places_list}
            constraint_result.append(result)

        if "if activity_type(activity)=='accommodation" in constraint and "accommodation_name_set.add(" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_hotel": places_list}
            constraint_result.append(result)
            
        if "accommodation_type_set.add(" in constraint and "if activity_type(activity)=='accommodation'" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_hotel_type": places_list}
            constraint_result.append(result)
            
        if "accommodation_type_set.add(" in constraint and "if activity_type(activity)=='accommodation'" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_hotel_type": places_list}
            constraint_result.append(result)

        if "accommodation_cost+=" in constraint and "result=accommodation_cost" in constraint:
            match = re.search(r'([<>]=?)\s*(\d+)', constraint)
            if match:
                operator = match.group(1)
                value = int(match.group(2))
            result = {"accommodation_cost": value, "accommodation_cost_operator": operator}
            constraint_result.append(result)

        if "accommodation_position=activity_position(activity)" in constraint and "result=(poi_distance(target_city(plan)" in constraint:
            match = re.search(r"'([^']+)'.*?([<>]=?)\s*([\d.]+)", constraint)
            if match:
                location = match.group(1)  
                operator = match.group(2)  
                value = float(match.group(3))
            if not contains_chinese(location):
                accommodation_match = re.search((
        r"poi_distance\(target_city\(plan\), '([^']+)', accommodation_position\)(<=|>=)([\d\.]+)"
    ), constraint)
                if accommodation_match:
                    accommodation_info = {
                        'accommodation': accommodation_match.group(1),
                        'accommodation_operator': accommodation_match.group(2),
                        'accommodation_distance': float(accommodation_match.group(3))
                    }
            result = accommodation_info
            constraint_result.append(result)

        if "if activity_type(activity)=='accommodation'" in constraint and "room_type(activity)" in constraint:
            match = re.search(r"room_type\(activity\)!=\s*(\d+)", constraint)
            if match:
                bed_count_value = int(match.group(1))
            result = {"room_type": bed_count_value}
            constraint_result.append(result)
        
        if "restaurant_name_set.add(" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_restaurant": places_list}
            constraint_result.append(result)

        if "restaurant_name_set.add(" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_restaurant": places_list}
            constraint_result.append(result)

        if "restaurant_type_set.add(" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_restaurant_type": places_list}
            constraint_result.append(result)

        if "restaurant_type_set.add(" in constraint and "result=not({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            places_list = [place.strip().strip('"') for place in match.split(',')]
            result = {"must_not_restaurant_type": places_list}
            constraint_result.append(result)

        if "restaurant_cost+=" in constraint and "result=restaurant_cost" in constraint:
            match = re.search(r'([<>]=?)\s*(\d+)', constraint)
            if match:
                operator = match.group(1)
                value = int(match.group(2))
            result = {"restaurant_cost": value, "restaurant_cost_operator": operator}
            constraint_result.append(result)

        if "idx_activity1" in constraint and "if activity_position(activity)==" in constraint:
            pattern = re.compile(r"==\s*'([^']+)'")
            sequence = []
            matches = pattern.findall(constraint)
            if matches:
                for match in matches:
                    sequence.append(match)
            result = {"sequence": sequence}
            constraint_result.append(result)

        if "if activity_position(activity)==" in constraint and "if activity_start_time(activity)" in constraint:
            restaurant_match = re.search(r"==\s*'([^']+)'", constraint)
            time_match = re.search(r"activity_start_time\(activity\)<=\s*'([\d:]+)' and activity_end_time\(activity\)>=\s*'([\d:]+)'", constraint)
            if restaurant_match and time_match:
                restaurant_name = restaurant_match.group(1)  
                min_time = time_match.group(1)  
                max_time = time_match.group(2) 
            if time_match is None:
                time_match = re.search(r"activity_start_time\(activity\)<=\s*'([\d:]+)'", constraint)
                if restaurant_match and time_match:
                    restaurant_name = restaurant_match.group(1)  
                    min_time = time_match.group(1)  
                    max_time = None
            result = {"restaurant_stop_name": restaurant_name, "restaurant_stop_time_min": min_time, "restaurant_stop_time_max": max_time}
            constraint_result.append(result)
        if "if activity_position(activity)==" in constraint and "if activity_end_time(activity)" in constraint:
            min_time = None
            restaurant_match = re.search(r"==\s*'([^']+)'", constraint)
            print(restaurant_match)
            restaurant_match = re.search(r"activity_position\([^)]*\)\s*==\s*'([^']+)'", constraint)
            print(restaurant_match)
            time_match = re.search(r"activity_end_time\(activity\)>=\s*'([\d:]+)'", constraint)
            if restaurant_match and time_match:
                restaurant_name = restaurant_match.group(1)
                max_time = time_match.group(1)  
            result = {"stop_name": restaurant_name, "stop_time_min": min_time, "stop_time_max": max_time}
            constraint_result.append(result)
        
        if "intercity_transport_go=''" in constraint and "intercity_transport_back=''" in constraint and "if allactivities(plan)[0]['type'] == " in constraint:
            transport_type_pattern = r"\[\s*\'type\'\s*\]\s*==\s*\"(.*?)\""
            matches = re.findall(transport_type_pattern, constraint)
            if matches:
                outbound_transport_type = matches[0] 
                inbound_transport_type = matches[-1]
            result = {"intercity_transport_start": outbound_transport_type, "intercity_transport_target": inbound_transport_type}
            constraint_result.append(result)

        if "intercity_transport_go=''" in constraint and "intercity_transport_back=''" in constraint and "if allactivities(plan)[0]['type'] != " in constraint:
            transport_type_pattern = r"\[\s*\'type\'\s*\]\s*!=\s*\"(.*?)\""
            matches = re.findall(transport_type_pattern, constraint)
            if matches:
                outbound_transport_type = matches[0] 
                inbound_transport_type = matches[-1]
            result = {"intercity_transport_not_start": outbound_transport_type, "intercity_transport_not_target": inbound_transport_type}
            constraint_result.append(result)

        if "inter_city_transportation_cost+=" in constraint and "result=inter_city_transportation_cost" in constraint:
            match = re.search(r"result=inter_city_transportation_cost<=\s*(\d+)", constraint)
            if match:
                number_value = match.group(1)
            result = {"inter_city_transportation_cost": number_value}
            constraint_result.append(result)
        
        if "inner_city_transportation_set.add" in constraint and "result=not({" in constraint:
            match = re.search(r'result=not\(\{\s*("[^"]*"(?:\s*,\s*"[^"]*")*)\s*\}&inner_city_transportation_set\)', constraint)
            if match:
                extracted_values = [item.strip('" ') for item in match.group(1).split(',')]
            result = {"inner_city_transportation_set_not": extracted_values}
            constraint_result.append(result)
        if "intercity_transport_set.add" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            if match:
                extracted_values = [item.strip('" ') for item in match.split(',')]
            result = {"intercity_transport_set": extracted_values}
            constraint_result.append(result)

        if "inner_city_transportation_cost +=" in constraint and "result=(inner_city_transportation_cost<=" in constraint:
            match = re.search(r"result=\(inner_city_transportation_cost<=\s*(\d+)\)", constraint)
            if match:
                number_value = match.group(1)
            result = {"inner_city_transportation_cost": number_value}
            constraint_result.append(result)
            
        if "innercity_transport_set.add" in constraint and "result=({" in constraint:
            match = re.search(r'\{(.*?)\}', constraint).group(1)
            if match:
                extracted_values = [item.strip('" ') for item in match.split(',')]
            result = {"innercity_transport_set": extracted_values}
            constraint_result.append(result)
        
        if "innercity_transport_distance(activity_transports(activity))" in constraint and "innercity_transport_type(activity_transports(activity))" in constraint:
            match = re.search(r"innercity_transport_type\(.*?\) != '(.*?)'.*?innercity_transport_distance\(.*?\)>([\d\.]+)", constraint)
            if match:
                transport_type = match.group(1)
                distance = float(match.group(2))
            result = {"innercity_transport_type:": transport_type, "innercity_transport_exceed": distance}
            constraint_result.append(result)
    return constraint_result