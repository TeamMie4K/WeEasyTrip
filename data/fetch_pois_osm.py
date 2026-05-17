# -*- coding: utf-8 -*-
"""
fetch_pois_osm.py — ดึงข้อมูล POI จาก OpenStreetMap (Overpass API) สำหรับภูเก็ต
ฟรี ไม่ต้อง API key
รัน: python fetch_pois_osm.py
ผลลัพธ์: phuket_pois_osm.json (merge กับ phuket_pois.json ที่มีอยู่ได้)
"""
import urllib.request, json, time, math

# Phuket bounding box: south, west, north, east
BBOX = "7.7,98.2,8.2,98.5"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# หมวดหมู่ที่ต้องการดึง: (osm_filter, category, default_duration_min, default_cost)
QUERIES = [
    # วัด
    ('node["amenity"="place_of_worship"]["religion"="buddhist"]',  'temple',    60, 0),
    ('way["amenity"="place_of_worship"]["religion"="buddhist"]',   'temple',    60, 0),
    # หาด
    ('node["natural"="beach"]',   'beach',  90, 0),
    ('way["natural"="beach"]',    'beach',  90, 0),
    # จุดชมวิว
    ('node["tourism"="viewpoint"]',  'viewpoint', 40, 0),
    # วัฒนธรรม/พิพิธภัณฑ์
    ('node["tourism"="museum"]',     'culture', 60, 100),
    ('node["historic"="monument"]',  'culture', 40, 0),
    # ตลาด/ถนนคนเดิน
    ('node["amenity"="marketplace"]', 'market', 60, 0),
    # กิจกรรม
    ('node["leisure"="water_park"]',  'activity', 180, 800),
    ('node["tourism"="theme_park"]',  'activity', 180, 500),
    # คาเฟ่ / ร้านกาแฟ
    ('node["amenity"="cafe"]["name"]',  'cafe', 60, 150),
    # ร้านอาหาร (เฉพาะที่มีชื่อและ rating)
    ('node["amenity"="restaurant"]["name"]', 'restaurant', 60, 200),
]

def overpass_query(filter_str, bbox):
    query = f"data=[out:json][timeout:30];({filter_str}({bbox}););out+center+50;"
    req = urllib.request.Request(
        OVERPASS_URL,
        data=query.encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ThesisProject/1.0 (phuket-tourism-research)"
        }
    )
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read())


def make_poi(element, category, duration_min, cost, index):
    tags = element.get('tags', {})
    lat = element.get('lat') or element.get('center', {}).get('lat')
    lng = element.get('lon') or element.get('center', {}).get('lon')
    if not lat or not lng:
        return None

    name_en = (tags.get('name:en') or tags.get('name') or '').strip()
    name_th = (tags.get('name:th') or tags.get('name') or name_en).strip()
    if not name_en:
        return None

    # เวลาเปิด-ปิด (default ถ้าไม่มีข้อมูล)
    open_min  = 480   # 08:00
    close_min = 1080  # 18:00
    if category == 'restaurant':
        open_min  = 660   # 11:00
        close_min = 1320  # 22:00
    elif category == 'market':
        open_min  = 1020  # 17:00
        close_min = 1380  # 23:00
    elif category == 'beach':
        open_min  = 360   # 06:00
        close_min = 1320  # 22:00

    # score: ใช้ stars ถ้ามี ไม่งั้น default 7.5
    stars = tags.get('stars') or tags.get('rating')
    try:
        score = float(stars)
        if score > 10:  # เป็น % หรือ 100-scale
            score = score / 10
        score = round(min(max(score, 5.0), 10.0), 1)
    except (TypeError, ValueError):
        score = 7.5

    return {
        "id": f"OSM_{category[:2].upper()}_{index:04d}",
        "name_th": name_th,
        "name_en": name_en,
        "category": category,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "score": score,
        "cost": cost,
        "duration_min": duration_min,
        "open_min": open_min,
        "close_min": close_min,
    }


def main():
    all_pois = []
    seen_names = set()
    idx = 0

    for filter_str, category, duration, cost in QUERIES:
        print(f"Fetching {category} ({filter_str[:40]}...)...")
        try:
            data = overpass_query(filter_str, BBOX)
            elements = data.get('elements', [])
            count = 0
            for e in elements:
                poi = make_poi(e, category, duration, cost, idx)
                if poi is None:
                    continue
                key = poi['name_en'].lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                all_pois.append(poi)
                idx += 1
                count += 1
            print(f"  → {count} POIs added")
            time.sleep(1)  # polite delay
        except Exception as e:
            print(f"  ERROR: {e}")

    # สรุปตามหมวด
    from collections import Counter
    cats = Counter(p['category'] for p in all_pois)
    print(f"\nTotal: {len(all_pois)} POIs")
    for cat, n in sorted(cats.items()):
        print(f"  {cat}: {n}")

    # บันทึก
    out_path = "phuket_pois_osm.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({"pois": all_pois}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_path}")
    print("Next: ตรวจสอบข้อมูล แล้ว merge เข้า phuket_pois.json")


if __name__ == '__main__':
    main()
