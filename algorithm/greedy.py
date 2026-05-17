# -*- coding: utf-8 -*-
"""greedy.py v11 - slot-based, realistic meal windows, dinner buffer, randomised"""
import random
from typing import List, Dict
from utils import (haversine_km, travel_time_min, travel_cost,
                   DAY_TIME_BUDGET, DAY_START_MIN)

DAY_PATTERN    = ['attr', 'attr', 'lunch', 'attr', 'attr', 'dinner']
LUNCH_TRIGGER  = 690
DINNER_TRIGGER = 1020
LUNCH_ARRIVE   = (600,  840)
DINNER_ARRIVE  = (1020, 1260)
MAX_MEAL_WAIT  = 90
DINNER_BUFFER_MIN = 150


def _find_best_for_slot(pois, used_ids, current_pos, current_time, hotel,
                        day_time, budget_left, day_categories,
                        slot_type, scoring_mode='ratio',
                        free_only=False, dinner_buffer=0, random_factor=0.0):
    candidates = []
    for poi in pois:
        if poi['id'] in used_ids: continue
        if slot_type == 'attr' and poi['category'] == 'restaurant': continue
        if slot_type in ('lunch', 'dinner') and poi['category'] != 'restaurant': continue
        if free_only and poi['cost'] > 0: continue
        if poi['duration_min'] > 240 and slot_type == 'attr': continue
        d_to   = haversine_km(current_pos['lat'], current_pos['lng'], poi['lat'], poi['lng'])
        d_back = haversine_km(poi['lat'], poi['lng'], hotel['lat'], hotel['lng'])
        travel_t = travel_time_min(d_to)
        back_t   = travel_time_min(d_back)
        arrive_raw = current_time + travel_t
        if arrive_raw < poi['open_min']:
            wait = poi['open_min'] - arrive_raw
            max_wait = MAX_MEAL_WAIT if slot_type in ('lunch', 'dinner') else 60
            if wait > max_wait: continue
            arrive = float(poi['open_min'])
        else:
            arrive = arrive_raw
        if arrive > poi['close_min']: continue
        if slot_type == 'lunch' and not (LUNCH_ARRIVE[0] <= arrive <= LUNCH_ARRIVE[1]): continue
        if slot_type == 'dinner' and not (DINNER_ARRIVE[0] <= arrive <= DINNER_ARRIVE[1]): continue
        finish = arrive + poi['duration_min']
        if (finish + back_t + dinner_buffer) - DAY_START_MIN > day_time: continue
        add_cost = travel_cost(d_to) + poi['cost']
        if poi['cost'] > 0 and add_cost > budget_left: continue
        cat_count = day_categories.get(poi['category'], 0)
        diversity_bonus = 1.0 if cat_count == 0 else (1.0 / (1 + cat_count * 0.5))
        if scoring_mode == 'quality':
            base_score = poi['score'] * diversity_bonus
        else:
            # ratio mode: ใช้ floor 80 เพื่อป้องกัน POI ฟรีใกล้ๆ ชนะเสมอจากระยะทาง
            # → POI ฟรีทุกอันแข่งกันด้วย score เป็นหลัก + noise กระจายได้จริง
            effective_cost = max(add_cost, 80.0)
            base_score = (poi['score'] * diversity_bonus) / (effective_cost + 1.0)
        noise = 1.0 + random.uniform(-random_factor, random_factor) if random_factor > 0 else 1.0
        score = base_score * noise
        candidates.append((score, poi, d_to, arrive))
    if not candidates: return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, best, best_d_to, best_arrive = candidates[0]
    return (best, best_d_to, best_arrive)


def greedy_solve(pois, hotel, days, budget, day_time=DAY_TIME_BUDGET,
                 scoring_mode='ratio', random_factor=0.15):
    used_ids = set()
    remaining_budget = float(budget)
    routes = [[] for _ in range(days)]
    per_day_budget = (budget / max(days, 1)) * 1.1

    pois_shuffled = list(pois)
    random.shuffle(pois_shuffled)

    for day_idx in range(days):
        current_pos = hotel
        current_time = float(DAY_START_MIN)
        day_categories = {}
        day_budget_left = min(per_day_budget, remaining_budget)
        past_lunch = False
        dinner_done = False

        for slot_type in DAY_PATTERN:
            if slot_type == 'lunch' and current_time < LUNCH_TRIGGER:
                current_time = float(LUNCH_TRIGGER)
            elif slot_type == 'dinner' and current_time < DINNER_TRIGGER:
                current_time = float(DINNER_TRIGGER)

            db = DINNER_BUFFER_MIN if (slot_type == 'attr' and past_lunch and not dinner_done) else 0

            result = _find_best_for_slot(
                pois_shuffled, used_ids, current_pos, current_time, hotel, day_time,
                day_budget_left, day_categories, slot_type, scoring_mode,
                dinner_buffer=db, random_factor=random_factor)

            if result is None and slot_type in ('lunch', 'dinner'):
                # Fallback 1: give meals a generous budget cap
                meal_cap = max(300, remaining_budget * 0.5)
                result = _find_best_for_slot(
                    pois_shuffled, used_ids, current_pos, current_time, hotel, day_time,
                    meal_cap, day_categories, slot_type, scoring_mode,
                    dinner_buffer=0, random_factor=random_factor)

            if result is None and slot_type in ('lunch', 'dinner'):
                # Fallback 2: any restaurant regardless of budget (must eat)
                result = _find_best_for_slot(
                    pois_shuffled, used_ids, current_pos, current_time, hotel, day_time,
                    1e9, day_categories, slot_type, scoring_mode,
                    dinner_buffer=0, random_factor=random_factor)

            if result is None:
                # Fallback: free POIs only
                result = _find_best_for_slot(
                    pois_shuffled, used_ids, current_pos, current_time, hotel, day_time,
                    1e9, day_categories, slot_type, scoring_mode,
                    free_only=True, dinner_buffer=db, random_factor=random_factor)

            if result is None and slot_type == 'attr' and not past_lunch:
                result = _find_best_for_slot(
                    pois_shuffled, used_ids, current_pos, current_time, hotel, day_time,
                    day_budget_left, day_categories, 'attr', scoring_mode,
                    dinner_buffer=0, random_factor=random_factor)

            if slot_type == 'lunch': past_lunch = True
            if slot_type == 'dinner': dinner_done = True
            if result is None: continue

            poi, d_to, arrive = result
            used_ids.add(poi['id'])
            routes[day_idx].append(poi)
            current_time = arrive + poi['duration_min']
            current_pos = poi
            spent = travel_cost(d_to) + poi['cost']
            remaining_budget -= spent
            day_budget_left = max(0, day_budget_left - spent)
            day_categories[poi['category']] = day_categories.get(poi['category'], 0) + 1

        if routes[day_idx]:
            d_back = haversine_km(current_pos['lat'], current_pos['lng'],
                                  hotel['lat'], hotel['lng'])
            remaining_budget -= travel_cost(d_back)
    return routes
