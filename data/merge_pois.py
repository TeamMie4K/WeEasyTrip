# -*- coding: utf-8 -*-
"""
merge_pois.py — รวม OSM data ใหม่ + ข้อมูลเดิม (restaurants + hotels)
รัน: python merge_pois.py
ผลลัพธ์: phuket_pois_merged.json
"""
import json
from collections import Counter

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# โหลดข้อมูลทั้งสอง
old = load('phuket_pois.json')
osm = load('phuket_pois_osm.json')

old_pois   = old['pois']
old_hotels = old.get('hotels', [])
osm_pois   = osm['pois']

# เก็บร้านอาหารจากข้อมูลเดิม (OSM ดึงไม่ได้เพราะ rate limit)
old_restaurants = [p for p in old_pois if p['category'] == 'restaurant']
old_activities  = [p for p in old_pois if p['category'] == 'activity']
old_cafes       = [p for p in old_pois if p['category'] == 'cafe']

# OSM pois (non-restaurant)
osm_non_rest = [p for p in osm_pois if p['category'] != 'restaurant']

# Re-index ทุก POI ด้วย ID ที่สม่ำเสมอ
merged_pois = []
seen_names = set()

def add_pois(pois_list, id_prefix):
    for p in pois_list:
        key = p['name_en'].lower().strip()
        if key in seen_names or not key:
            continue
        seen_names.add(key)
        merged_pois.append(p)

# Priority: OSM non-restaurant ก่อน (ข้อมูลใหม่กว่า ครบกว่า)
add_pois(osm_non_rest, 'OSM')

# เติม activity จากเดิมที่ OSM ไม่ค่อยมี
add_pois(old_activities, 'ACT')

# เติม cafe จากเดิม
add_pois(old_cafes, 'CAFE')

# เติมร้านอาหารจากเดิม (OSM timeout)
add_pois(old_restaurants, 'REST')

# Re-assign IDs ให้เรียงลำดับ
for i, p in enumerate(merged_pois):
    cat_prefix = {'temple':'T','beach':'B','viewpoint':'V',
                  'culture':'C','market':'M','activity':'A','restaurant':'R'}
    prefix = cat_prefix.get(p['category'], 'P')
    p['id'] = f"P{i+1:02d}"

# สรุป
cats = Counter(p['category'] for p in merged_pois)
print(f"Merged POIs: {len(merged_pois)} total")
for cat, n in sorted(cats.items()):
    print(f"  {cat}: {n}")
print(f"Hotels: {len(old_hotels)}")

# บันทึก
result = {"pois": merged_pois, "hotels": old_hotels}
save('phuket_pois_merged.json', result)
print(f"\nSaved to phuket_pois_merged.json")
print("ตรวจสอบแล้วถ้าโอเค: copy phuket_pois_merged.json → phuket_pois.json")
