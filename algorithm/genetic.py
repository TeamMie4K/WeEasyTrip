# -*- coding: utf-8 -*-
"""
genetic.py - Genetic Algorithm สำหรับปัญหา B-TOPTW

โครงสร้าง chromosome: list of list ของ POI dict
  chromosome = [
      [poi_a, poi_b, ...],   # day 1
      [poi_c, poi_d, ...],   # day 2
      ...
  ]

Operators:
  - Initialization: greedy seed + random
  - Selection:      tournament (k=3)
  - Crossover:      day-level swap (เลือก parent ของแต่ละวันแบบสุ่ม)
  - Mutation:       swap / insert / remove
  - Repair:         ลบ POI ที่แย่ที่สุดออกถ้าละเมิด constraint
  - Replacement:    elitism (เก็บ best ไว้ทุก gen)
"""
import random
import time
import copy
from typing import List, Dict, Tuple
from utils import (evaluate_route, DAY_TIME_BUDGET, DAY_START_MIN)
from greedy import greedy_solve
from hybrid import meal_fill


# ============================================================
# Fitness function
# ============================================================
def fitness(chromosome: List[List[Dict]], hotel: Dict, budget: float) -> float:
    """fitness = total_score - penalty(violations + schedule imbalance)
    soft constraint: penalize budget, time/window, and unrealistic schedule"""
    result = evaluate_route(chromosome, hotel, budget)
    score = result['total_score']
    penalty = 0.0

    if result['total_cost'] > budget:
        penalty += (result['total_cost'] - budget) * 0.005

    for v in result['violations']:
        if 'งบประมาณเกิน' in v:
            pass
        elif 'ใช้เวลาเกิน' in v:
            penalty += 5.0
        elif 'หลังเวลาปิด' in v:
            penalty += 3.0
        else:
            penalty += 2.0

    # Schedule balance: each day must look like a real travel day
    for day in chromosome:
        if not day:
            continue
        cats = [p['category'] for p in day]
        n_rest = sum(1 for c in cats if c == 'restaurant')
        n_attr = sum(1 for c in cats if c != 'restaurant')

        # 1) จำกัดร้านอาหาร 2 ต่อวัน (lunch + dinner)
        if n_rest > 2:
            penalty += (n_rest - 2) * 12.0
        # 1b) ขาดร้านอาหาร = penalty หนัก
        if n_rest == 0:
            penalty += 20.0
        elif n_rest == 1:
            penalty += 10.0
        # 2) วันที่มีแต่ร้านอาหาร ไม่มีที่เที่ยว = penalty หนัก
        if n_rest > 0 and n_attr == 0:
            penalty += 25.0
        # 3) จุดท่องเที่ยวน้อยเกิน
        if n_attr < 2 and len(day) > 0:
            penalty += 4.0
        # 4) วันที่ทุกจุดเป็นหมวดเดียวกัน
        unique_cats = len(set(cats))
        if len(day) >= 3 and unique_cats < 2:
            penalty += 6.0

    return score - penalty


# ============================================================
# Initial population
# ============================================================
def initial_population(pois: List[Dict], hotel: Dict, days: int,
                       budget: float, pop_size: int = 50) -> List[List[List[Dict]]]:
    """สร้าง population เริ่มต้นจาก greedy seeds ที่ shuffle POI order ต่างกัน
    วิธีนี้ทำให้ทุก chromosome มี meal structure ครบ (lunch + dinner) ตั้งแต่ต้น
    ทำให้ GA วิ่งจาก valid starting points แทนที่จะเริ่มจาก random ที่ไม่มีร้านอาหาร"""
    population = []

    # Primary greedy seed (original POI order)
    population.append(greedy_solve(pois, hotel, days, budget))

    # Greedy seeds with shuffled POI orders (เหมือน Hybrid)
    seed_pois = list(pois)
    while len(population) < pop_size:
        random.shuffle(seed_pois)
        cand = greedy_solve(seed_pois, hotel, days, budget)
        population.append(cand)

    return population


# ============================================================
# Selection
# ============================================================
def tournament_select(population: List, fitnesses: List[float],
                      k: int = 3) -> List[List[Dict]]:
    """Tournament selection - เลือก k ตัวสุ่ม คืนตัวที่ fitness สูงสุด"""
    contestants = random.sample(range(len(population)), k)
    best_idx = contestants[0]
    for c in contestants[1:]:
        if fitnesses[c] > fitnesses[best_idx]:
            best_idx = c
    return copy.deepcopy(population[best_idx])


# ============================================================
# Crossover
# ============================================================
def crossover(parent1: List[List[Dict]],
              parent2: List[List[Dict]]) -> List[List[Dict]]:
    """Day-level crossover: แต่ละวันสุ่มเอามาจาก p1 หรือ p2
    แล้วลบ duplicate ข้ามวัน (POI ห้ามซ้ำ)"""
    days = len(parent1)
    child: List[List[Dict]] = []
    for d in range(days):
        if random.random() < 0.5:
            child.append([dict(p) for p in parent1[d]])
        else:
            child.append([dict(p) for p in parent2[d]])

    # remove duplicates
    seen = set()
    new_child: List[List[Dict]] = [[] for _ in range(days)]
    for d in range(days):
        for poi in child[d]:
            if poi['id'] not in seen:
                seen.add(poi['id'])
                new_child[d].append(poi)
    return new_child


# ============================================================
# Mutation
# ============================================================
def mutate(chromosome: List[List[Dict]], all_pois: List[Dict],
           mutation_rate: float = 0.3) -> List[List[Dict]]:
    """3 mutations: swap (สลับใน-ระหว่างวัน), insert, remove"""
    if random.random() > mutation_rate:
        return chromosome

    days = len(chromosome)
    used_ids = set(p['id'] for day in chromosome for p in day)
    op = random.choice(['swap', 'insert', 'remove', 'cross_day_swap'])

    if op == 'swap':
        days_with_2 = [i for i, day in enumerate(chromosome) if len(day) >= 2]
        if days_with_2:
            d = random.choice(days_with_2)
            i, j = random.sample(range(len(chromosome[d])), 2)
            chromosome[d][i], chromosome[d][j] = chromosome[d][j], chromosome[d][i]
    elif op == 'cross_day_swap' and days >= 2:
        non_empty = [i for i, day in enumerate(chromosome) if day]
        if len(non_empty) >= 2:
            d1, d2 = random.sample(non_empty, 2)
            i = random.randrange(len(chromosome[d1]))
            j = random.randrange(len(chromosome[d2]))
            chromosome[d1][i], chromosome[d2][j] = chromosome[d2][j], chromosome[d1][i]
    elif op == 'insert':
        unused = [p for p in all_pois if p['id'] not in used_ids]
        if unused:
            poi = random.choice(unused)
            d = random.randrange(days)
            pos = random.randint(0, len(chromosome[d]))
            chromosome[d].insert(pos, poi)
    elif op == 'remove':
        non_empty = [i for i, day in enumerate(chromosome) if day]
        if non_empty:
            d = random.choice(non_empty)
            idx = random.randrange(len(chromosome[d]))
            chromosome[d].pop(idx)

    return chromosome


# ============================================================
# Repair
# ============================================================
def repair(chromosome: List[List[Dict]], hotel: Dict,
           budget: float) -> List[List[Dict]]:
    """ลบ POI ที่ ratio score/cost ต่ำที่สุดออก จนกว่าจะ valid
    หรือ chromosome ว่าง"""
    result = evaluate_route(chromosome, hotel, budget)
    max_iter = 50
    while not result['valid'] and max_iter > 0:
        worst_d, worst_i = None, None
        worst_ratio = float('inf')
        for d, day in enumerate(chromosome):
            for i, poi in enumerate(day):
                ratio = poi['score'] / (poi['cost'] + 1.0)
                if ratio < worst_ratio:
                    worst_ratio = ratio
                    worst_d, worst_i = d, i
        if worst_d is None:
            break
        chromosome[worst_d].pop(worst_i)
        result = evaluate_route(chromosome, hotel, budget)
        max_iter -= 1
    return chromosome


# ============================================================
# Main GA loop
# ============================================================
def genetic_solve(pois: List[Dict], hotel: Dict, days: int, budget: float,
                  pop_size: int = 50, generations: int = 100,
                  mutation_rate: float = 0.3, verbose: bool = False
                  ) -> Tuple[List[List[Dict]], List[float]]:
    """แก้ปัญหา B-TOPTW ด้วย Genetic Algorithm

    Returns: (best_chromosome, history of best_fitness per gen)
    """
    population = initial_population(pois, hotel, days, budget, pop_size)
    fitnesses = [fitness(c, hotel, budget) for c in population]

    best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
    best_chromosome = copy.deepcopy(population[best_idx])
    best_fitness = fitnesses[best_idx]
    history = [best_fitness]

    for gen in range(generations):
        new_pop = [copy.deepcopy(best_chromosome)]  # elitism

        while len(new_pop) < pop_size:
            p1 = tournament_select(population, fitnesses)
            p2 = tournament_select(population, fitnesses)
            child = crossover(p1, p2)
            child = mutate(child, pois, mutation_rate)
            child = repair(child, hotel, budget)
            new_pop.append(child)

        population = new_pop
        fitnesses = [fitness(c, hotel, budget) for c in population]

        cur_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
        if fitnesses[cur_best_idx] > best_fitness:
            best_fitness = fitnesses[cur_best_idx]
            best_chromosome = copy.deepcopy(population[cur_best_idx])

        history.append(best_fitness)
        if verbose and gen % 20 == 0:
            print(f"  Gen {gen:3d}: best fitness = {best_fitness:.2f}")

    # Guarantee lunch + dinner in every day
    best_chromosome = meal_fill(best_chromosome, pois, hotel, budget)

    # Remove attrs from days that still exceed time budget
    from hybrid import _time_repair
    best_chromosome = _time_repair(best_chromosome, hotel)

    return best_chromosome, history


def main():
    from utils import load_data, print_result
    random.seed(42)
    pois, hotels = load_data('../data/phuket_pois.json')
    hotel = hotels[1]  # Novotel Karon

    print(f"\n{'=' * 60}")
    print(f"  Genetic Algorithm Test")
    print(f"{'=' * 60}")
    print(f"  Hotel:  {hotel['name_en']}")
    print(f"  POIs:   {len(pois)}")
    print(f"  Days:   3")
    print(f"  Budget: 15,000 บาท")
    print(f"  Population: 50, Generations: 100, Mutation: 0.3")
    print(f"\n  Running GA...")

    days = 3
    budget = 15000

    t0 = time.time()
    routes, history = genetic_solve(pois, hotel, days, budget,
                                    pop_size=50, generations=100,
                                    mutation_rate=0.3, verbose=True)
    elapsed_ms = (time.time() - t0) * 1000

    result = evaluate_route(routes, hotel, budget)
    print_result(result, label='GA Result', elapsed_ms=elapsed_ms)

    print(f"\n  Convergence: gen 0 fitness = {history[0]:.1f}, "
          f"final = {history[-1]:.1f}, "
          f"improvement = {history[-1] - history[0]:.1f}")


if __name__ == '__main__':
    main()
