# WeEasyTrip — ระบบแนะนำการท่องเที่ยวภูเก็ตภายใต้งบประมาณ

ระบบแนะนำการท่องเที่ยวแบบหลายวันในจังหวัดภูเก็ต ภายใต้งบประมาณจำกัด
โดยใช้ Optimization Algorithm สำหรับการจัดเส้นทาง

## เป้าหมายของโปรเจค (Thesis Focus)

แก้ปัญหา **Budget-Constrained Team Orienteering Problem with Time Windows (B-TOPTW)**
โดยเปรียบเทียบประสิทธิภาพของ 3 อัลกอริทึม:

1. **Greedy Algorithm** (Baseline) — slot-based, เลือก POI ที่ score/cost ratio ดีที่สุดทีละ slot
2. **Genetic Algorithm (GA)** — population-based metaheuristic, global search
3. **Hybrid Algorithm** — Greedy seed + GA refinement + 2-opt local search (proposed method)

ตัวชี้วัด (Evaluation Metrics):
- Solution Quality = total score ของจุดที่เลือก
- Constraint validity (เวลา, งบ, time window, meal pattern)
- Runtime (ms)
- Convergence (GA/Hybrid เท่านั้น)

## โครงสร้างโปรเจค

```
WeEasyTrip/
├── README.md
├── docs/
│   └── problem_formulation.md       # นิยามปัญหา B-TOPTW + สมการคณิตศาสตร์
├── data/
│   ├── phuket_pois.json             # ข้อมูลหลัก: 164 POIs + 20 โรงแรม
│   ├── phuket_pois_backup.json      # สำรองข้อมูล
│   ├── fetch_pois_osm.py            # ดึงข้อมูลจาก OpenStreetMap (Overpass API)
│   └── merge_pois.py                # รวม OSM + ข้อมูลเดิม
├── algorithm/
│   ├── utils.py                     # ฟังก์ชันช่วย: ระยะทาง, เวลา, ตรวจ constraint
│   ├── greedy.py                    # Greedy slot-based algorithm (Baseline)
│   ├── genetic.py                   # Genetic Algorithm
│   └── hybrid.py                    # Hybrid: Greedy seed + GA + 2-opt
├── backend/
│   └── main.py                      # FastAPI server (Python)
├── frontend/
│   ├── index.html                   # หน้า UI หลัก
│   ├── style.css                    # Aurora background + glass-morphism + dark/light
│   └── app.js                       # Algorithm selector, day filter, map, swap modal
├── experiments/
│   ├── run_experiments.py           # รัน 30 trials × 3 algos × 3 scenarios
│   └── results/
│       ├── results.json
│       ├── stats.txt
│       └── convergence.png
└── thesis_filled.docx               # รายงานฉบับเต็ม
```

## ข้อมูล POI

ดึงจาก **OpenStreetMap** ผ่าน Overpass API — ไม่ต้องใช้ API key

| หมวด | จำนวน |
|------|-------|
| restaurant (ร้านอาหาร) | 49 |
| beach (หาด) | 29 |
| temple (วัด) | 24 |
| activity (กิจกรรม) | 21 |
| culture (วัฒนธรรม/พิพิธภัณฑ์) | 19 |
| viewpoint (จุดชมวิว) | 12 |
| market (ตลาด) | 10 |
| **รวม** | **164 POIs + 20 โรงแรม** |

## Day Pattern (รูปแบบวัน)

ทุกวันบังคับรูปแบบ: **attr → attr → lunch → attr → attr → dinner** (6 slots/day)

| Parameter | ค่า |
|-----------|-----|
| เวลาท่องเที่ยว | 8:00–22:00 (840 นาที/วัน) |
| Lunch window | 10:00–14:00 (arrive 600–840 นาที) |
| Dinner window | 17:00–21:00 (arrive 1020–1260 นาที) |
| ความเร็วเดินทาง | 40 กม/ชม (เฉลี่ย) |
| ค่าเดินทาง | 10 บาท/กม |

## Tier Logic (3 Packages)

| Tier | Hotel budget | Total budget | Scoring | Restaurant cap |
|------|-------------|--------------|---------|----------------|
| Budget | 20% | 40% | ratio | 150 บาท |
| Standard | 45% | 75% | quality | 400 บาท (dynamic) |
| Premium | 55% | 100% | quality | ไม่จำกัด (dynamic) |

## Algorithm Parameters

| Algorithm | Production | Experiments |
|-----------|-----------|-------------|
| Greedy | random_factor=0.15 | — |
| GA | pop=30, gen=40, mut=0.3 | pop=50, gen=100, mut=0.3 |
| Hybrid | pop=20, gen=40, mut=0.3, early_stop=15 | pop=30, gen=60, mut=0.3 |

## วิธี run

```bash
# ติดตั้ง dependencies
pip install fastapi uvicorn pydantic

# Backend (terminal ที่โฟลเดอร์ backend/)
uvicorn main:app --reload --port 8000

# Frontend — เปิด frontend/index.html ใน browser ได้เลย

# รัน experiments
cd experiments
python run_experiments.py
```

## Future Work

- Real-time traffic / weather integration
- Multi-objective optimization (เวลา vs เงิน vs score)
- User accounts / save trips
- Mobile app
