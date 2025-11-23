import pandas as pd
import numpy as np
import json, os
from sklearn.cluster import DBSCAN
from haversine import haversine, Unit
from fuzzywuzzy import process
from pypinyin import lazy_pinyin
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from sklearn.metrics.pairwise import haversine_distances

def cluster_scenic_spots_now(spots, eps_km=1.0, min_samples=3, allowed_types=None, unallowed_types=None, max_budget=None, must_attraction=None, must_not_attraction=None):
    if unallowed_types != []:
        spots = [s for s in spots if not any(t in s['type'] for t in unallowed_types)]

    if allowed_types != []:
        spots = [s for s in spots if any(t in s['type'] for t in allowed_types)]
    
    if max_budget is not None and max_budget != []:
        for s in spots:
            break
        spots = [s for s in spots if s.get('price', 0.0) <= max_budget]
    coords = np.array([[s['lat'], s['lon']] for s in spots])
    kms_per_radian = 6371.0088
    epsilon = eps_km / kms_per_radian

    db = DBSCAN(eps=epsilon, min_samples=min_samples, metric='haversine')
    labels = db.fit_predict(np.radians(coords))

    clustered = {}
    for label in set(labels):
        if label == -1:
            continue
        clustered[label] = [spot for spot, l in zip(spots, labels) if l == label]
    return clustered

def load_attraction(json_load, city):
    curdir = os.path.dirname(os.path.realpath(__file__))
    data_path_list = os.path.join(curdir, f"{"../../environment/database/attractions"}/{city}/attractions.csv")
    spots_data = pd.read_csv(data_path_list, encoding="utf-8").to_dict('records')
    return spots_data

def find_similar_spots(spots_data, database, target_name=None, avoid_target_name=None, threshold=80):
    if target_name:
        spot_names = [spot['name'] for spot in spots_data]
        match, score = process.extractOne(target_name, spot_names)
        if score >= threshold:
            return spots_data
        db_match, db_score = process.extractOne(target_name, [db_spot['name'] for db_spot in database])
        if db_score >= threshold:
            matched_spot = next(spot for spot in database if spot['name'] == db_match)
            spots_data.append(matched_spot)
            return spots_data
    if avoid_target_name:
        spot_names = [spot['name'] for spot in spots_data]
        avoid_match, avoid_score = process.extractOne(avoid_target_name, spot_names)
        if avoid_score >= threshold:
            spots_data = [spot for spot in spots_data if spot['name'] != avoid_match]
            return spots_data
    return None

def cluster_scenic_spots(
    spots, eps_km=1.0, min_samples=3, allowed_types=None, unallowed_types=None,
    max_budget=None, must_attraction=None, must_not_attraction=None,
    auto_expand=True, max_eps_km=20, min_min_samples=2
):
    spots = [s for s in spots if s.get('endtime') > s.get('opentime')]
    
    all_spots = spots
    
    if unallowed_types:
        spots = [s for s in spots if not any(t in s['type'] for t in unallowed_types)]

    if allowed_types:
        spots = [s for s in spots if any(t in s['type'] for t in allowed_types)]

    if max_budget is not None:
        spots = [s for s in spots if s.get('price', 0.0) <= max_budget]

    if must_not_attraction:
        spots = [s for s in spots if s['name'] not in must_not_attraction]

    if not spots and not must_attraction:
        return [], []

    all_spots_dict = {s['name']: s for s in (all_spots if all_spots is not None else spots)}

    if must_attraction:
        must_spots = []
        for name in must_attraction:
            if name in all_spots_dict:
                must_spots.append(all_spots_dict[name])
        
        must_spots_with_coords = [s for s in must_spots if 'lat' in s and 'lon' in s]
        group = must_spots.copy()
        if must_spots_with_coords:
            center_lat = np.mean([s['lat'] for s in must_spots_with_coords])
            center_lon = np.mean([s['lon'] for s in must_spots_with_coords])
            center = np.radians([[center_lat, center_lon]])
            must_names_set = set([s['name'] for s in must_spots])
            dists = []
            for s in spots:
                if s['name'] in must_names_set:
                    continue
                spot_coord = np.radians([[s['lat'], s['lon']]])
                dist = haversine_distances(center, spot_coord)[0][0] * 6371.0088
                dists.append((dist, s))
            group.extend([s for dist, s in dists if dist <= eps_km])
        
        return group, spots

    coords = np.array([[s['lat'], s['lon']] for s in spots])
    kms_per_radian = 6371.0088

    clustered = []
    cur_eps_km = eps_km
    cur_min_samples = min_samples
    while auto_expand and cur_eps_km <= max_eps_km and cur_min_samples >= min_min_samples:
        epsilon = cur_eps_km / kms_per_radian
        db = DBSCAN(eps=epsilon, min_samples=cur_min_samples, metric='haversine')
        labels = db.fit_predict(np.radians(coords))
        clusters = {}
        for label in set(labels):
            if label == -1:
                continue
            group = [spot for spot, l in zip(spots, labels) if l == label]
            if must_not_attraction and any(s['name'] in must_not_attraction for s in group):
                continue
            clusters[label] = group
        if clusters:
            clustered = max(clusters.values(), key=lambda x: len(x))
            break
        cur_eps_km *= 1.5
        if cur_eps_km > max_eps_km and cur_min_samples > min_min_samples:
            cur_min_samples -= 1
            cur_eps_km = eps_km
    return clustered, spots


def recommend_cluster(
    clustered, spots, min_count=5, must_attraction=None, must_not_attraction=None
):
    must_not_attraction = set(must_not_attraction or [])

    result = []
    already_names = set()
    for s in clustered:
        if s['name'] not in must_not_attraction and s['name'] not in already_names:
            result.append(s)
            already_names.add(s['name'])

    result = [s for s in result if s.get('endtime') > s.get('opentime')]

    candidates = [s for s in spots if s['name'] not in already_names and s['name'] not in must_not_attraction]
    coords = [s for s in result if 'lat' in s and 'lon' in s]
    if coords:
        center_lat = np.mean([s['lat'] for s in coords])
        center_lon = np.mean([s['lon'] for s in coords])
        center = np.radians([[center_lat, center_lon]])
        dists = []
        for s in candidates:
            if 'lat' in s and 'lon' in s and s.get('endtime') > s.get('opentime'):
                spot_coord = np.radians([[s['lat'], s['lon']]])
                dist = haversine_distances(center, spot_coord)[0][0] * 6371.0088
            else:
                dist = float('inf')
            dists.append((dist, s))
        dists.sort(key=lambda x: x[0])
        for _, s in dists:
            result.append(s)
            if len(result) >= min_count:
                break
    else:
        for s in candidates:
            if s.get('endtime') > s.get('opentime'):
                result.append(s)
            if len(result) >= min_count:
                break

    return result[:min_count]