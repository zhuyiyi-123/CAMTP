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
import json
import numpy as np
from pypinyin import lazy_pinyin
from chinatravel.symbol_verification.hard_constraint import evaluate_constraints_py
project_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
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
from prompts import *


print(project_root_path)