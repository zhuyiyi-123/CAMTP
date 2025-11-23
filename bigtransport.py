import pandas as pd
import numpy as np
import json
from sklearn.cluster import DBSCAN
from haversine import haversine, Unit
from fuzzywuzzy import process
from pypinyin import lazy_pinyin
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from sklearn.metrics.pairwise import haversine_distances

def get_all_options(start, end, env, outbound_type=None):
    if outbound_type is None:
        airplane = env.intercitytransport.select(
            start_city=start,
            end_city=end,
            intercity_type="airplane",
            earliest_leave_time="00:00"
        )
        train = env.intercitytransport.select(
            start_city=start,
            end_city=end,
            intercity_type="train",
            earliest_leave_time="00:00"
        )
        airplane['Type'] = 'airplane'
        train['Type'] = 'train'
        return pd.concat([airplane, train], ignore_index=True)
    else:
        transport = env.intercitytransport.select(
            start_city=start,
            end_city=end,
            intercity_type=outbound_type,
            earliest_leave_time="00:00"
        )
        transport['Type'] = outbound_type
        return transport
    
def intercity_transport(query, json_load, transport_query, env, outbound_type=None, return_type=None):
    go_options = get_all_options(query["start_city"], query["target_city"], env, outbound_type)
    back_options = get_all_options(query["target_city"], query["start_city"], env, return_type)

    go_options['RealCost'] = go_options['Cost'] * query["people_number"]
    back_options['RealCost'] = back_options['Cost'] * query["people_number"]
    
    go_options = go_options.sort_values('EndTime').reset_index(drop=True)
    back_options = back_options.sort_values('BeginTime', ascending=False).reset_index(drop=True)

    best_go = None
    best_back = None
    best_score = None

    for _, go_row in go_options.iterrows():
        for _, back_row in back_options.iterrows():
            total_cost = go_row['RealCost'] + back_row['RealCost']
            if transport_query["intercity_cost"] != None and total_cost <= transport_query["intercity_cost"]:
                end_time = datetime.strptime(go_row['EndTime'], "%H:%M")
                begin_time = datetime.strptime(back_row['BeginTime'], "%H:%M")
                score = end_time.timestamp() - begin_time.timestamp()
                if best_score is None or score < best_score:
                    best_go = go_row
                    best_back = back_row
                    best_score = score
    if best_go is not None:
        best_go = best_go.to_frame().T 
        best_back = best_back.to_frame().T 
        columns_to_check = ['FlightID', 'TrainID']
        if not best_go.empty:  
            for column in columns_to_check:
                if column in best_go.columns and pd.isna(best_go.iat[0, best_go.columns.get_loc(column)]):
                    best_go.drop(columns=column, inplace=True) 
        if not best_back.empty:  
            for column in columns_to_check:
                if column in best_back.columns and pd.isna(best_back.iat[0, best_back.columns.get_loc(column)]):
                    best_back.drop(columns=column, inplace=True)

        best_go_updated = best_go.squeeze()
        best_back_updated = best_back.squeeze()
        return best_go_updated, best_back_updated

    for _, go_row in go_options.iterrows():
        for _, back_row in back_options.iterrows():
            total_cost = go_row['RealCost'] + back_row['RealCost']
            if total_cost <= transport_query["intercity_cost"]:
                best_go = go_row
                best_back = back_row
                print("⚠️ Found an option within budget, but the timing is not ideal")
                return best_go, best_back

    min_go_cost = go_options['RealCost'].min()
    min_back_cost = back_options['RealCost'].min()
    min_total = min_go_cost + min_back_cost
    budget_gap = min_total - transport_query["intercity_cost"]

    print(f"❌ No option meets the budget; the minimum required is {min_total} yuan")
    print(f"  Budget shortfall: {budget_gap} yuan")

    return None

def intercity_transport_result(transport_query, env, query, json_load):
    if transport_query["intercity_cost"] == 0.00  and json_load["total_cost"] is None:
        transport_query["intercity_cost"] = 100000
    elif json_load["total_cost"] is not None:
        transport_query["intercity_cost"] = json_load["total_cost"]
    if query["start_city"] == "苏州" or query["target_city"] == "苏州":
        transport_query["bigtransport_type"]["go_must_type"] = "train"
        transport_query["bigtransport_type"]["back_must_type"] = "train"
    if transport_query["bigtransport_type"]["go_must_type"] != "train" and transport_query["bigtransport_type"]["back_must_type"] != "train":
        if transport_query["intercity_cost"] is None:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="airplane", earliest_leave_time="00:00")
            try:
                earliest_result = result.loc[result['BeginTime'].idxmin()]
            except:
                result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="train", earliest_leave_time="00:00")
                earliest_result = result.loc[result['BeginTime'].idxmin()]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="airplane", earliest_leave_time="00:00")
            try:
                lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
            except:
                last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="train", earliest_leave_time="00:00")
                lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
        else:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="airplane", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            earliest_result_sum = result.loc[result['BeginTime'].idxmin()]['Cost'] * query["people_number"]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="airplane", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
            lastest_result_sum = last_result.loc[last_result['BeginTime'].idxmax()]['Cost'] * query["people_number"]
            sum = earliest_result_sum + lastest_result_sum
            if  sum > transport_query["intercity_cost"]:
                earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env=env)
                if earliest_result is None :
                    transport_query["intercity_cost"] = lastest_result
                    earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env)
                
    elif transport_query["bigtransport_type"]["go_must_type"] != "train" and transport_query["bigtransport_type"]["back_must_type"] == "train":
        if transport_query["intercity_cost"] is None:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="airplane", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="train", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
        else:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="airplane", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            earliest_result_sum = result.loc[result['BeginTime'].idxmin()]['Cost'] * json_load["people_number"]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="train", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
            lastest_result_sum = last_result.loc[last_result['BeginTime'].idxmax()]['Cost'] * json_load["people_number"]
            sum = earliest_result_sum + lastest_result_sum
            if  sum > transport_query["intercity_cost"]:
                earliest_result, lastest_result =  intercity_transport(query, json_load, transport_query, env, outbound_type=None, return_type="train")
                if earliest_result is None :
                    transport_query["intercity_cost"] = lastest_result
                    earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env, outbound_type=None, return_type="train")
    elif transport_query["bigtransport_type"]["go_must_type"] == "train" and transport_query["bigtransport_type"]["back_must_type"] != "train":
        if transport_query["intercity_cost"] is None:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="train", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="airplane", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
        else:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="train", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            earliest_result_sum = result.loc[result['BeginTime'].idxmin()]['Cost'] * json_load["people_number"]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="airplane", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
            lastest_result_sum = last_result.loc[last_result['BeginTime'].idxmax()]['Cost'] * json_load["people_number"]
            sum = earliest_result_sum + lastest_result_sum
            if  sum > transport_query["intercity_cost"]:
                earliest_result, lastest_result =  intercity_transport(query, json_load, transport_query, env, outbound_type="train", return_type=None)
                if earliest_result is None :
                    transport_query["intercity_cost"] = lastest_result
                    earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env, outbound_type="train", return_type=None)
    else:
        if transport_query["intercity_cost"] is None:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="train", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="train", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
        else:
            result = env.intercitytransport.select(start_city=query["start_city"], end_city=query["target_city"], intercity_type="train", earliest_leave_time="00:00")
            earliest_result = result.loc[result['BeginTime'].idxmin()]
            earliest_result_sum = result.loc[result['BeginTime'].idxmin()]['Cost'] * json_load["people_number"]
            last_result = env.intercitytransport.select(start_city=query["target_city"], end_city=query["start_city"], intercity_type="train", earliest_leave_time="00:00")
            lastest_result = last_result.loc[last_result['BeginTime'].idxmax()]
            lastest_result_sum = last_result.loc[last_result['BeginTime'].idxmax()]['Cost'] * json_load["people_number"]
            sum = earliest_result_sum + lastest_result_sum
            earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env=env, outbound_type="train", return_type="train")
            if  sum > transport_query["intercity_cost"]:
                earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env, outbound_type="train", return_type="train")
                if earliest_result is None :
                    transport_query["intercity_cost"] = lastest_result
                    earliest_result, lastest_result = intercity_transport(query, json_load, transport_query, env, outbound_type="train", return_type="train")
    
    return earliest_result, lastest_result

