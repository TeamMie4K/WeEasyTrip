# -*- coding: utf-8 -*-
"""utils.py - helper functions for distance, time, cost, route evaluation"""
import json
import math
from typing import Dict, List, Tuple

# Constants
AVG_SPEED_KMH = 40
COST_PER_KM = 10
DAY_TIME_BUDGET = 840       # 14 hours (8:00 - 22:00)
DAY_START_MIN = 480         # 8:00


def load_data(path: str) -> Tuple[List[Dict], List[Dict]]:
    """Load POIs and hotels from JSON"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['pois'], data['hotels']


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two coordinates (km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def travel_time_min(dist_km: float) -> float:
    return (dist_km / AVG_SPEED_KMH) * 60.0


def travel_cost(dist_km: float) -> float:
    return dist_km * COST_PER_KM


def evaluate_route(routes_per_day: List[List[Dict]], hotel: Dict,
                   budget: float, day_time: float = DAY_TIME_BUDGET) -> Dict:
    """Evaluate route quality with all constraints"""
    total_score = 0.0
    total_cost = 0.0
    days_detail = []
    violations = []

    for day_idx, day_pois in enumerate(routes_per_day):
        day_dist = 0.0
        day_cost_local = 0.0
        day_score_local = 0.0
        current_time = float(DAY_START_MIN)
        arrivals = []

        if not day_pois:
            days_detail.append({
                'pois': [], 'distance_km': 0.0, 'time_min': 0.0,
                'cost': 0.0, 'score': 0.0, 'arrivals': []
            })
            continue

        path = [hotel] + day_pois + [hotel]

        for i in range(len(path) - 1):
            d = haversine_km(path[i]['lat'], path[i]['lng'],
                             path[i + 1]['lat'], path[i + 1]['lng'])
            t = travel_time_min(d)
            c = travel_cost(d)
            day_dist += d
            day_cost_local += c
            current_time += t

            if i + 1 < len(path) - 1:
                poi = path[i + 1]
                if current_time < poi['open_min']:
                    current_time = float(poi['open_min'])
                if current_time > poi['close_min']:
                    violations.append(
                        f"Day {day_idx + 1}: ไปถึง {poi['id']} หลังเวลาปิด"
                    )
                arrivals.append((poi['id'], int(current_time)))
                day_score_local += poi['score']
                day_cost_local += poi['cost']
                current_time += poi['duration_min']

        day_time_total = current_time - DAY_START_MIN
        if day_time_total > day_time:
            violations.append(
                f"Day {day_idx + 1}: ใช้เวลาเกิน ({day_time_total:.0f} > {day_time} นาที)"
            )

        days_detail.append({
            'pois': [p['id'] for p in day_pois],
            'distance_km': round(day_dist, 2),
            'time_min': round(day_time_total, 1),
            'cost': round(day_cost_local, 0),
            'score': round(day_score_local, 1),
            'arrivals': arrivals
        })
        total_score += day_score_local
        total_cost += day_cost_local

    if total_cost > budget:
        violations.append(f"งบประมาณเกิน: {total_cost:.0f} > {budget}")

    return {
        'total_score': round(total_score, 1),
        'total_cost': round(total_cost, 0),
        'days_detail': days_detail,
        'valid': len(violations) == 0,
        'violations': violations
    }


def print_result(result: Dict, label: str = '', elapsed_ms: float = None):
    print('=' * 60)
    if label:
        print(f"  {label}")
        print('=' * 60)
    print(f"  Total score : {result['total_score']}")
    print(f"  Total cost  : {result['total_cost']:.0f}")
    print(f"  Valid       : {result['valid']}")
    if elapsed_ms is not None:
        print(f"  Runtime     : {elapsed_ms:.1f} ms")
    if result['violations']:
        print(f"  Violations  : {len(result['violations'])}")
        for v in result['violations'][:3]:
            print(f"    - {v}")
    print('  Days:')
    for i, d in enumerate(result['days_detail']):
        print(f"    Day {i + 1}: {len(d['pois'])} จุด - "
              f"score={d['score']}, time={d['time_min']:.0f}m, "
              f"cost={d['cost']:.0f}, dist={d['distance_km']}km")
        print(f"      {d['pois']}")
