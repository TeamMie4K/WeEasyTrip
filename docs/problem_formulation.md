# Problem Formulation — Budget-Constrained Team Orienteering Problem with Time Windows (B-TOPTW)

เอกสารนี้ใช้เป็นพื้นฐานสำหรับ Chapter 3 ของ thesis (Methodology / Problem Formulation)

---

## 1. Problem Description

ผู้ใช้ระบุงบประมาณ B และจำนวนวันทริป D สำหรับเที่ยวภูเก็ต
ระบบมีฐานข้อมูลจุดท่องเที่ยว / ร้านอาหาร / โรงแรม จำนวน 164 จุด (ดึงจาก OpenStreetMap)
แต่ละจุดมี score (ความน่าสนใจ), cost (ค่าใช้จ่าย), duration (เวลาที่ใช้), และ time window (เปิด-ปิด)

**Day Pattern บังคับ:** ทุกวันมีรูปแบบ `attr → attr → lunch → attr → attr → dinner`
(2 สถานที่เช้า + กลางวัน + 2 สถานที่บ่าย + เย็น)
เวลาท่องเที่ยว: 8:00–22:00 (840 นาที/วัน)

**เป้าหมาย:** เลือกและจัดลำดับ subset ของจุด แบ่งเป็น D วัน เพื่อให้ score รวมสูงสุด
ภายใต้ข้อจำกัด: งบประมาณรวม, เวลาในแต่ละวัน, time window ของแต่ละจุด,
รูปแบบมื้ออาหาร (lunch + dinner ทุกวัน), และเริ่ม-จบที่โรงแรมเดียวกันทุกวัน

ปัญหานี้ในวงการ Operations Research เรียกว่า **Team Orienteering Problem with Time Windows (TOPTW)**
แต่เพิ่ม constraint ด้านงบประมาณและ meal pattern จึงเรียกว่า **B-TOPTW with Meal Constraints**

---

## 2. Notation

| Symbol | Meaning |
|--------|---------|
| `V`    | เซตของจุด (POI) ทั้งหมด, `\|V\| = 164` |
| `H`    | จุดเริ่มต้น/สิ้นสุด (โรงแรม) |
| `D`    | จำนวนวันทริป (1–7) |
| `B`    | งบประมาณรวม (บาท) |
| `T_d`  | เวลาที่ใช้ได้ในวัน d = 840 นาที (8:00–22:00) |
| `s_i`  | score ของจุด i (5.0–10.0) |
| `c_i`  | ค่าใช้จ่ายของจุด i (บาท) |
| `dur_i`| เวลาที่ใช้ที่จุด i (นาที) |
| `[o_i, e_i]` | time window: เปิด `o_i`, ปิด `e_i` (นาทีนับจากเที่ยงคืน) |
| `t_ij` | เวลาเดินทางจากจุด i ไป j (ความเร็วเฉลี่ย 40 กม/ชม) |
| `c_ij` | ค่าเดินทางจาก i ไป j (10 บาท/กม) |
| `x_ijd`| binary = 1 ถ้าวันที่ d เดินทางจาก i ไป j |
| `a_id` | เวลาที่มาถึงจุด i ในวันที่ d |
| `y_id` | binary = 1 ถ้าจุด i ถูกเลือกในวันที่ d |

---

## 3. Mathematical Formulation

### Objective

```
maximize  Σ_d Σ_i  s_i · y_id
```

### Constraints

**(C1) Budget constraint**
```
Σ_d Σ_i c_i · y_id  +  Σ_d Σ_i Σ_j c_ij · x_ijd  ≤  B
```

**(C2) Time constraint per day**
```
Σ_i dur_i · y_id  +  Σ_i Σ_j t_ij · x_ijd  ≤  840 นาที        ∀ d
```

**(C3) Time windows** — ต้องมาถึงในช่วงที่จุดเปิด
```
o_i  ≤  a_id  ≤  e_i        ∀ i, d  ที่  y_id = 1
```

**(C4) Start/End at hotel**
```
Σ_j x_Hjd = 1     ∀ d
Σ_i x_iHd = 1     ∀ d
```

**(C5) Flow conservation**
```
Σ_j x_ijd = Σ_j x_jid = y_id     ∀ i ≠ H, ∀ d
```

**(C6) Each POI visited at most once**
```
Σ_d y_id  ≤  1     ∀ i ≠ H
```

**(C7) Meal pattern per day**
```
Σ_i y_id · [category_i = restaurant]  =  2     ∀ d   (lunch + dinner)
a_lunch_d  ∈  [600, 840]  นาที   (10:00–14:00)
a_dinner_d ∈  [1020, 1260] นาที  (17:00–21:00)
```

---

## 4. Complexity Analysis

ปัญหา B-TOPTW เป็น **NP-hard** เพราะ generalize มาจาก Traveling Salesman Problem และ Knapsack Problem
จำนวน solution space ≈ O(N! / (N-K)!) สำหรับ N=164, K≈25 → ใหญ่เกินกว่า exact algorithm จะแก้ได้ใน polynomial time
จึงต้องใช้ **metaheuristic** เช่น Genetic Algorithm + Local Search (2-opt)

---

## 5. Solution Representation

แต่ละ chromosome แทนเป็น list of lists ของ POI dict:

```python
chromosome = [
    [poi_attr1, poi_attr2, poi_lunch, poi_attr3, poi_attr4, poi_dinner],  # day 1
    [poi_attr5, poi_attr6, poi_lunch2, ...],                               # day 2
    ...
]
```

**Fitness function:**
```
fitness(chromosome) = total_score(chromosome) - penalty(violations)
```

penalty รวม: เกินเวลาต่อวัน (+50), ไปถึงหลังปิด (+25), ร้านอาหารมากเกินไป/ขาดหาย, diversity

---

## 6. อัลกอริทึมทั้ง 3 ตัว

### 6.1 Greedy Algorithm (Baseline)

ทำงานแบบ slot-by-slot ตาม DAY_PATTERN:
1. สำหรับแต่ละ slot (attr/lunch/dinner) เลือก POI ที่ดีที่สุดจาก candidate pool
2. **Scoring mode ratio:** `score × diversity_bonus / (cost + 1.0)` — ใช้ Budget/Standard
3. **Scoring mode quality:** `score × diversity_bonus` — ใช้ Premium
4. ตรวจ time window, budget, dinner buffer ก่อน commit

**ข้อดี:** รวดเร็วมาก (~2–6 ms), ได้ผลที่ใช้ได้ทันที  
**ข้อเสีย:** ได้ local optimum เท่านั้น

### 6.2 Genetic Algorithm (GA)

**Parameters (production):** pop_size=30, generations=40, mutation_rate=0.3  
**Parameters (experiments):** pop_size=50, generations=100, mutation_rate=0.3

| Operator | รายละเอียด |
|----------|-----------|
| Initialization | Greedy seeds ทั้งหมด — รัน greedy_solve() ด้วย POI order ที่ shuffle ต่างกัน (ไม่ใช้ random init) |
| Selection | Tournament selection, k=3 |
| Crossover | Day-level swap (แต่ละวันสุ่มเอาจาก parent 1 หรือ 2) |
| Mutation | swap_attr / swap_rest / cross_day / remove |
| Repair | ลบ POI ratio ต่ำสุดออกถ้าละเมิด constraint |
| Elitism | เก็บ best chromosome ทุก generation |
| Post-process | meal_fill() + _time_repair() หลัง GA จบ |

### 6.3 Hybrid Algorithm (แนะนำ)

ผสมข้อดีของ Greedy + GA + Local Search:

**Step 1:** สร้าง initial population จาก greedy seeds หลาย random seeds  
**Step 2:** GA refinement พร้อม adaptive mutation rate และ early stopping (15 gen ไม่ดีขึ้น)  
**Step 3:** 2-opt local search ต่อวัน — สลับ position ของ attr เพื่อลด travel distance  
**Step 4:** meal_fill() — รับประกัน lunch + dinner ทุกวัน  
**Step 5:** _time_repair() — ลบ attr ที่ทำให้เกินเวลา  

**Parameters (production):** pop_size=20, generations=40, mutation_rate=0.3  
**Parameters (experiments):** pop_size=30, generations=60, mutation_rate=0.3

---

## 7. ผู้ใช้-System Interaction

1. ระบบสร้าง 3 packages (Budget/Standard/Premium) โดยต่างกันที่: โรงแรม, สัดส่วนงบ, scoring mode
2. ผู้ใช้เลือก package ที่สนใจ
3. ผู้ใช้กด swap จุดบางจุด → ระบบ recompute cost/time/score ใหม่ (evaluate_route)

---

## 8. References

1. Vansteenwegen, P., et al. (2009). *The Orienteering Problem: A survey*. European Journal of Operational Research.
2. Gunawan, A., et al. (2016). *Orienteering Problem: A survey of recent variants, solution approaches and applications*. EJOR.
3. Souffriau, W., et al. (2008). *A greedy randomised adaptive search procedure for the team orienteering problem*. Journal of Heuristics.
4. Gavalas, D., et al. (2014). *A survey on algorithmic approaches for solving tourist trip design problems*. Journal of Heuristics.
5. Holland, J. H. (1992). *Adaptation in natural and artificial systems*. MIT Press.
6. OpenStreetMap contributors (2024). *Overpass API — OpenStreetMap data*. https://overpass-api.de
