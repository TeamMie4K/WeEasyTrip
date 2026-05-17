// app.js - Phuket Smart Trip Planner Frontend
// Modern UI version

const API_BASE = 'http://localhost:8000';

const STATE = {
  pois: [],
  hotels: [],
  poisById: {},
  packages: [],
  selectedPkg: null,
  selectedIdx: null,
  swapContext: null,
  map: null,
  mapMarkers: [],
  mapPolylines: [],
  // Track markers/polylines per day for filtering
  mapDayLayers: {},   // {dayIdx: {markers: [], polyline: line, visible: true}}
  hotelMarker: null,
};

const DAY_COLORS = ['#06b6d4', '#a78bfa', '#f97316', '#10b981', '#f43f5e', '#fbbf24', '#3b82f6'];

const CAT_LABELS = {
  all: 'ทั้งหมด',
  beach: 'หาด', temple: 'วัด', viewpoint: 'จุดชมวิว',
  culture: 'วัฒนธรรม', market: 'ตลาด',
  activity: 'กิจกรรม', restaurant: 'ร้านอาหาร'
};

const CAT_EMOJI = {
  beach: '🏖️', temple: '🛕', viewpoint: '🌄',
  culture: '🏛️', market: '🛍️',
  activity: '🎢', restaurant: '🍽️', hotel: '🏨'
};

// Inline SVG icons (Lucide-style)
const ICON = {
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  coin:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8h-4a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H8"/><path d="M12 6v2m0 8v2"/></svg>',
  route: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M9 19h6a4 4 0 0 0 0-8h-6a4 4 0 0 1 0-8h6"/></svg>',
  star:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
  swap:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>',
  plus:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  spin:  '<svg class="spinner" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="50" stroke-dashoffset="30" stroke-linecap="round"/></svg>',
};

// ============================================================
// Init
// ============================================================
window.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initDateRange();
  initMap();
  initBudgetValidation();
  initAlgoControl();
  await loadPois();
});

const ALGO_HINTS = {
  greedy: '⚡ Greedy: เร็วที่สุด (~5 ms) — เลือกจุดดีที่สุดทีละขั้น แต่อาจไม่ optimal ในภาพรวม',
  ga:     '🧬 Genetic Algorithm: optimization ทั้งทริปพร้อมกัน (~2 sec) — global optimal กว่า greedy',
  hybrid: '⭐ Hybrid (แนะนำ): Greedy seed → GA refine → 2-opt local search (~100 ms) — รวมข้อดีของทั้งสอง',
};
let SELECTED_ALGO = 'hybrid';

function initAlgoControl() {
  document.querySelectorAll('#algoControl button').forEach(b => {
    b.onclick = () => {
      document.querySelectorAll('#algoControl button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      SELECTED_ALGO = b.dataset.val;
      document.getElementById('algoHint').textContent = ALGO_HINTS[SELECTED_ALGO];
    };
  });
}

function initBudgetValidation() {
  const budgetInput = document.getElementById('budget');
  if (!budgetInput) return;
  const hint = budgetInput.closest('.form-group').querySelector('.input-hint');
  budgetInput.addEventListener('input', () => {
    const v = +budgetInput.value;
    if (v < VALIDATION.budget.min) {
      hint.textContent = `ต้องอย่างน้อย ${fmt(VALIDATION.budget.min)} บาท (ตอนนี้ ${fmt(v || 0)})`;
      hint.style.color = 'var(--accent-danger)';
      highlightField('budget', true);
    } else if (v > VALIDATION.budget.max) {
      hint.textContent = `สูงสุด ${fmt(VALIDATION.budget.max)} บาท`;
      hint.style.color = 'var(--accent-danger)';
      highlightField('budget', true);
    } else {
      hint.textContent = `${fmt(VALIDATION.budget.min)} - ${fmt(VALIDATION.budget.max)} บาท`;
      hint.style.color = '';
      highlightField('budget', false);
    }
  });
}

function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.dataset.theme = saved;
}

function toggleTheme() {
  const cur = document.documentElement.dataset.theme || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  // re-tile map (since dark mode applies CSS filter)
  if (STATE.map) STATE.map.invalidateSize();
}

// === Date range picker (Flatpickr) ===
let DATE_PICKER = null;
let SELECTED_DAYS = 3;

function initDateRange() {
  const today = new Date();
  const tomorrow = new Date(today.getTime() + 24*60*60*1000);
  const day4    = new Date(today.getTime() + 4*24*60*60*1000);

  DATE_PICKER = flatpickr('#dateRange', {
    mode: 'range',
    minDate: 'today',
    maxDate: new Date().fp_incr(180),
    locale: (window.flatpickr && flatpickr.l10ns && flatpickr.l10ns.th) ? 'th' : 'default',
    defaultDate: [tomorrow, day4],
    dateFormat: 'Y-m-d',
    altInput: true,
    altFormat: 'j M Y',
    onChange: (selectedDates) => {
      // ถ้าเลือกแค่วันเดียว (กำลังรอวันสิ้นสุด) ให้ onDayCreate เพิ่มคำใบ้
      updateDateSummary(selectedDates);
    },
    onDayCreate: (dObj, dStr, fp, dayElem) => {
      // ถ้าเลือก start date แล้ว และ hover/click วันเดิม → แสดง tooltip "1 วัน"
      if (fp.selectedDates.length === 1) {
        const startTs = fp.selectedDates[0].getTime();
        const cellTs  = dayElem.dateObj?.getTime();
        if (cellTs === startTs) {
          dayElem.title = 'คลิกเพื่อ One Day Trip';
        }
      }
    },
    onClose: (selectedDates) => {
      // ถ้าปิดโดยมีแค่ 1 วัน → ถือว่าเป็น One Day Trip
      if (selectedDates.length === 1) {
        const d = selectedDates[0];
        DATE_PICKER.setDate([d, d], false);
        updateDateSummary([d, d]);
      }
    },
  });
  updateDateSummary([tomorrow, day4]);
}

function getSelectedDays() {
  return SELECTED_DAYS;
}

function updateDateSummary(dates) {
  const sumEl = document.getElementById('dateSummary');
  const fmtDate = d => d.toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'numeric'});

  // กำลังเลือกวันแรก (ยังไม่ได้เลือกวันสิ้นสุด)
  if (!dates || dates.length < 1) {
    sumEl.textContent = 'กรุณาเลือกช่วงวันเดินทาง';
    sumEl.className = 'date-summary invalid';
    SELECTED_DAYS = 3;
    setOneDayTripMode(false);
    return;
  }

  // เลือกวันเดียว (คลิก 1 ครั้ง หรือเลือกวันเดิม 2 ครั้ง)
  if (dates.length === 1) {
    sumEl.innerHTML = `🌅 <b>One Day Trip</b> · ${fmtDate(dates[0])} — เลือกวันสิ้นสุดหรือคลิกวันเดิมอีกครั้ง`;
    sumEl.className = 'date-summary oneday';
    SELECTED_DAYS = 1;
    setOneDayTripMode(true);
    return;
  }

  const [ci, co] = dates;
  const nights = Math.round((co - ci) / (24*60*60*1000));
  const days = nights + 1;

  if (nights === 0) {
    // เลือกวันเดิมเป็น start และ end → One Day Trip
    sumEl.innerHTML = `🌅 <b>One Day Trip</b> · ${fmtDate(ci)}`;
    sumEl.className = 'date-summary oneday';
    SELECTED_DAYS = 1;
    setOneDayTripMode(true);
  } else if (days > 7) {
    sumEl.innerHTML = `เลือกได้ไม่เกิน 7 วัน (ขณะนี้ <b>${days} วัน ${nights} คืน</b>) — ระบบจะใช้แค่ 7 วัน`;
    sumEl.className = 'date-summary invalid';
    SELECTED_DAYS = 7;
    setOneDayTripMode(false);
  } else {
    sumEl.innerHTML = `<b>${fmtDate(ci)}</b> → <b>${fmtDate(co)}</b> · ${days} วัน ${nights} คืน`;
    sumEl.className = 'date-summary';
    SELECTED_DAYS = days;
    setOneDayTripMode(false);
  }
}

function setOneDayTripMode(isOneDay) {
  const checkbox = document.getElementById('includeHotel');
  const label    = document.getElementById('hotelToggleLabel');
  const hint     = document.getElementById('hotelToggleHint');
  const card     = document.getElementById('hotelOptionCard');
  const icon     = document.getElementById('hotelCardIcon');
  if (!checkbox) return;

  if (isOneDay) {
    checkbox.checked  = false;
    checkbox.disabled = true;
    card?.classList.add('hotel-card-locked');
    if (icon) icon.textContent = '🔒';
    // Badge inline กับ title row
    const titleRow = card?.querySelector('.hotel-card-title-row');
    if (titleRow && !titleRow.querySelector('.hotel-lock-badge')) {
      const badge = document.createElement('span');
      badge.className = 'hotel-lock-badge';
      badge.textContent = '🌅 One Day Trip';
      titleRow.appendChild(badge);
    }
    label.textContent = 'ไม่รวมค่าโรงแรม';
    hint.textContent  = 'ทริปวันเดียวไม่มีค่าที่พัก — ใช้งบทั้งหมดสำหรับกิจกรรม';
  } else {
    checkbox.disabled = false;
    card?.classList.remove('hotel-card-locked');
    if (icon) icon.textContent = checkbox.checked ? '🏨' : '🏕️';
    card?.querySelector('.hotel-lock-badge')?.remove();
    onHotelToggle();
  }
}

function changeTravelers(delta) {
  const inp = document.getElementById('travelers');
  const v = Math.min(10, Math.max(1, +inp.value + delta));
  inp.value = v;
}

function toggleHotelOption() {
  // คลิกที่ card ทั้งใบ → toggle checkbox (ยกเว้นเมื่อล็อค)
  const checkbox = document.getElementById('includeHotel');
  if (!checkbox || checkbox.disabled) return;
  checkbox.checked = !checkbox.checked;
  onHotelToggle();
}

function onHotelToggle() {
  const checkbox = document.getElementById('includeHotel');
  if (checkbox?.disabled) return;  // ล็อคโดย One Day Trip
  const checked = checkbox?.checked;
  const label = document.getElementById('hotelToggleLabel');
  const hint  = document.getElementById('hotelToggleHint');
  const icon  = document.getElementById('hotelCardIcon');
  if (checked) {
    label.textContent = 'รวมค่าโรงแรมในงบประมาณ';
    hint.textContent  = 'ระบบจะหักค่าโรงแรมออกจากงบก่อนวางแผนกิจกรรม';
    if (icon) icon.textContent = '🏨';
  } else {
    label.textContent = 'ไม่รวมค่าโรงแรม';
    hint.textContent  = 'เหมาะสำหรับทริปวันเดียว หรือมีที่พักของตัวเองแล้ว';
    if (icon) icon.textContent = '🏕️';
  }
}

function initMap() {
  STATE.map = L.map('map', {zoomControl: true, attributionControl: false}).setView([7.88, 98.36], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(STATE.map);
  L.control.attribution({prefix: false}).addAttribution('© OSM').addTo(STATE.map);
}

// ============================================================
// API status indicator
// ============================================================
function setApiStatus(state, text) {
  const el = document.getElementById('apiStatus');
  el.className = 'api-status ' + state;
  el.querySelector('.status-text').textContent = text;
}

async function loadPois() {
  try {
    setApiStatus('loading', 'connecting...');
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(`${API_BASE}/api/pois`, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    STATE.pois = data.pois;
    STATE.hotels = data.hotels;
    [...data.pois, ...data.hotels].forEach(p => STATE.poisById[p.id] = p);
    setApiStatus('ok', `${data.pois.length} POIs · ${data.hotels.length} hotels`);
  } catch (e) {
    setApiStatus('error', 'backend offline');
    showToast(`โหลดข้อมูลไม่สำเร็จ — ตรวจสอบว่า backend รันที่ ${API_BASE}`, 'error', 6000);
  }
}

// ============================================================
// Toast notifications
// ============================================================
function showToast(msg, kind = 'ok', duration = 3500) {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  const iconMap = {ok: ICON.check, error: ICON.alert, loading: ICON.spin};
  el.innerHTML = `<span class="toast-icon">${iconMap[kind] || ICON.check}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    el.style.transition = 'all 200ms';
    setTimeout(() => el.remove(), 220);
  }, duration);
  return el;
}

// ============================================================
// Search packages
// ============================================================
// Client-side validation rules (must match backend Pydantic schema)
const VALIDATION = {
  budget: { min: 1000,  max: 100000, label: 'งบประมาณ' },
  days:   { min: 1,     max: 7,      label: 'จำนวนวัน' },
  travelers: { min: 1,  max: 10,     label: 'จำนวนคน' },
};

function validateInputs(budget, days, travelers) {
  const errors = [];
  if (!Number.isFinite(budget) || budget < VALIDATION.budget.min) {
    errors.push(`${VALIDATION.budget.label}ต้องอย่างน้อย ${fmt(VALIDATION.budget.min)} บาท (ใส่ไว้ ${fmt(budget || 0)} บาท)`);
  }
  if (budget > VALIDATION.budget.max) {
    errors.push(`${VALIDATION.budget.label}สูงสุด ${fmt(VALIDATION.budget.max)} บาท`);
  }
  if (days < VALIDATION.days.min || days > VALIDATION.days.max) {
    errors.push(`${VALIDATION.days.label}ต้องอยู่ระหว่าง ${VALIDATION.days.min}-${VALIDATION.days.max} วัน (ตอนนี้ ${days})`);
  }
  if (travelers < VALIDATION.travelers.min || travelers > VALIDATION.travelers.max) {
    errors.push(`${VALIDATION.travelers.label}ต้อง ${VALIDATION.travelers.min}-${VALIDATION.travelers.max} คน`);
  }
  return errors;
}

function highlightField(id, hasError) {
  const wrapper = document.getElementById(id)?.closest('.input-with-unit, .date-range-input, .counter-control, .select-input');
  if (wrapper) wrapper.classList.toggle('has-error', hasError);
  const input = document.getElementById(id);
  if (input) input.classList.toggle('has-error', hasError);
}

async function searchPackages() {
  const budget = +document.getElementById('budget').value;
  const days = getSelectedDays();
  const travelers = +document.getElementById('travelers').value;
  // One Day Trip → บังคับไม่รวมโรงแรม
  const includeHotel = days === 1 ? false : (document.getElementById('includeHotel')?.checked !== false);

  // === Client-side validation FIRST ===
  const errors = validateInputs(budget, days, travelers);
  highlightField('budget', errors.some(e => e.includes('งบประมาณ')));
  highlightField('dateRange', errors.some(e => e.includes('จำนวนวัน')));
  if (errors.length > 0) {
    showToast(errors[0], 'error', 5000);
    return;
  }

  // === Clear previous results ===
  if (STATE.map) {
    STATE.mapMarkers.forEach(m => STATE.map.removeLayer(m));
    STATE.mapPolylines.forEach(p => STATE.map.removeLayer(p));
    if (STATE.hotelMarker) STATE.map.removeLayer(STATE.hotelMarker);
    STATE.mapMarkers = [];
    STATE.mapPolylines = [];
    STATE.mapDayLayers = {};
    STATE.hotelMarker = null;
  }
  STATE.packages = [];
  STATE.selectedPkg = null;
  STATE.selectedIdx = null;
  document.getElementById('detailPanel').style.display = 'none';
  document.getElementById('dayToggles').innerHTML = '';
  document.getElementById('dayPanels').innerHTML = '';

  const btn = document.getElementById('searchBtn');
  btn.classList.add('loading');
  btn.disabled = true;

  const sec = document.getElementById('packagesSection');
  sec.style.display = 'block';
  document.getElementById('metaSummary').textContent = `กำลังคำนวณด้วย Genetic Algorithm...`;
  const grid = document.getElementById('packagesRow');
  grid.innerHTML = '';
  const skTpl = document.getElementById('skeletonTemplate');
  for (let i = 0; i < 3; i++) grid.appendChild(skTpl.content.cloneNode(true));
  sec.scrollIntoView({behavior: 'smooth', block: 'start'});

  const loadingToast = showToast('กำลังเรียก Genetic Algorithm 3 รอบ...', 'loading', 30000);

  try {
    const res = await fetch(`${API_BASE}/api/packages`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({budget, days, travelers, seed: Math.floor(Math.random() * 100000), algorithm: SELECTED_ALGO, include_hotel: includeHotel}),
    });
    if (!res.ok) {
      // Parse FastAPI/Pydantic 422 detail
      let detail = `HTTP ${res.status}`;
      try {
        const errData = await res.json();
        if (errData.detail && Array.isArray(errData.detail)) {
          detail = errData.detail.map(d => {
            const field = d.loc ? d.loc[d.loc.length - 1] : '?';
            return `${field}: ${d.msg}`;
          }).join(' · ');
        } else if (errData.detail) {
          detail = errData.detail;
        }
      } catch {}
      throw new Error(detail);
    }
    const data = await res.json();
    STATE.packages = data.packages;
    STATE.includeHotel = includeHotel;
    renderPackages();
    const totalRuntime = data.packages.reduce((s, p) => s + p.runtime_ms, 0);
    document.getElementById('metaSummary').textContent =
      `งบ ${fmt(budget)} ฿ · ${days} วัน · ${travelers} คน · ${(totalRuntime/1000).toFixed(1)} วินาที`;
    loadingToast.remove();
    showToast(`สร้าง ${data.packages.length} แพ็กเกจสำเร็จ`, 'ok');
  } catch (e) {
    loadingToast.remove();
    showToast(`ผิดพลาด: ${e.message}`, 'error', 6000);
    grid.innerHTML = '';
    document.getElementById('metaSummary').textContent = '';
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ============================================================
// Render package cards
// ============================================================
function renderPackages() {
  const grid = document.getElementById('packagesRow');
  grid.innerHTML = '';

  const showHotel = STATE.includeHotel !== false;

  STATE.packages.forEach((pkg, idx) => {
    const card = document.createElement('div');
    card.className = `package-card ${pkg.valid ? '' : 'invalid'}`;
    card.onclick = () => pkg.valid && selectPackage(idx);
    const totalPois = pkg.days.reduce((s, d) => s + d.pois.length, 0);
    card.innerHTML = `
      <div class="tier-row">
        <span class="tier-badge tier-${pkg.tier}">${pkg.tier}</span>
        <span class="runtime">${pkg.runtime_ms.toFixed(0)} ms</span>
      </div>
      ${showHotel
        ? `<div class="hotel-name">${CAT_EMOJI.hotel} ${pkg.hotel.name_en}</div>`
        : `<div class="hotel-name no-hotel">🏕️ ไม่รวมที่พัก</div>`}
      ${pkg.valid ? `
        <div class="score-display">
          <span class="score-num">${pkg.total_score}</span>
          <span class="score-label">รวมคะแนน · ${totalPois} จุด</span>
        </div>
        ${showHotel ? `<div class="stat-row"><span class="label">ค่าโรงแรม</span><span class="val">${fmt(pkg.total_hotel_cost)} ฿</span></div>` : ''}
        <div class="stat-row"><span class="label">ค่ากิจกรรม</span><span class="val">${fmt(pkg.total_activity_cost)} ฿</span></div>
        <div class="stat-row total"><span class="label">รวมทั้งหมด</span><span class="val">${fmt(pkg.total_cost)} ฿</span></div>
      ` : `
        <div class="invalid-msg">${pkg.violations[0] || 'งบไม่พอสำหรับแพ็กเกจนี้'}</div>
      `}
    `;
    grid.appendChild(card);
  });
}

// ============================================================
// Select a package
// ============================================================
function selectPackage(idx) {
  STATE.selectedPkg = JSON.parse(JSON.stringify(STATE.packages[idx]));
  STATE.selectedIdx = idx;
  document.querySelectorAll('.package-card').forEach((c, i) =>
    c.classList.toggle('selected', i === idx)
  );
  document.getElementById('detailPanel').style.display = 'block';
  renderDetail(STATE.selectedPkg);
  // CRITICAL: must invalidate size after detail panel becomes visible,
  // otherwise map container has 0px and fitBounds fails
  setTimeout(() => {
    STATE.map.invalidateSize();
    drawOnMap(STATE.selectedPkg);
    document.getElementById('detailPanel').scrollIntoView({behavior: 'smooth', block: 'start'});
  }, 120);
}

// ============================================================
// Map drawing
// ============================================================
function drawOnMap(pkg) {
  // Clear all old layers
  STATE.mapMarkers.forEach(m => STATE.map.removeLayer(m));
  STATE.mapPolylines.forEach(p => STATE.map.removeLayer(p));
  if (STATE.hotelMarker) STATE.map.removeLayer(STATE.hotelMarker);
  STATE.mapMarkers = [];
  STATE.mapPolylines = [];
  STATE.mapDayLayers = {};

  const showHotel = STATE.includeHotel !== false;

  // Hotel marker — แสดงเฉพาะเมื่อรวมโรงแรม
  if (showHotel) {
    const hotelIcon = L.divIcon({
      html: `<div class="map-hotel-marker">🏨</div>`,
      className: '',
      iconSize: [40, 40], iconAnchor: [20, 20],
    });
    STATE.hotelMarker = L.marker([pkg.hotel.lat, pkg.hotel.lng], {icon: hotelIcon})
      .bindPopup(`<b>🏨 ${pkg.hotel.name_en}</b><br><small>${pkg.hotel.cost} ฿/คืน</small>`)
      .addTo(STATE.map);
  } else {
    STATE.hotelMarker = null;
  }

  // allLatLngs: รวม hotel ไว้ใน bounds เฉพาะเมื่อรวมโรงแรม
  const allLatLngs = showHotel ? [[pkg.hotel.lat, pkg.hotel.lng]] : [];

  pkg.days.forEach((day, dIdx) => {
    const color = DAY_COLORS[dIdx % DAY_COLORS.length];
    // path: เริ่ม/จบที่โรงแรมเฉพาะเมื่อรวมโรงแรม
    const path = showHotel ? [[pkg.hotel.lat, pkg.hotel.lng]] : [];
    const dayMarkers = [];

    day.pois.forEach((poi, pIdx) => {
      const icon = L.divIcon({
        html: `<div class="map-poi-marker" style="--c:${color};">
                 <span class="d">${dIdx + 1}</span>
                 <span class="p">${pIdx + 1}</span>
               </div>`,
        className: '',
        iconSize: [36, 36], iconAnchor: [18, 18],
      });
      const m = L.marker([poi.lat, poi.lng], {icon}).bindPopup(
        `<b>${poi.name_th}</b><br>
         <small>${poi.name_en}</small><br>
         <span style="opacity:0.7;">วันที่ ${dIdx + 1} · ลำดับ ${pIdx + 1}</span><br>
         ★ ${poi.score} · ${poi.cost} ฿ · ${poi.duration_min} นาที`
      ).addTo(STATE.map);
      dayMarkers.push(m);
      STATE.mapMarkers.push(m);
      path.push([poi.lat, poi.lng]);
      allLatLngs.push([poi.lat, poi.lng]);
    });

    if (showHotel) path.push([pkg.hotel.lat, pkg.hotel.lng]);
    const line = L.polyline(path, {
      color, weight: 3, opacity: 0.8, dashArray: '6, 8',
    }).bindTooltip(`Day ${dIdx + 1}`).addTo(STATE.map);
    STATE.mapPolylines.push(line);

    // Save layers for this day
    STATE.mapDayLayers[dIdx] = {
      markers: dayMarkers,
      polyline: line,
      visible: true,
      color,
    };
  });

  renderDayToggles(pkg);

  if (allLatLngs.length > 1) {
    STATE.map.fitBounds(L.latLngBounds(allLatLngs).pad(0.15));
  }
}

// === Day toggles UI ===
function renderDayToggles(pkg) {
  const root = document.getElementById('dayToggles');
  if (!root) return;

  let html = `<button class="day-toggle show-all" onclick="toggleAllDays(true)" title="แสดงทุกวัน">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <span>แสดงทุกวัน</span>
              </button>`;
  html += `<button class="day-toggle hide-all" onclick="toggleAllDays(false)" title="ซ่อนทุกวัน">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
             <span>ซ่อนทุกวัน</span>
           </button>`;
  html += pkg.days.map((day, dIdx) => {
    const color = DAY_COLORS[dIdx % DAY_COLORS.length];
    const visible = STATE.mapDayLayers[dIdx] ? STATE.mapDayLayers[dIdx].visible : true;
    return `<button class="day-toggle ${visible ? 'active' : ''}"
                    style="--c:${color};"
                    onclick="toggleDay(${dIdx})">
              <span class="day-dot"></span>
              <span>วัน ${dIdx + 1} (${day.pois.length})</span>
            </button>`;
  }).join('');
  root.innerHTML = html;
}

function toggleDay(dIdx) {
  const layer = STATE.mapDayLayers[dIdx];
  if (!layer) return;
  layer.visible = !layer.visible;
  if (layer.visible) {
    layer.markers.forEach(m => m.addTo(STATE.map));
    layer.polyline.addTo(STATE.map);
  } else {
    layer.markers.forEach(m => STATE.map.removeLayer(m));
    STATE.map.removeLayer(layer.polyline);
  }
  renderDayToggles(STATE.selectedPkg);
}

function toggleAllDays(showAll) {
  Object.keys(STATE.mapDayLayers).forEach(k => {
    const layer = STATE.mapDayLayers[k];
    if (showAll && !layer.visible) {
      layer.markers.forEach(m => m.addTo(STATE.map));
      layer.polyline.addTo(STATE.map);
      layer.visible = true;
    } else if (!showAll && layer.visible) {
      layer.markers.forEach(m => STATE.map.removeLayer(m));
      STATE.map.removeLayer(layer.polyline);
      layer.visible = false;
    }
  });
  renderDayToggles(STATE.selectedPkg);
}

// ============================================================
// Render detail panel
// ============================================================
function renderDetail(pkg) {
  const showHotel = STATE.includeHotel !== false;
  document.getElementById('detailTitle').textContent = showHotel
    ? `${pkg.tier} — ${pkg.hotel.name_en}`
    : `${pkg.tier} — ไม่รวมที่พัก`;

  // KPIs
  const totalPois = pkg.days.reduce((s, d) => s + d.pois.length, 0);
  document.querySelector('#kpiScore .kpi-val').textContent = pkg.total_score;
  document.querySelector('#kpiCost .kpi-val').textContent = `${fmt(pkg.total_activity_cost)} ฿`;
  document.querySelector('#kpiPois .kpi-val').textContent = totalPois;

  const root = document.getElementById('dayPanels');
  root.innerHTML = '';

  pkg.days.forEach((day, dIdx) => {
    const color = DAY_COLORS[dIdx % DAY_COLORS.length];
    const panel = document.createElement('div');
    panel.className = 'day-panel';
    panel.innerHTML = `
      <div class="day-head">
        <div class="day-title">
          <div class="day-color" style="background:${color};box-shadow:0 0 8px ${color};"></div>
          <h3>วันที่ ${dIdx + 1}</h3>
        </div>
        <div class="day-stats">
          <span>${ICON.star} ${day.score}</span>
          <span>${ICON.coin} ${fmt(day.cost)}</span>
          <span>${ICON.clock} ${day.time_min.toFixed(0)}m</span>
          <span>${ICON.route} ${day.distance_km.toFixed(1)}km</span>
        </div>
      </div>
      <ul class="poi-list" id="day-${dIdx}-list"></ul>
      <button class="day-add" onclick="addPoiToDay(${dIdx})">
        <div class="add-num">${ICON.plus}</div>
        <span>เพิ่มสถานที่</span>
      </button>
    `;
    root.appendChild(panel);

    const list = panel.querySelector('.poi-list');
    if (!day.pois.length) {
      list.innerHTML = '<li style="text-align:center;color:var(--text-muted);padding:1rem 0;font-size:0.85rem;">ยังไม่มีจุดในวันนี้</li>';
    }
    // Build path: hotel → pois → hotel (for distance connectors)
    const routePath = showHotel
      ? [{ lat: pkg.hotel.lat, lng: pkg.hotel.lng }, ...day.pois, { lat: pkg.hotel.lat, lng: pkg.hotel.lng }]
      : [...day.pois];

    day.pois.forEach((poi, pIdx) => {
      // Distance connector before this POI
      if (pIdx === 0 && showHotel) {
        const distKm = haversineKm(pkg.hotel.lat, pkg.hotel.lng, poi.lat, poi.lng);
        const distEl = document.createElement('li');
        distEl.className = 'dist-connector';
        distEl.innerHTML = `<span class="dist-line"></span><span class="dist-badge">🏨 → ${distKm.toFixed(1)} km</span><span class="dist-line"></span>`;
        list.appendChild(distEl);
      } else if (pIdx > 0) {
        const prev = day.pois[pIdx - 1];
        const distKm = haversineKm(prev.lat, prev.lng, poi.lat, poi.lng);
        const distEl = document.createElement('li');
        distEl.className = 'dist-connector';
        distEl.innerHTML = `<span class="dist-line"></span><span class="dist-badge">↓ ${distKm.toFixed(1)} km</span><span class="dist-line"></span>`;
        list.appendChild(distEl);
      }

      const li = document.createElement('li');
      li.className = 'poi-item';
      li.innerHTML = `
        <div class="poi-num">${pIdx + 1}</div>
        <div class="poi-info">
          <div class="poi-name">${CAT_EMOJI[poi.category] || ''} ${poi.name_th}</div>
          <div class="poi-meta">
            <span class="pill">${CAT_LABELS[poi.category] || poi.category}</span>
            <span>★ ${poi.score}</span>
            <span>${poi.cost} ฿</span>
            <span>${poi.duration_min}m</span>
          </div>
        </div>
        <div class="poi-actions">
          <button class="btn-swap" onclick="openSwapModal(${dIdx}, ${pIdx})" title="เปลี่ยน">${ICON.swap}</button>
          <button class="btn-remove" onclick="removePoi(${dIdx}, ${pIdx})" title="ลบ">${ICON.trash}</button>
        </div>
      `;
      list.appendChild(li);

      // Return connector after last POI
      if (pIdx === day.pois.length - 1 && showHotel) {
        const distKm = haversineKm(poi.lat, poi.lng, pkg.hotel.lat, pkg.hotel.lng);
        const distEl = document.createElement('li');
        distEl.className = 'dist-connector';
        distEl.innerHTML = `<span class="dist-line"></span><span class="dist-badge">↓ ${distKm.toFixed(1)} km → 🏨</span><span class="dist-line"></span>`;
        list.appendChild(distEl);
      }
    });
  });
}

// ============================================================
// Swap modal
// ============================================================
function openSwapModal(dayIdx, poiIdx) {
  const currentPoi = STATE.selectedPkg.days[dayIdx].pois[poiIdx];
  STATE.swapContext = {dayIdx, poiIdx, currentPoi, mode: 'swap', categoryFilter: 'all'};
  document.getElementById('swapTitle').textContent = 'เปลี่ยนสถานที่';
  document.getElementById('swapCurrentInfo').textContent =
    `ปัจจุบัน: ${CAT_EMOJI[currentPoi.category] || ''} ${currentPoi.name_th}`;
  document.getElementById('swapFilter').value = '';
  renderSwapList();
  document.getElementById('swapModal').classList.add('open');
}

function addPoiToDay(dayIdx) {
  STATE.swapContext = {dayIdx, poiIdx: null, currentPoi: null, mode: 'add', categoryFilter: 'all'};
  document.getElementById('swapTitle').textContent = 'เพิ่มจุดใหม่';
  document.getElementById('swapCurrentInfo').textContent = `เพิ่มในวันที่ ${dayIdx + 1}`;
  document.getElementById('swapFilter').value = '';
  renderSwapList();
  document.getElementById('swapModal').classList.add('open');
}

function setCategoryFilter(cat) {
  STATE.swapContext.categoryFilter = cat;
  renderSwapList();
}

function renderSwapList() {
  const ctx = STATE.swapContext;
  const usedIds = new Set();
  STATE.selectedPkg.days.forEach(d => d.pois.forEach(p => usedIds.add(p.id)));
  const all = STATE.pois.filter(p => !usedIds.has(p.id));

  const counts = {all: all.length};
  all.forEach(p => { counts[p.category] = (counts[p.category] || 0) + 1; });

  const filterCat = ctx.categoryFilter || 'all';
  const candidates = (filterCat === 'all' ? all : all.filter(p => p.category === filterCat))
    .sort((a, b) => b.score - a.score);

  const cats = ['all', 'beach', 'temple', 'viewpoint', 'culture', 'market', 'activity', 'restaurant'];
  const filterButtons = cats
    .filter(c => counts[c])
        .map(c => `<button class="cat-btn ${c === filterCat ? 'active' : ''}" onclick="setCategoryFilter('${c}')">
                 ${c === 'all' ? '' : CAT_EMOJI[c] + ' '}${CAT_LABELS[c]} <span style="opacity:0.7">${counts[c]}</span>
               </button>`).join('');

  const list = document.getElementById('swapList');
  list.innerHTML = `
    <div class="cat-filter">${filterButtons}</div>
    ${candidates.length === 0
      ? '<div class="empty-msg">ไม่มีจุดที่ตรงเงื่อนไข</div>'
      : candidates.map(p => `
        <div class="swap-option" onclick="confirmSwap('${p.id}')">
          <div class="opt-info">
            <b>${CAT_EMOJI[p.category] || ''} ${p.name_th}</b>
            <span class="meta">${CAT_LABELS[p.category]} · ${p.cost} ฿ · ${p.duration_min} นาที</span>
          </div>
          <span class="opt-score">★ ${p.score}</span>
        </div>
      `).join('')
    }
  `;
}

function filterSwapList() {
  const q = document.getElementById('swapFilter').value.toLowerCase();
  document.querySelectorAll('.swap-option').forEach(el => {
    el.style.display = el.textContent.toLowerCase().includes(q) ? 'flex' : 'none';
  });
}

async function confirmSwap(newPoiId) {
  const ctx = STATE.swapContext;
  const newPoi = STATE.poisById[newPoiId];
  if (ctx.mode === 'swap') {
    STATE.selectedPkg.days[ctx.dayIdx].pois[ctx.poiIdx] = newPoi;
  } else {
    STATE.selectedPkg.days[ctx.dayIdx].pois.push(newPoi);
  }
  closeSwapModal();
  await recomputeAndRefresh();
}

function removePoi(dayIdx, poiIdx) {
  STATE.selectedPkg.days[dayIdx].pois.splice(poiIdx, 1);
  recomputeAndRefresh();
}

function closeSwapModal() {
  document.getElementById('swapModal').classList.remove('open');
  STATE.swapContext = null;
}

// ============================================================
// Re-shuffle: regenerate the selected tier's package in-place
// ============================================================
async function reshufflePackage() {
  if (!STATE.selectedPkg) return;
  const targetTier = STATE.selectedPkg.tier;

  const budget    = +document.getElementById('budget').value;
  const days      = getSelectedDays();
  const travelers = +document.getElementById('travelers').value;
  const includeHotel = days === 1 ? false : (document.getElementById('includeHotel')?.checked !== false);

  const detailEl = document.getElementById('detailPanel');
  // Inject animated overlay
  const overlay = document.createElement('div');
  overlay.id = 'reshuffleOverlay';
  overlay.innerHTML = `<div class="reshuffle-overlay-inner">
    <svg class="reshuffle-ring" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="25" cy="25" r="20" stroke="rgba(34,211,238,0.25)" stroke-width="3"/>
      <circle cx="25" cy="25" r="20" stroke="#22d3ee" stroke-width="3" stroke-dasharray="40 90" stroke-linecap="round"/>
    </svg>
    <span>กำลังสุ่มสถานที่ใหม่...</span>
  </div>`;
  detailEl.appendChild(overlay);
  detailEl.classList.add('reshuffling');
  const t = showToast('กำลังสุ่มสถานที่ใหม่...', 'loading', 30000);

  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 25000);
    const res = await fetch(`${API_BASE}/api/packages`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        budget, days, travelers,
        seed: Math.floor(Math.random() * 1000000),
        algorithm: SELECTED_ALGO,
        include_hotel: includeHotel,
      }),
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Update global package list
    STATE.packages = data.packages;
    STATE.includeHotel = includeHotel;

    // Find the matching tier (or fall back to same index)
    const tierIdx = data.packages.findIndex(p => p.tier === targetTier);
    const newIdx  = tierIdx >= 0 ? tierIdx : STATE.selectedIdx;
    STATE.selectedIdx = newIdx;
    STATE.selectedPkg = JSON.parse(JSON.stringify(data.packages[newIdx]));

    // Refresh package cards without clearing detail section
    renderPackages();
    document.querySelectorAll('.package-card').forEach((c, i) =>
      c.classList.toggle('selected', i === newIdx)
    );

    // Update detail in-place
    renderDetail(STATE.selectedPkg);
    setTimeout(() => {
      STATE.map.invalidateSize();
      drawOnMap(STATE.selectedPkg);
    }, 80);

    t.remove();
    showToast(`สุ่มใหม่แล้ว! Score ${STATE.selectedPkg.total_score}`, 'ok');
  } catch (e) {
    t.remove();
    showToast(`ผิดพลาด: ${e.message}`, 'error');
  } finally {
    detailEl.classList.remove('reshuffling');
    document.getElementById('reshuffleOverlay')?.remove();
  }
}

async function recomputeAndRefresh() {
  const t = showToast('กำลังคำนวณเส้นทางใหม่...', 'loading', 10000);
  try {
    const routes = STATE.selectedPkg.days.map(d => d.pois.map(p => p.id));
    const res = await fetch(`${API_BASE}/api/recompute`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        hotel_id: STATE.selectedPkg.hotel.id,
        days: STATE.selectedPkg.days.length,
        budget: 100000,
        routes,
        travelers: +document.getElementById('travelers').value,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    STATE.selectedPkg = data;
    drawOnMap(data);
    renderDetail(data);
    t.remove();
    if (data.violations.length) {
      showToast(`อัปเดตแล้ว · ${data.violations.length} คำเตือน`, 'error', 4000);
    } else {
      showToast(`อัปเดต! Score ${data.total_score}`, 'ok');
    }
  } catch (e) {
    t.remove();
    showToast(`ผิดพลาด: ${e.message}`, 'error');
  }
}

function fmt(n) { return Math.round(n).toLocaleString('th-TH'); }

function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371, dLat = (lat2-lat1)*Math.PI/180, dLng = (lng2-lng1)*Math.PI/180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
  return R * 2 * Math.asin(Math.sqrt(a));
}


document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSwapModal();
});
