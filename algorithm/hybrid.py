# -*- coding: utf-8 -*-
"""
hybrid.py - Hybrid Algorithm: Greedy seed + GA refinement + 2-opt local search

Workflow:
  1) Greedy slot-based → ได้ initial solution ที่ใช้งานได้ทันที
  2) GA refinement → ลองสับเปลี่ยน POIs ระหว่างวันเพื่อหา global optima
  3) 2-opt local search → ปรับลำดับ attractions ในแต่ละวันให้ travel distance น้อยสุด

ออกแบบให้รักษา slot pattern (slot 3 = lunch, slot 6 = dinner) ตลอดกระบวนการ
"""
import random
import copy
import time
from typing import List, Dict, Tuple
from utils import (haversine_km, travel_time_min, travel_cost,
                   evaluate_route, DAY_TIME_BUDGET, DAY_START_MIN)
from greedy import (greedy_solve, _find_best_for_slot,
                    LUNCH_TRIGGER, DINNER_TRIGGER)


# ============================================================
# 2-opt local search
# ============================================================
def _route_distance(day_pois: List[Dict], hotel: Dict) -> float:
    """Total travel distance for a day's route (hotel → POIs → hotel)"""
    if not day_pois:
        return 0.0
    path = [hotel] + day_pois + [hotel]
    total = 0.0
    for i in range(len(path) - 1):
        total += haversine_km(path[i]['lat'], path[i]['lng'],
                              path[i + 1]['lat'], path[i + 1]['lng'])
    return total


def two_opt_day(day_pois: List[Dict], hotel: Dict) -> List[Dict]:
    """2-opt swap optimization within a day.
    รักษาตำแหน่ง slot 3 (lunch) และ slot 6 (dinner) ไว้
    Only accepts swaps that don't create time-window violations.
    """
    n = len(day_pois)
    if n < 3:
        return day_pois

    # หา positions ที่เป็น restaurant - ห้ามขยับ
    fixed_positions = set()
    for idx, p in enumerate(day_pois):
        if p['category'] == 'restaurant':
            fixed_positions.add(idx)

    current = list(day_pois)
    current_dist = _route_distance(current, hotel)
    improved = True
    iters = 0
    while improved and iters < 50:
        improved = False
        iters += 1
        for i in range(n - 1):
            if i in fixed_positions:
                continue
            for j in range(i + 1, n):
                if j in fixed_positions:
                    continue
                # Try swap positions i and j
                trial = list(current)
                trial[i], trial[j] = trial[j], trial[i]
                trial_dist = _route_distance(trial, hotel)
                if trial_dist < current_dist - 0.01:
                    # Validate: no time violations after swap
                    ev = evaluate_route([trial], hotel, float('inf'))
                    if ev['valid']:
                        current = trial
                        current_dist = trial_dist
                        improved = True
                        break
            if improved:
                break
    return current


# ============================================================
# GA operators (slot-aware)
# ============================================================
def _slot_repair(chromosome: List[List[Dict]]) -> List[List[Dict]]:
    """แก้ chromosome ให้ตรงรูปแบบ slot:
       attractions ใน slots 1,2,4,5  +  restaurants ใน slots 3,6
       ถ้าไม่มี restaurant ในวัน → leave gap (skip slot)
    """
    repaired = []
    for day in chromosome:
        attrs = [p for p in day if p['category'] != 'restaurant']
        rests = [p for p in day if p['category'] == 'restaurant']

        # Cap to max 4 attractions, 2 restaurants
        attrs = attrs[:4]
        rests = rests[:2]

        # Build day in slot order: a,a,r,a,a,r
        new_day = []
        # Slot 1, 2: attrs[0], attrs[1] (if available)
        for i in range(2):
            if i < len(attrs):
                new_day.append(attrs[i])
        # Slot 3: lunch restaurant
        if len(rests) >= 1:
            new_day.append(rests[0])
        # Slot 4, 5: attrs[2], attrs[3]
        for i in range(2, 4):
            if i < len(attrs):
                new_day.append(attrs[i])
        # Slot 6: dinner restaurant
        if len(rests) >= 2:
            new_day.append(rests[1])
        repaired.append(new_day)

    # Remove cross-day duplicates
    seen = set()
    final = [[] for _ in repaired]
    for d, day in enumerate(repaired):
        for poi in day:
            if poi['id'] not in seen:
                seen.add(poi['id'])
                final[d].append(poi)
    return final


def _crossover(p1: List[List[Dict]], p2: List[List[Dict]]) -> List[List[Dict]]:
    """Day-level crossover: each day randomly inherits from p1 or p2"""
    days = len(p1)
    child = []
    for d in range(days):
        if random.random() < 0.5:
            child.append([dict(x) for x in p1[d]])
        else:
            child.append([dict(x) for x in p2[d]])
    return _slot_repair(child)


def _mutate(chromosome: List[List[Dict]], all_pois: List[Dict],
            mutation_rate: float = 0.3) -> List[List[Dict]]:
    """Mutation operators (slot-aware):
       - swap_attr: swap attraction with unused
       - swap_rest: swap restaurant with unused
       - move_across_days: move POI from one day to another
    """
    if random.random() > mutation_rate:
        return chromosome

    used_ids = {p['id'] for day in chromosome for p in day}
    unused_attrs = [p for p in all_pois if p['category'] != 'restaurant' and p['id'] not in used_ids]
    unused_rests = [p for p in all_pois if p['category'] == 'restaurant' and p['id'] not in used_ids]

    op = random.choice(['swap_attr', 'swap_rest', 'cross_day', 'remove'])

    if op == 'swap_attr' and unused_attrs:
        days_with_attr = [(d, [i for i, p in enumerate(chromosome[d])
                                if p['category'] != 'restaurant'])
                          for d in range(len(chromosome))]
        days_with_attr = [(d, idxs) for d, idxs in days_with_attr if idxs]
        if days_with_attr:
            d, idxs = random.choice(days_with_attr)
            i = random.choice(idxs)
            chromosome[d][i] = random.choice(unused_attrs)

    elif op == 'swap_rest' and unused_rests:
        days_with_rest = [(d, [i for i, p in enumerate(chromosome[d])
                                if p['category'] == 'restaurant'])
                          for d in range(len(chromosome))]
        days_with_rest = [(d, idxs) for d, idxs in days_with_rest if idxs]
        if days_with_rest:
            d, idxs = random.choice(days_with_rest)
            i = random.choice(idxs)
            chromosome[d][i] = random.choice(unused_rests)

    elif op == 'cross_day' and len(chromosome) >= 2:
        non_empty = [d for d in range(len(chromosome)) if chromosome[d]]
        if len(non_empty) >= 2:
            d1, d2 = random.sample(non_empty, 2)
            i = random.randrange(len(chromosome[d1]))
            j = random.randrange(len(chromosome[d2]))
            # Only swap same-category
            if chromosome[d1][i]['category'] == chromosome[d2][j]['category']:
                chromosome[d1][i], chromosome[d2][j] = chromosome[d2][j], chromosome[d1][i]

    elif op == 'remove':
        non_empty = [d for d in range(len(chromosome)) if chromosome[d]]
        if non_empty:
            d = random.choice(non_empty)
            i = random.randrange(len(chromosome[d]))
            chromosome[d].pop(i)

    return _slot_repair(chromosome)


# ============================================================
# Fitness function (slot + budget aware)
# ============================================================
def _fitness(chromosome: List[List[Dict]], hotel: Dict, budget: float,
             scoring_mode: str = 'ratio') -> float:
    result = evaluate_route(chromosome, hotel, budget)
    score = result['total_score']
    penalty = 0.0

    if result['total_cost'] > budget:
        penalty += (result['total_cost'] - budget) * 0.005
    for v in result['violations']:
        if 'งบประมาณเกิน' in v: pass
        elif 'ใช้เวลาเกิน' in v: penalty += 50.0
        elif 'หลังเวลาปิด' in v: penalty += 25.0
        else: penalty += 10.0

    # Slot pattern bonus: reward valid 6-slot days
    slot_bonus = 0.0
    for day in chromosome:
        n = len(day)
        if n == 0:
            continue
        # Reward exact 6 POIs
        if n == 6:
            slot_bonus += 3.0
        # Reward having lunch + dinner
        rests = [p for p in day if p['category'] == 'restaurant']
        if len(rests) >= 1:
            slot_bonus += 1.0
        if len(rests) >= 2:
            slot_bonus += 1.0
        # Penalty for too many restaurants
        if len(rests) > 2:
            penalty += (len(rests) - 2) * 5.0

    return score + slot_bonus - penalty


# ============================================================
# Meal fill — guarantee lunch + dinner in every day
# ============================================================
def meal_fill(routes: List[List[Dict]], pois: List[Dict], hotel: Dict,
              budget: float, scoring_mode: str = 'ratio') -> List[List[Dict]]:
    """Post-process GA/Hybrid result: use greedy slot logic to insert
    missing lunch and dinner into every day that lacks them.

    GA controls attraction selection (better global search);
    this ensures realistic meal slots are always present.
    """
    used_ids = {p['id'] for day in routes for p in day}
    ev = evaluate_route(routes, hotel, budget)
    remaining = max(0.0, budget - ev['total_cost'])

    new_routes = []
    for day_idx, day in enumerate(routes):
        attrs  = [p for p in day if p['category'] != 'restaurant']
        e_rest = [p for p in day if p['category'] == 'restaurant']

        # Already has lunch + dinner — just rearrange into slot order
        if len(e_rest) >= 2:
            new_day = (attrs[:2] + [e_rest[0]] + attrs[2:4] + [e_rest[1]])
            new_routes.append(new_day)
            continue

        # Split attractions into morning (slots 1-2) and afternoon (slots 4-5)
        morning   = attrs[:2]
        afternoon = attrs[2:4]
        days_left = max(1, len(routes) - day_idx)
        day_bgt   = remaining / days_left
        day_cats  = {}

        # --- Simulate time through morning attractions ---
        cur_t   = float(DAY_START_MIN)
        cur_pos = hotel
        for poi in morning:
            d = haversine_km(cur_pos['lat'], cur_pos['lng'],
                             poi['lat'], poi['lng'])
            cur_t += travel_time_min(d)
            if cur_t < poi['open_min']:
                cur_t = float(poi['open_min'])
            cur_t += poi['duration_min']
            cur_pos = poi
            day_cats[poi['category']] = day_cats.get(poi['category'], 0) + 1
            day_bgt -= travel_cost(d) + poi['cost']

        # Advance to lunch window
        if cur_t < LUNCH_TRIGGER:
            cur_t = float(LUNCH_TRIGGER)

        # --- Find lunch ---
        lunch = None
        if e_rest:
            # Use existing restaurant as lunch (already in used_ids)
            lunch = e_rest[0]
            d = haversine_km(cur_pos['lat'], cur_pos['lng'],
                             lunch['lat'], lunch['lng'])
            cur_t = max(cur_t + travel_time_min(d), float(lunch['open_min']))
            cur_t += lunch['duration_min']
            cur_pos = lunch
        else:
            r = _find_best_for_slot(pois, used_ids, cur_pos, cur_t, hotel,
                                    DAY_TIME_BUDGET, day_bgt, day_cats,
                                    'lunch', scoring_mode)
            if r:
                lunch, d_l, arr_l = r
                used_ids.add(lunch['id'])
                cost_l = travel_cost(d_l) + lunch['cost']
                day_bgt   -= cost_l
                remaining -= cost_l
                cur_t      = arr_l + lunch['duration_min']
                cur_pos    = lunch

        if lunch:
            day_cats['restaurant'] = day_cats.get('restaurant', 0) + 1

        # --- Simulate time through afternoon attractions ---
        for poi in afternoon:
            d = haversine_km(cur_pos['lat'], cur_pos['lng'],
                             poi['lat'], poi['lng'])
            cur_t += travel_time_min(d)
            if cur_t < poi['open_min']:
                cur_t = float(poi['open_min'])
            cur_t += poi['duration_min']
            cur_pos = poi
            day_cats[poi['category']] = day_cats.get(poi['category'], 0) + 1
            day_bgt -= travel_cost(d) + poi['cost']

        # Advance to dinner window
        if cur_t < DINNER_TRIGGER:
            cur_t = float(DINNER_TRIGGER)

        # --- Find dinner ---
        dinner = None
        r = _find_best_for_slot(pois, used_ids, cur_pos, cur_t, hotel,
                                DAY_TIME_BUDGET, day_bgt, day_cats,
                                'dinner', scoring_mode)
        if r is None:
            # Fallback: relax budget — dinner is a hard requirement
            meal_cap = max(500, budget * 0.08)
            r = _find_best_for_slot(pois, used_ids, cur_pos, cur_t, hotel,
                                    DAY_TIME_BUDGET, meal_cap, day_cats,
                                    'dinner', scoring_mode)
        if r is None:
            # Last resort: free restaurants only
            r = _find_best_for_slot(pois, used_ids, cur_pos, cur_t, hotel,
                                    DAY_TIME_BUDGET, 1e9, day_cats,
                                    'dinner', scoring_mode, free_only=True)
        if r:
            dinner, d_d, arr_d = r
            used_ids.add(dinner['id'])
            remaining -= travel_cost(d_d) + dinner['cost']

        # --- Assemble day in slot order ---
        new_day = list(morning)
        if lunch:    new_day.append(lunch)
        new_day.extend(afternoon)
        if dinner:   new_day.append(dinner)
        new_routes.append(new_day)

    return new_routes


# ============================================================
# Time repair — remove worst attr from over-budget days
# ============================================================
def _time_repair(routes: List[List[Dict]], hotel: Dict) -> List[List[Dict]]:
    """Remove violating non-restaurant POIs from days that:
      (a) exceed DAY_TIME_BUDGET, or
      (b) contain POIs visited after their closing time.
    Preserves restaurant (meal) slots."""
    import re as _re
    routes = [list(d) for d in routes]
    for d_idx in range(len(routes)):
        for _ in range(10):  # max 10 removals per day
            ev = evaluate_route([routes[d_idx]], hotel, float('inf'))
            day_viols = [v for v in ev['violations'] if f'Day 1:' in v]
            time_ok = ev['days_detail'][0]['time_min'] <= DAY_TIME_BUDGET
            if time_ok and not day_viols:
                break

            # Collect IDs of POIs that arrived after closing time
            late_ids = set()
            for v in day_viols:
                if 'หลังเวลาปิด' in v:
                    m = _re.search(r'ไปถึง (\S+) หลังเวลาปิด', v)
                    if m:
                        late_ids.add(m.group(1))

            # Priority: remove a late-arrival POI first, else lowest-score attr
            worst_i = None
            if late_ids:
                for i, p in enumerate(routes[d_idx]):
                    if p['id'] in late_ids and p['category'] != 'restaurant':
                        worst_i = i
                        break
            if worst_i is None:
                worst_score = float('inf')
                for i, p in enumerate(routes[d_idx]):
                    if p['category'] != 'restaurant' and p['score'] < worst_score:
                        worst_score = p['score']; worst_i = i
            if worst_i is None:
                break
            routes[d_idx].pop(worst_i)
    return routes


# ============================================================
# Hybrid main
# ============================================================
def hybrid_solve(pois: List[Dict], hotel: Dict, days: int, budget: float,
                 scoring_mode: str = 'ratio',
                 pop_size: int = 30, generations: int = 60,
                 mutation_rate: float = 0.3,
                 verbose: bool = False) -> Tuple[List[List[Dict]], List[float]]:
    """Hybrid Algorithm:
       Step 1: Greedy slot-based seed (multiple random starts)
       Step 2: GA refinement
       Step 3: 2-opt local search per day
       Returns: (best_chromosome, fitness_history)
    """
    # Step 1: Initial population from multiple greedy seeds with different POI orders
    population = []
    seed_pois = list(pois)
    random.shuffle(seed_pois)
    population.append(greedy_solve(seed_pois, hotel, days, budget, scoring_mode=scoring_mode))
    population.append(greedy_solve(pois, hotel, days, budget, scoring_mode=scoring_mode))
    while len(population) < pop_size:
        random.shuffle(seed_pois)
        cand = greedy_solve(seed_pois, hotel, days, budget, scoring_mode=scoring_mode)
        population.append(cand)

    fitnesses = [_fitness(c, hotel, budget, scoring_mode) for c in population]

    best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
    best = copy.deepcopy(population[best_idx])
    best_fit = fitnesses[best_idx]
    history = [best_fit]
    no_improve = 0
    EARLY_STOP = 15

    # Step 2: GA evolution
    for gen in range(generations):
        new_pop = [copy.deepcopy(best)]  # elitism

        # Adaptive mutation rate (decrease over generations)
        cur_mut_rate = mutation_rate * (1.0 - gen / (2.0 * generations))

        while len(new_pop) < pop_size:
            # Tournament selection k=3
            c1 = random.sample(range(len(population)), 3)
            p1 = population[max(c1, key=lambda i: fitnesses[i])]
            c2 = random.sample(range(len(population)), 3)
            p2 = population[max(c2, key=lambda i: fitnesses[i])]
            child = _crossover(p1, p2)
            child = _mutate(child, pois, cur_mut_rate)
            new_pop.append(child)

        population = new_pop
        fitnesses = [_fitness(c, hotel, budget, scoring_mode) for c in population]

        cur_best = max(range(len(population)), key=lambda i: fitnesses[i])
        if fitnesses[cur_best] > best_fit:
            best_fit = fitnesses[cur_best]
            best = copy.deepcopy(population[cur_best])
            no_improve = 0
        else:
            no_improve += 1

        history.append(best_fit)
        if verbose and gen % 10 == 0:
            print(f"  Gen {gen}: fitness={best_fit:.2f}")
        # Early stopping
        if no_improve >= EARLY_STOP:
            if verbose:
                print(f"  Early stop at gen {gen} (no improvement for {EARLY_STOP} gens)")
            break

    # Step 3: 2-opt local search on best solution
    refined = []
    for day in best:
        refined.append(two_opt_day(day, hotel))

    # Step 4: Guarantee lunch + dinner in every day
    refined = meal_fill(refined, pois, hotel, budget, scoring_mode)

    # Step 5: Remove attrs from days that still exceed time budget
    refined = _time_repair(refined, hotel)

    return refined, history


def main():
    from utils import load_data, print_result
    pois, hotels = load_data('../data/phuket_pois.json')
    h = next(h for h in hotels if h['id'] == 'H11')
    print(f"Hotel: {h['name_en']}")
    t0 = time.time()
    routes, history = hybrid_solve(pois, h, 6, 6800, verbose=True)
    elapsed = (time.time() - t0) * 1000
    print(f"\nElapsed: {elapsed:.0f} ms")
    print(f"History: gen0={history[0]:.1f} → final={history[-1]:.1f}")
    result = evaluate_route(routes, h, 6800)
    print_result(result, label='Hybrid')


if __name__ == '__main__':
    main()
