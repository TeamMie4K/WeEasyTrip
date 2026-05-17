# -*- coding: utf-8 -*-
"""FastAPI Backend - WeEasyTrip"""
import sys, os, time, random
from typing import List, Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(THIS_DIR), 'algorithm'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from utils import load_data, evaluate_route
from greedy import greedy_solve
from genetic import genetic_solve
from hybrid import hybrid_solve

DATA_PATH = os.path.join(os.path.dirname(THIS_DIR), 'data', 'phuket_pois.json')
POIS, HOTELS = load_data(DATA_PATH)
HOTEL_BY_ID = {h['id']: h for h in HOTELS}
POI_BY_ID = {p['id']: p for p in POIS}


class PackageRequest(BaseModel):
    budget: float = Field(..., ge=1000, le=100000)
    days: int = Field(..., ge=1, le=7)
    travelers: int = Field(1, ge=1, le=10)
    seed: Optional[int] = Field(None, description="Random seed; None = random every call")
    algorithm: Optional[str] = Field('hybrid', description="'greedy' | 'ga' | 'hybrid'")
    include_hotel: Optional[bool] = Field(True, description="รวมค่าโรงแรมในงบหรือไม่")


class RecomputeRequest(BaseModel):
    hotel_id: str
    days: int
    budget: float
    routes: List[List[str]]
    travelers: int = 1


class DayDetail(BaseModel):
    day: int
    pois: List[dict]
    distance_km: float
    time_min: float
    cost: float
    score: float


class Package(BaseModel):
    tier: str
    hotel: dict
    days: List[DayDetail]
    total_score: float
    total_activity_cost: float
    total_hotel_cost: float
    total_cost: float
    runtime_ms: float
    valid: bool
    violations: List[str]


class PackageResponse(BaseModel):
    request: dict
    packages: List[Package]


def make_day_details(routes_per_day, hotel, travelers=1):
    eval_result = evaluate_route(routes_per_day, hotel, budget=float('inf'))
    days = []
    for i, day_pois in enumerate(routes_per_day):
        det = eval_result['days_detail'][i]
        days.append(DayDetail(
            day=i + 1,
            pois=[{
                'id': p['id'], 'name_th': p['name_th'], 'name_en': p['name_en'],
                'category': p['category'], 'lat': p['lat'], 'lng': p['lng'],
                'score': p['score'], 'cost': p['cost'] * travelers,
                'duration_min': p['duration_min'],
            } for p in day_pois],
            distance_km=det['distance_km'],
            time_min=det['time_min'],
            cost=det['cost'] * travelers,
            score=det['score']
        ))
    return days, eval_result


def _trim_to_budget(routes, hotel, max_activity_budget, travelers):
    """4-phase budget + time-window enforcement:
       1) Swap expensive restaurants → cheaper unused
       2) Remove paid attractions (highest cost first)
       3) Remove any POI (incl. restaurants) if still over budget
       4) Remove POIs causing time-window violations
    """
    import re as _re
    from utils import evaluate_route as _eval

    def _check(rts):
        r = _eval(rts, hotel, budget=float('inf'))
        # Budget ครอบคลุมเฉพาะ ค่าเข้า + ค่าอาหาร (per-person × travelers)
        # ค่าเดินทาง (transportation) ถือเป็น overhead ไม่นับในงบกิจกรรม
        poi_cost = sum(p['cost'] for day in rts for p in day) * travelers
        return poi_cost, r

    used_ids = {p['id'] for day in routes for p in day}
    unused_rest = sorted(
        [p for p in POIS if p['category'] == 'restaurant' and p['id'] not in used_ids],
        key=lambda x: x['cost'])

    # Phase 1: swap expensive restaurants → cheaper unused
    for cheap_rest in unused_rest:
        total_act, _ = _check(routes)
        if total_act <= max_activity_budget:
            break
        worst_d, worst_i, worst_cost = None, None, cheap_rest['cost']
        for di, day in enumerate(routes):
            for pi, p in enumerate(day):
                if p['category'] == 'restaurant' and p['cost'] > worst_cost:
                    worst_cost = p['cost']; worst_d, worst_i = di, pi
        if worst_d is None:
            break
        old_id = routes[worst_d][worst_i]['id']
        routes[worst_d][worst_i] = cheap_rest
        used_ids.discard(old_id)
        used_ids.add(cheap_rest['id'])

    # Phase 2: remove paid attractions (highest cost first)
    while True:
        total_act, _ = _check(routes)
        if total_act <= max_activity_budget:
            break
        worst_d, worst_i, worst_cost = None, None, 0
        for di, day in enumerate(routes):
            for pi, p in enumerate(day):
                if p['category'] != 'restaurant' and p['cost'] > worst_cost:
                    worst_cost = p['cost']; worst_d, worst_i = di, pi
        if worst_d is None:
            break
        routes[worst_d].pop(worst_i)

    # Phase 3: remove any POI (incl. restaurants) if still over budget
    while True:
        total_act, _ = _check(routes)
        if total_act <= max_activity_budget:
            break
        worst_d, worst_i, worst_cost = None, None, -1
        for di, day in enumerate(routes):
            for pi, p in enumerate(day):
                if p['cost'] > worst_cost:
                    worst_cost = p['cost']; worst_d, worst_i = di, pi
        if worst_d is None:
            break
        routes[worst_d].pop(worst_i)

    # Phase 4: remove POIs arriving after close time
    for _ in range(30):
        _, result = _check(routes)
        tw = [v for v in result['violations'] if 'หลังเวลาปิด' in v]
        if not tw:
            break
        removed = False
        for viol in tw:
            m = _re.search(r'ไปถึง (\S+) หลังเวลาปิด', viol)
            if not m:
                continue
            bad_id = m.group(1)
            for di, day in enumerate(routes):
                for pi, p in enumerate(day):
                    if p['id'] == bad_id:
                        routes[di].pop(pi)
                        removed = True
                        break
                if removed:
                    break
        if not removed:
            break

    return routes


def build_package(tier, hotel, routes, days, budget, runtime_ms, travelers,
                  max_total_budget=None, hotel_cost_override=None):
    nights = max(0, days - 1)
    hotel_cost = hotel_cost_override if hotel_cost_override is not None else hotel['cost'] * nights
    # Enforce max_total_budget if given
    if max_total_budget is not None:
        max_activity = max(0, max_total_budget - hotel_cost)
        routes = _trim_to_budget(routes, hotel, max_activity, travelers)
    day_details, eval_result = make_day_details(routes, hotel, travelers)
    activity_cost = sum(d.cost for d in day_details)
    total = activity_cost + hotel_cost
    violations = list(eval_result['violations'])
    valid = eval_result['valid']
    return Package(
        tier=tier, hotel=hotel, days=day_details,
        total_score=eval_result['total_score'] if valid else 0,
        total_activity_cost=activity_cost,
        total_hotel_cost=hotel_cost,
        total_cost=total,
        runtime_ms=runtime_ms,
        valid=valid,
        violations=violations
    )


app = FastAPI(title='WeEasyTrip API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'],
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


@app.get('/api/health')
def health():
    return {'status': 'ok', 'pois': len(POIS), 'hotels': len(HOTELS)}


@app.get('/api/pois')
def get_pois():
    return {'pois': POIS, 'hotels': HOTELS}


@app.post('/api/packages', response_model=PackageResponse)
def create_packages(req: PackageRequest):
    """3 packages with realistic budget differentiation + algorithm selector."""
    # Use provided seed for reproducibility; None → random each call
    random.seed(req.seed)

    # tier: (name, hotel_r, total_r, scoring_mode, score_pct, max_rest_cost)
    # score_pct: percentile ของ attraction score สูงสุดที่อนุญาต
    # max_rest_cost: ราคาร้านอาหารสูงสุด (None = ไม่จำกัด)
    tier_specs = [
        ('Budget',   0.20, 0.40, 'ratio',   0.50,  150),  # ร้านถูก + attr ระดับกลาง
        ('Standard', 0.45, 0.75, 'quality', 0.80,  400),  # ร้านกลาง + attr ระดับดี
        ('Premium',  0.55, 1.00, 'quality', None,  None), # ทุกอย่าง เน้น score สูงสุด
    ]
    all_pois = POIS
    sorted_hotels = sorted(HOTELS, key=lambda h: h['cost'])

    # คำนวณ score threshold จาก non-restaurant POIs
    _attr_scores = sorted(p['score'] for p in all_pois if p['category'] != 'restaurant')
    def _percentile(lst, pct):
        idx = max(0, int(len(lst) * pct) - 1)
        return lst[idx]

    def make_tier_pois(score_pct, max_rest_cost=None):
        """กรอง POI ตาม tier:
           - attr: กรองตาม score percentile
           - restaurant: กรองตาม max_rest_cost เพื่อให้ tier ต่างกันชัดเจน
        """
        result = []
        attr_max = _percentile(_attr_scores, score_pct) if score_pct is not None else float('inf')
        for p in all_pois:
            if p['category'] == 'restaurant':
                if max_rest_cost is None or p['cost'] <= max_rest_cost:
                    result.append(p)
            else:
                if p['score'] <= attr_max:
                    result.append(p)
        return result

    def find_best_hotel(max_per_night, exclude):
        cands = [h for h in sorted_hotels
                 if h['cost'] <= max_per_night and h['id'] not in exclude]
        if not cands:
            free = [h for h in sorted_hotels if h['id'] not in exclude]
            return free[0] if free else None
        return max(cands, key=lambda h: h['score'])

    packages = []
    picked = set()
    algo = (req.algorithm or 'hybrid').lower()

    nights = max(0, req.days - 1)
    include_hotel = req.include_hotel if req.include_hotel is not None else True

    for tier, hotel_r, total_r, mode, score_pct, max_rest_cost in tier_specs:
        if include_hotel:
            max_per_night = req.budget * hotel_r / max(nights, 1) if nights > 0 else 0
            hotel = find_best_hotel(max_per_night, picked) if nights > 0 else sorted_hotels[0]
        else:
            # ไม่รวมโรงแรม: เลือกโรงแรมถูกสุดสำหรับ routing เท่านั้น
            avail = [h for h in sorted_hotels if h['id'] not in picked]
            hotel = avail[0] if avail else sorted_hotels[0]

        if hotel is None:
            packages.append(Package(
                tier=tier, hotel=sorted_hotels[0],
                days=[DayDetail(day=i+1, pois=[], distance_km=0, time_min=0,
                                cost=0, score=0) for i in range(req.days)],
                total_score=0, total_activity_cost=0, total_hotel_cost=0,
                total_cost=0, runtime_ms=0, valid=False,
                violations=[f'No hotel for {tier}']
            ))
            continue
        picked.add(hotel['id'])

        # คำนวณค่าโรงแรม (0 ถ้าไม่รวมโรงแรม หรือทริปวันเดียว)
        hotel_total = hotel['cost'] * nights if include_hotel else 0

        # งบสำหรับกิจกรรม
        target_total = req.budget * total_r
        budget_for_act = max(0, target_total - hotel_total) / req.travelers

        # Dynamic restaurant cap สำหรับ quality mode:
        # ป้องกันร้านอาหารแพงกินงบหมดในทริปงบต่ำ
        # Budget tier ใช้ ratio scoring ซึ่ง penalize ร้านแพงอยู่แล้ว → ไม่ต้องแตะ
        if mode == 'quality':
            # จัดสรรสูงสุด 1/5 ของงบต่อวันต่อมื้อ
            # floor=150 ensures >= 21 restaurants in pool (7 days x 2 meals = 14 slots needed)
            dyn_rest_cap = max(150.0, budget_for_act / (max(req.days, 1) * 5.0))
            if max_rest_cost is not None:
                effective_rest_cap = min(max_rest_cost, dyn_rest_cap)
            else:
                # Premium: ใช้ dynamic cap เฉพาะเมื่องบต่ำ; งบสูง (dyn≥500) ไม่จำกัด
                effective_rest_cap = dyn_rest_cap if dyn_rest_cap < 500 else None
        else:
            # Budget (ratio mode): ใช้ tier cap เดิม
            effective_rest_cap = max_rest_cost

        # กรอง POI pool ตาม tier (ทำให้แต่ละ tier ต่างกัน)
        tier_pois = make_tier_pois(score_pct, effective_rest_cap)

        t0 = time.time()
        if algo == 'greedy':
            routes = greedy_solve(tier_pois, hotel, req.days, budget_for_act,
                                  scoring_mode=mode, random_factor=0.15)
        elif algo == 'ga':
            routes, _hist = genetic_solve(tier_pois, hotel, req.days, budget_for_act,
                                          pop_size=30, generations=40,
                                          mutation_rate=0.3, verbose=False)
        else:  # hybrid
            routes, _hist = hybrid_solve(tier_pois, hotel, req.days, budget_for_act,
                                         scoring_mode=mode, pop_size=20,
                                         generations=40, mutation_rate=0.3,
                                         verbose=False)
        runtime_ms = (time.time() - t0) * 1000.0
        # ใช้ target_total เป็น cap แทน req.budget เพื่อให้แต่ละ tier ถูกตัดต่างกัน
        packages.append(build_package(tier, hotel, routes, req.days,
                                       req.budget, runtime_ms, req.travelers,
                                       max_total_budget=target_total,
                                       hotel_cost_override=hotel_total))
    return PackageResponse(request=req.dict(), packages=packages)


@app.post('/api/recompute', response_model=Package)
def recompute(req: RecomputeRequest):
    if req.hotel_id not in HOTEL_BY_ID:
        raise HTTPException(status_code=404, detail=f'Hotel {req.hotel_id} not found')
    hotel = HOTEL_BY_ID[req.hotel_id]
    routes_per_day = []
    for day in req.routes:
        day_pois = []
        for pid in day:
            if pid not in POI_BY_ID:
                raise HTTPException(status_code=404, detail=f'POI {pid} not found')
            day_pois.append(POI_BY_ID[pid])
        routes_per_day.append(day_pois)
    return build_package('Custom', hotel, routes_per_day, req.days,
                         req.budget, 0, req.travelers)


if __name__ == '__main__':
    import uvicorn
    print('Starting WeEasyTrip API...')
    print(f'Loaded {len(POIS)} POIs and {len(HOTELS)} hotels')
    uvicorn.run(app, host='0.0.0.0', port=8000)
