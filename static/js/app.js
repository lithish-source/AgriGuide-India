/* ==========================================================================
   AgriGuide India — Frontend JavaScript
   Handles: search, district profile load, Plotly charts, AI advisor, compare.
   ========================================================================== */

const API = {
  states: '/api/states',
  search: (q) => `/api/search?q=${encodeURIComponent(q)}`,
  profile: (s, d) => `/api/profile/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  crops: (s, d, n=5) => `/api/crops/${encodeURIComponent(s)}/${encodeURIComponent(d)}?n=${n}`,
  cropsAll: (s, d) => `/api/crops-all/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  trend: (s, d) => `/api/trend/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  risks: (s, d) => `/api/risks/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  alternatives: (s, d) => `/api/alternatives/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  mapState: '/api/map/state',
  mapDistrict: '/api/map/district',
  advisor: '/api/advisor',
  compare: (sa, da, sb, db) => `/api/compare?state_a=${encodeURIComponent(sa)}&district_a=${encodeURIComponent(da)}&state_b=${encodeURIComponent(sb)}&district_b=${encodeURIComponent(db)}`,
  report: (s, d) => `/api/report/${encodeURIComponent(s)}/${encodeURIComponent(d)}`,
  nearestDistrict: (lat, lon) => `/api/nearest-district?lat=${lat}&lon=${lon}`,
};

const CATEGORY_COLORS = {
  Excellent: '#16a34a', Good: '#eab308', Moderate: '#f97316', Poor: '#dc2626'
};

const PLOT_LAYOUT = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: { color: '#cbd5e1', family: 'Inter, sans-serif' },
  margin: { l: 50, r: 30, t: 40, b: 50 },
  xaxis: { gridcolor: '#1f2a47', zerolinecolor: '#1f2a47' },
  yaxis: { gridcolor: '#1f2a47', zerolinecolor: '#1f2a47' },
};

const PLOT_CONFIG = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
};

/* ----------------------------- helpers ----------------------------- */
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${await res.text()}`);
  return res.json();
}

function categoryColor(cat) {
  return CATEGORY_COLORS[cat] || '#94a3b8';
}

function categoryClass(cat) { return `cat-${cat}`; }

function fmt(n, digits=0) {
  if (n == null || isNaN(n)) return '—';
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: digits });
}

/* ==========================================================================
   State index loader (used by every page)
   ========================================================================== */
let STATE_DISTRICTS = null;
async function loadStatesIndex() {
  if (STATE_DISTRICTS) return STATE_DISTRICTS;
  STATE_DISTRICTS = await fetchJSON(API.states);
  return STATE_DISTRICTS;
}

function populateStateDropdown(selectEl, includeAll=false) {
  if (!selectEl) return;
  selectEl.innerHTML = includeAll ? '<option value="">All States</option>' : '<option value="">Select State</option>';
  Object.keys(STATE_DISTRICTS).sort().forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    selectEl.appendChild(opt);
  });
}

function populateDistrictDropdown(selectEl, state, includeAll=false) {
  if (!selectEl) return;
  selectEl.innerHTML = includeAll ? '<option value="">All Districts</option>' : '<option value="">Select District</option>';
  if (!state || !STATE_DISTRICTS[state]) return;
  STATE_DISTRICTS[state].forEach(d => {
    const opt = document.createElement('option');
    opt.value = d; opt.textContent = d;
    selectEl.appendChild(opt);
  });
}

/* ==========================================================================
   HOME PAGE — search + profile + map + advisor
   ========================================================================== */

let currentProfile = null;

document.addEventListener('DOMContentLoaded', async () => {
  const isHome = document.body.dataset.page === 'home';
  const isCompare = document.body.dataset.page === 'compare';
  const isAdvisor = document.body.dataset.page === 'advisor';

  try { await loadStatesIndex(); }
  catch(e) { console.error('Failed to load states', e); }

  if (isHome) initHomePage();
  if (isCompare) initComparePage();
  if (isAdvisor) initAdvisorPage();

  initFloatingAdvisor();
});

/* ---------------------- Home: search + profile ---------------------- */
function initHomePage() {
  // Header search (state + district dropdowns)
  const stateSel = $('#stateSelect');
  const districtSel = $('#districtSelect');
  populateStateDropdown(stateSel);
  stateSel.addEventListener('change', () => {
    populateDistrictDropdown(districtSel, stateSel.value);
  });
  districtSel.addEventListener('change', () => {
    if (stateSel.value && districtSel.value) {
      loadDistrictProfile(stateSel.value, districtSel.value);
    }
  });

  // Hero search bar (free-text)
  const searchInput = $('#heroSearchInput');
  const searchResults = $('#heroSearchResults');
  if (searchInput) {
    let timer;
    searchInput.addEventListener('input', () => {
      clearTimeout(timer);
      const q = searchInput.value.trim();
      if (q.length < 2) { searchResults.classList.remove('show'); return; }
      timer = setTimeout(async () => {
        const results = await fetchJSON(API.search(q));
        searchResults.innerHTML = results.length === 0
          ? '<div class="search-result"><span class="text-muted">No matches</span></div>'
          : results.map(r => `
              <div class="search-result" data-state="${r.state}" data-district="${r.district}">
                <div><div class="name">${r.district}</div><div class="state">${r.state}</div></div>
                <span class="score" style="color:${categoryColor(r.category)}">${r.suitability_score}</span>
              </div>`).join('');
        searchResults.classList.add('show');
      }, 200);
    });
    searchResults.addEventListener('click', (e) => {
      const item = e.target.closest('.search-result');
      if (!item) return;
      loadDistrictProfile(item.dataset.state, item.dataset.district);
      searchInput.value = '';
      searchResults.classList.remove('show');
      // Sync dropdowns
      stateSel.value = item.dataset.state;
      stateSel.dispatchEvent(new Event('change'));
      setTimeout(() => { districtSel.value = item.dataset.district; }, 100);
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-bar')) searchResults.classList.remove('show');
    });
  }

  // Detect location
  $('#detectLocationBtn')?.addEventListener('click', detectLocation);

  // Load map
  loadIndiaMap();

  // If district passed in URL hash (#state/district), auto-load
  const hash = location.hash.slice(1);
  if (hash && hash.includes('/')) {
    const [s, d] = hash.split('/').map(decodeURIComponent);
    if (s && d) {
      stateSel.value = s;
      stateSel.dispatchEvent(new Event('change'));
      setTimeout(() => { districtSel.value = d; loadDistrictProfile(s, d); }, 200);
    }
  }
}

async function detectLocation() {
  const btn = $('#detectLocationBtn');
  if (!btn) return;

  if (!navigator.geolocation) {
    alert('Geolocation is not supported by your browser. Trying IP-based location instead...');
    tryIPGeolocation(btn);
    return;
  }

  // Check secure context (geolocation needs HTTPS or localhost)
  if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
    console.warn('Not on secure context, skipping GPS. Trying IP fallback.');
    tryIPGeolocation(btn);
    return;
  }

  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Detecting...';

  navigator.geolocation.getCurrentPosition(async (pos) => {
    const { latitude, longitude } = pos.coords;
    console.log('GPS success:', latitude, longitude);
    try {
      const match = await reverseGeocodeToDistrict(latitude, longitude);
      if (match) {
        console.log('Matched:', match);
        loadDistrictProfile(match.state, match.district);
        syncDropdowns(match.state, match.district);
      } else {
        // Name matching failed — try nearest district by distance
        console.log('Name matching failed, trying nearest-district fallback...');
        const nearest = await fetchJSON(API.nearestDistrict(latitude, longitude) + '&n=1');
        if (nearest && nearest.length > 0) {
          console.log('Nearest district:', nearest[0]);
          loadDistrictProfile(nearest[0].state, nearest[0].district);
          syncDropdowns(nearest[0].state, nearest[0].district);
        } else {
          alert('Could not match your location to any Indian district. Please search manually.');
        }
      }
    } catch (e) {
      console.error('Reverse geocoding error:', e);
      alert('Could not determine your district. Please search manually.\n\nError: ' + (e.message || e));
    }
    btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
  }, (err) => {
    console.error('GPS error:', err.code, err.message);
    let msg = 'Location detection failed.';
    if (err.code === 1) msg = 'Location permission denied. Trying IP-based fallback...';
    else if (err.code === 2) msg = 'Location unavailable. Trying IP-based fallback...';
    else if (err.code === 3) msg = 'Location request timed out. Trying IP-based fallback...';
    // Don't alert — just try IP fallback silently
    btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
    tryIPGeolocation(btn);
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
}

/* Helper: sync the state/district dropdowns to match a loaded profile */
function syncDropdowns(state, district) {
  const stateSel = $('#stateSelect');
  if (stateSel) {
    stateSel.value = state;
    stateSel.dispatchEvent(new Event('change'));
    setTimeout(() => {
      const dSel = $('#districtSelect');
      if (dSel) dSel.value = district;
    }, 200);
  }
}

/* IP-based geolocation fallback — works on HTTP, less accurate than GPS */
async function tryIPGeolocation(btn) {
  if (!btn) return;
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Trying IP location...';
  try {
    const r = await fetch('https://ipapi.co/json/');
    if (!r.ok) throw new Error('IP geolocation failed');
    const j = await r.json();
    console.log('IP geolocation result:', j);
    if (j.latitude && j.longitude) {
      const match = await reverseGeocodeToDistrict(j.latitude, j.longitude);
      if (match) {
        console.log('IP-based match:', match);
        loadDistrictProfile(match.state, match.district);
        syncDropdowns(match.state, match.district);
        btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
        return;
      }
      // Try nearest district
      const nearest = await fetchJSON(API.nearestDistrict(j.latitude, j.longitude) + '&n=1');
      if (nearest && nearest.length > 0) {
        console.log('IP-based nearest:', nearest[0]);
        loadDistrictProfile(nearest[0].state, nearest[0].district);
        syncDropdowns(nearest[0].state, nearest[0].district);
        btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
        return;
      }
    }
    btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
    alert('Could not determine your district automatically. Please search manually using the search box.');
  } catch (e) {
    console.warn('IP geolocation failed:', e);
    btn.disabled = false; btn.innerHTML = '📍 Detect My Location';
    alert('Could not determine your location. Please search your district manually using the search box above.');
  }
}

/* ---------------------- Reverse geocoding + fuzzy matching ---------------------- *
 * The dataset uses canonical Indian state/district names like "Tamil Nadu",
 * "Andhra Pradesh", "Uttar Pradesh". Reverse-geocoders often return accented
 * or partially different strings ("Tamil Nādu", "Telangana", "Puducherry").
 * We normalise Unicode, strip punctuation, and use Levenshtein-based fuzzy
 * matching to find the best in-database district for any lat/lon.
 */

function normalize(s) {
  if (!s) return '';
  return s.toString()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')   // strip accents
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')                        // strip punctuation
    .replace(/\s+/g, ' ')
    .trim();
}

function levenshtein(a, b) {
  if (!a) return b ? b.length : 0;
  if (!b) return a.length;
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)]);
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i-1] === b[j-1]
        ? dp[i-1][j-1]
        : Math.min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1]) + 1;
    }
  }
  return dp[m][n];
}

// Similarity 0-1 between two strings (1 = identical, 0 = no relation)
function similarity(a, b) {
  const na = normalize(a), nb = normalize(b);
  if (!na || !nb) return 0;
  if (na === nb) return 1;
  if (na.includes(nb) || nb.includes(na)) return 0.85;
  const d = levenshtein(na, nb);
  return 1 - d / Math.max(na.length, nb.length);
}

// Try multiple reverse geocoders, return best {state, district, score}
async function reverseGeocodeToDistrict(lat, lon) {
  if (!STATE_DISTRICTS) await loadStatesIndex();
  const allStates = Object.keys(STATE_DISTRICTS);

  // --- Pass 1: Nominatim (OpenStreetMap) — best for Indian district names ---
  let addr = null;
  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`,
      { headers: { 'Accept-Language': 'en' } }
    );
    if (r.ok) {
      const j = await r.json();
      addr = j.address || null;
    }
  } catch (e) { console.warn('Nominatim failed', e); }

  // --- Pass 2: BigDataCloud fallback (no key needed) ---
  if (!addr) {
    try {
      const r = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`);
      if (r.ok) {
        const j = await r.json();
        const admin2 = j.localityInfo?.administrative?.slice(-2)[0]?.name;
        addr = {
          state: j.principalSubdivision,
          state_district: admin2,
          county: j.locality || j.city,
          city: j.city || j.locality,
          town: j.locality,
        };
      }
    } catch (e) { console.warn('BigDataCloud failed', e); }
  }

  if (addr) {
    // ----- Match state -----
    const stateCandidates = [addr.state, addr.state_district, addr.region].filter(Boolean);
    let bestState = null, bestStateScore = 0;
    for (const sc of stateCandidates) {
      for (const dbState of allStates) {
        const sim = similarity(sc, dbState);
        const simShort = similarity(sc.split(' ')[0], dbState.split(' ')[0]) * 0.9;
        const score = Math.max(sim, simShort);
        if (score > bestStateScore) { bestStateScore = score; bestState = dbState; }
      }
    }

    if (bestState && bestStateScore >= 0.55) {
      const districts = STATE_DISTRICTS[bestState] || [];
      if (districts.length) {
        const districtCandidates = [
          addr.state_district, addr.county, addr.city, addr.town,
          addr.village, addr.municipality, addr.suburb,
        ].filter(Boolean);

        let bestDistrict = null, bestDistrictScore = 0;
        const cleanRe = /\b(district|taluka|taluk|tehsil|division|sub[- ]?district)\b/gi;

        for (const dc of districtCandidates) {
          for (const dbDistrict of districts) {
            const sim = similarity(dc, dbDistrict);
            const simClean = similarity(dc.replace(cleanRe, '').trim(), dbDistrict) * 0.95;
            const score = Math.max(sim, simClean);
            if (score > bestDistrictScore) { bestDistrictScore = score; bestDistrict = dbDistrict; }
          }
        }

        // If district match is still weak, expand search to ALL states
        if (bestDistrictScore < 0.55) {
          for (const dc of districtCandidates) {
            for (const dbState of allStates) {
              for (const dbDistrict of STATE_DISTRICTS[dbState]) {
                const score = similarity(dc, dbDistrict);
                if (score > bestDistrictScore) {
                  bestDistrictScore = score;
                  bestDistrict = dbDistrict;
                  bestState = dbState;
                }
              }
            }
          }
        }

        if (bestDistrict && bestDistrictScore >= 0.45) {
          console.log(`Location matched by name: ${bestDistrict}, ${bestState} (state=${bestStateScore.toFixed(2)}, district=${bestDistrictScore.toFixed(2)})`);
          return { state: bestState, district: bestDistrict, score: bestDistrictScore, method: 'name' };
        }
      }
    }
  }

  // --- Pass 3 (FALLBACK): Nearest-district by haversine distance ---
  // When name-matching fails (e.g. user is in a town like "Ponneri" that
  // isn't itself a district name), use the actual lat/lon to find the
  // closest district in our database. This always works as long as the
  // user is somewhere in India.
  try {
    const r = await fetch(API.nearestDistrict(lat, lon) + '&n=1');
    if (r.ok) {
      const j = await r.json();
      if (Array.isArray(j) && j.length > 0) {
        const nearest = j[0];
        console.log(`Location matched by nearest-district fallback: ${nearest.district}, ${nearest.state} (${nearest.distance_km} km away)`);
        return {
          state: nearest.state,
          district: nearest.district,
          score: 1.0,
          method: 'nearest',
          distance_km: nearest.distance_km,
        };
      }
    }
  } catch (e) { console.warn('Nearest-district fallback failed', e); }

  console.warn('All geolocation methods failed.');
  return null;
}

async function loadDistrictProfile(state, district) {
  const section = $('#profileSection');
  if (!section) return;
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Show skeleton
  section.innerHTML = `<div class="center"><div class="spinner"></div><p class="text-muted">Loading ${district}, ${state}…</p></div>`;

  try {
    const profile = await fetchJSON(API.profile(state, district));
    currentProfile = profile;
    location.hash = `${encodeURIComponent(state)}/${encodeURIComponent(district)}`;
    renderProfile(profile);
    // Update advisor context labels immediately so the chatbot knows which district is loaded
    const ctxFab = $('#advisorCtxFab');
    if (ctxFab) ctxFab.textContent = `Context: ${profile.district}, ${profile.state}`;
    const ctxFull = $('#advisorCtxFull');
    if (ctxFull) ctxFull.textContent = `Context: ${profile.district}, ${profile.state}`;
    // Load auxiliary data in parallel
    renderCrops(state, district);
    renderRisks(profile.risks);
    renderAlternatives(state, district);
    renderProfileCharts(profile);
  } catch(e) {
    section.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Could not load profile</h3><p>${e.message}</p></div>`;
  }
}

function renderProfile(p) {
  const section = $('#profileSection');
  const scorePct = p.suitability_score;
  const color = categoryColor(p.suitability_category);
  section.innerHTML = `
    <div class="fade-in">
      <div class="section-header" style="margin-bottom: 1rem;">
        <div>
          <h2>${p.district}, ${p.state}</h2>
          <p>Complete agricultural suitability profile based on ${p.n_years_data} years of crop-production data</p>
        </div>
        <a class="btn btn-secondary btn-sm" href="${API.report(p.state, p.district)}" target="_blank">⬇ Download PDF Report</a>
      </div>

      <!-- Score -->
      <div class="card" style="margin-bottom: 1rem;">
        <div class="score-display">
          <div class="score-circle" style="--score-pct: ${scorePct}; --score-color: ${color};">
            <div class="score-num">${scorePct.toFixed(1)}<small>/100</small></div>
          </div>
          <div class="score-info">
            <span class="category ${categoryClass(p.suitability_category)}">${p.suitability_category}</span>
            <div class="range">
              Range: <span class="cat-Poor" style="padding:2px 6px;border-radius:4px;">0-25 Poor</span> ·
              <span class="cat-Moderate" style="padding:2px 6px;border-radius:4px;">26-50 Moderate</span> ·
              <span class="cat-Good" style="padding:2px 6px;border-radius:4px;">51-75 Good</span> ·
              <span class="cat-Excellent" style="padding:2px 6px;border-radius:4px;">76-100 Excellent</span>
            </div>
            <div class="text-muted" style="margin-top:0.6rem;font-size:0.9rem;">${p.summary.headline}</div>
          </div>
        </div>
      </div>

      <!-- Indicator cards -->
      <div class="card-grid cols-4" style="margin-bottom: 1rem;">
        <div class="card">
          <div class="card-title">Rainfall</div>
          <div class="card-value">${p.rainfall_mm} <small style="font-size:0.7em;color:var(--text-2);">mm/year</small></div>
          <div class="card-sub">${p.rainfall_mm < 700 ? 'Low' : p.rainfall_mm < 1200 ? 'Moderate' : p.rainfall_mm < 1800 ? 'Good' : 'High'}</div>
        </div>
        <div class="card">
          <div class="card-title">Soil Quality</div>
          <div class="card-value">${p.soil_quality.toFixed(1)}<small style="font-size:0.5em;color:var(--text-2);">/100</small></div>
          <div class="card-sub">${p.soil_quality < 40 ? 'Low' : p.soil_quality < 70 ? 'Moderate' : 'High'}</div>
        </div>
        <div class="card">
          <div class="card-title">Avg Temperature</div>
          <div class="card-value">${p.temperature_c.toFixed(1)}<small style="font-size:0.6em;color:var(--text-2);"> °C</small></div>
          <div class="card-sub">${p.temperature_c > 30 ? 'Warm zone' : p.temperature_c > 22 ? 'Tropical' : 'Cooler zone'}</div>
        </div>
        <div class="card">
          <div class="card-title">Irrigation Dependency</div>
          <div class="card-value">${p.irrigation_dependency.toFixed(1)}<small style="font-size:0.5em;color:var(--text-2);">/100</small></div>
          <div class="card-sub">${p.irrigation_dependency > 60 ? 'High' : p.irrigation_dependency > 30 ? 'Moderate' : 'Low'}</div>
        </div>
      </div>

      <!-- Crops + Risks side-by-side -->
      <div class="card-grid cols-2" style="margin-bottom: 1rem;">
        <div class="card">
          <div class="card-title">Top Recommended Crops</div>
          <div id="cropList"><div class="center"><div class="spinner"></div></div></div>
        </div>
        <div class="card">
          <div class="card-title">Risk Factors</div>
          <div id="riskList"><div class="center"><div class="spinner"></div></div></div>
        </div>
      </div>

      <!-- Charts -->
      <div class="card-grid cols-2" style="margin-bottom: 1rem;">
        <div class="card">
          <div class="card-title">Crop Suitability Radar</div>
          <div id="radarChart" style="height: 340px;"></div>
        </div>
        <div class="card">
          <div class="card-title">Top Crops — Suitability %</div>
          <div id="cropBarChart" style="height: 340px;"></div>
        </div>
      </div>

      <div class="card-grid cols-2" style="margin-bottom: 1rem;">
        <div class="card">
          <div class="card-title">Crop Distribution</div>
          <div id="cropPieChart" style="height: 340px;"></div>
        </div>
        <div class="card">
          <div class="card-title">Suitability vs Yield</div>
          <div id="scatterChart" style="height: 340px;"></div>
        </div>
      </div>

      <!-- Soil + Water quality radar charts -->
      <div class="card-grid cols-2" style="margin-bottom: 1rem;">
        <div class="card">
          <div class="card-title">Soil Micronutrient Profile (Radar)</div>
          <div id="soilRadarChart" style="height: 340px;"></div>
        </div>
        <div class="card">
          <div class="card-title">Water Quality Parameters (Radar)</div>
          <div id="waterRadarChart" style="height: 340px;"></div>
        </div>
      </div>

      <!-- Yearly trend -->
      <div class="card" style="margin-bottom: 1rem;">
        <div class="card-title">Agricultural Productivity Trend (1997–2023)</div>
        <p class="text-muted" style="font-size:0.85rem;margin-top:0;">Yearly production, cultivated area, and average yield over ${p.n_years_data} years of data.</p>
        <div id="trendChart" style="height: 380px;"></div>
      </div>

      <!-- Alternatives -->
      <div class="card">
        <div class="card-title">Best Alternative Districts</div>
        <p class="text-muted" style="font-size:0.85rem;margin-top:0;">Nearby districts with better agricultural conditions</p>
        <div id="altList" style="margin-top:0.8rem;"><div class="center"><div class="spinner"></div></div></div>
      </div>
    </div>
  `;
}

async function renderCrops(state, district) {
  const wrap = $('#cropList');
  if (!wrap) return;
  try {
    const crops = await fetchJSON(API.crops(state, district, 5));
    if (!crops.length) { wrap.innerHTML = '<p class="text-muted">No crop data available.</p>'; return; }
    wrap.innerHTML = crops.map((c, i) => `
      <div class="crop-item">
        <div class="crop-rank">${i+1}</div>
        <div class="crop-body">
          <div class="crop-name">${c.crop} <span class="crop-type">· ${c.type||''}</span></div>
          <div class="crop-bar"><div class="crop-bar-fill" style="width: ${c.suitability_pct}%"></div></div>
        </div>
        <div class="crop-score">
          <div class="pct">${c.suitability_pct.toFixed(1)}%</div>
          <div class="conf">conf ${c.confidence.toFixed(0)}%</div>
          <span class="crop-rating ${c.performance_rating.replace(/\s/g,'')}">${c.performance_rating}</span>
        </div>
      </div>`).join('');
  } catch(e) { wrap.innerHTML = `<p class="text-muted">Failed to load crops.</p>`; }
}

function renderRisks(risks) {
  const wrap = $('#riskList');
  if (!wrap) return;
  if (!risks || !risks.length) { wrap.innerHTML = '<p class="text-muted">No risk data.</p>'; return; }
  wrap.innerHTML = risks.map(r => `
    <div class="risk-card level-${r.level}" style="margin-bottom:0.6rem;">
      <div class="risk-icon">!</div>
      <div class="risk-body">
        <div class="risk-name">${r.name} <span class="risk-level">${r.level}</span></div>
        <div class="risk-detail">${r.detail}</div>
        <div class="risk-mitigation"><strong>Mitigation:</strong> ${r.mitigation}</div>
      </div>
    </div>`).join('');
}

async function renderAlternatives(state, district) {
  const wrap = $('#altList');
  if (!wrap) return;
  try {
    const alts = await fetchJSON(API.alternatives(state, district));
    if (!alts.length) {
      wrap.innerHTML = `<p class="text-muted">No nearby districts with better conditions — your district is already well-suited for the region.</p>`;
      return;
    }
    wrap.innerHTML = `
      <div class="card-grid cols-3">
        ${alts.map(a => `
          <div class="card" style="cursor:pointer;" onclick="loadDistrictProfile('${a.state}','${a.district}')">
            <div class="card-title">${a.district}</div>
            <div class="card-value" style="color:${categoryColor(a.category)}">${a.suitability_score}</div>
            <div class="card-sub">${a.distance_km} km away · ${a.category}</div>
            <div class="text-accent" style="font-size:0.85rem;margin-top:0.4rem;">Top: ${a.top_crop}</div>
          </div>`).join('')}
      </div>`;
  } catch(e) { wrap.innerHTML = `<p class="text-muted">Failed to load alternatives.</p>`; }
}

/* ---------------------- Charts ---------------------- */
async function renderProfileCharts(profile) {
  // Need full crop distribution for radar + pie + scatter
  let cropsAll = [];
  try { cropsAll = await fetchJSON(API.cropsAll(profile.state, profile.district)); }
  catch(e) { console.warn(e); }
  const top5 = cropsAll.slice(0, 5);

  // Radar — top 5 crops across 4 metrics (suitability, confidence, yield(0-100), area(0-100))
  if ($('#radarChart')) {
    const maxYield = Math.max(...top5.map(c => c.avg_yield), 1);
    const maxArea = Math.max(...top5.map(c => c.total_area), 1);
    const traces = top5.map((c, i) => ({
      type: 'scatterpolar',
      r: [c.suitability_pct, c.confidence, (c.avg_yield/maxYield)*100, (c.total_area/maxArea)*100, c.suitability_pct],
      theta: ['Suitability','Confidence','Yield','Cultivation Scale','Suitability'],
      fill: 'toself',
      name: c.crop,
      line: { color: ['#16a34a','#eab308','#3b82f6','#f97316','#a855f7'][i % 5] },
      opacity: 0.55,
    }));
    Plotly.react('radarChart', traces, {
      ...PLOT_LAYOUT,
      polar: { radialaxis: { range: [0, 100], gridcolor: '#1f2a47', color: '#64748b' },
               angularaxis: { gridcolor: '#1f2a47', color: '#cbd5e1' } },
      legend: { orientation: 'h', y: -0.15, font: { color: '#cbd5e1', size: 11 } },
      margin: { l: 30, r: 30, t: 10, b: 50 },
    }, PLOT_CONFIG);
  }

  // Bar — top 5 suitability
  if ($('#cropBarChart')) {
    Plotly.react('cropBarChart', [{
      type: 'bar',
      x: top5.map(c => c.suitability_pct),
      y: top5.map(c => c.crop),
      orientation: 'h',
      marker: { color: top5.map((c,i) => ['#16a34a','#22c55e','#65a30d','#eab308','#f97316'][i % 5]),
                line: { color: 'rgba(0,0,0,0.2)', width: 1 } },
      text: top5.map(c => `${c.suitability_pct.toFixed(1)}%`),
      textposition: 'outside',
      textfont: { color: '#cbd5e1' },
      hovertemplate: '<b>%{y}</b><br>Suitability: %{x:.1f}%<extra></extra>',
    }], {
      ...PLOT_LAYOUT,
      xaxis: { ...PLOT_LAYOUT.xaxis, range: [0, 100], title: 'Suitability %' },
      yaxis: { ...PLOT_LAYOUT.yaxis, autorange: 'reversed' },
      margin: { l: 110, r: 40, t: 10, b: 40 },
    }, PLOT_CONFIG);
  }

  // Pie — full distribution
  if ($('#cropPieChart') && cropsAll.length) {
    const top = cropsAll.slice(0, 6);
    const others = cropsAll.slice(6).reduce((s, c) => s + c.suitability_pct, 0);
    const labels = top.map(c => c.crop).concat(others > 0 ? ['Others'] : []);
    const values = top.map(c => c.suitability_pct).concat(others > 0 ? [others] : []);
    Plotly.react('cropPieChart', [{
      type: 'pie',
      labels, values,
      hole: 0.55,
      marker: { colors: ['#16a34a','#22c55e','#65a30d','#eab308','#f97316','#dc2626','#64748b'] },
      textinfo: 'label+percent',
      textfont: { color: '#fff', size: 11 },
      hovertemplate: '<b>%{label}</b><br>%{value:.1f} (%{percent})<extra></extra>',
    }], {
      ...PLOT_LAYOUT,
      showlegend: false,
      margin: { l: 10, r: 10, t: 10, b: 10 },
    }, PLOT_CONFIG);
  }

  // Scatter — suitability vs yield (all crops for district)
  if ($('#scatterChart') && cropsAll.length) {
    Plotly.react('scatterChart', [{
      type: 'scatter',
      mode: 'markers+text',
      x: cropsAll.map(c => c.suitability_pct),
      y: cropsAll.map(c => c.avg_yield),
      text: cropsAll.map(c => c.crop),
      textposition: 'top center',
      textfont: { size: 9, color: '#94a3b8' },
      marker: {
        size: cropsAll.map(c => Math.max(8, Math.min(28, c.total_area / 200))),
        color: cropsAll.map(c => c.suitability_pct),
        colorscale: [[0,'#dc2626'],[0.5,'#eab308'],[1,'#16a34a']],
        showscale: false,
        opacity: 0.75,
        line: { color: '#0f172a', width: 1 },
      },
      hovertemplate: '<b>%{text}</b><br>Suitability: %{x:.1f}%<br>Yield: %{y:.2f} t/ha<extra></extra>',
    }], {
      ...PLOT_LAYOUT,
      xaxis: { ...PLOT_LAYOUT.xaxis, title: 'Suitability %', range: [0, 100] },
      yaxis: { ...PLOT_LAYOUT.yaxis, title: 'Avg Yield (t/ha)' },
      margin: { l: 60, r: 20, t: 10, b: 50 },
    }, PLOT_CONFIG);
  }

  // Trend line — yearly production / area / yield
  if ($('#trendChart')) {
    try {
      const trend = await fetchJSON(API.trend(profile.state, profile.district));
      if (!trend.length) {
        $('#trendChart').innerHTML = '<p class="text-muted" style="text-align:center;padding-top:2rem;">No yearly trend data available for this district.</p>';
      } else {
        const years = trend.map(t => t.year);
        const traces = [
          {
            type: 'scatter', mode: 'lines+markers', name: 'Production (t)',
            x: years, y: trend.map(t => t.production),
            line: { color: '#16a34a', width: 2.5 },
            marker: { size: 5 },
            hovertemplate: '<b>%{x}</b><br>Production: %{y:,} t<extra></extra>',
            yaxis: 'y',
          },
          {
            type: 'scatter', mode: 'lines+markers', name: 'Cultivated Area (ha)',
            x: years, y: trend.map(t => t.area),
            line: { color: '#3b82f6', width: 2.5 },
            marker: { size: 5 },
            hovertemplate: '<b>%{x}</b><br>Area: %{y:,} ha<extra></extra>',
            yaxis: 'y',
          },
          {
            type: 'scatter', mode: 'lines+markers', name: 'Avg Yield (t/ha)',
            x: years, y: trend.map(t => t.avg_yield),
            line: { color: '#eab308', width: 2.5, dash: 'dot' },
            marker: { size: 5 },
            hovertemplate: '<b>%{x}</b><br>Yield: %{y:.3f} t/ha<extra></extra>',
            yaxis: 'y2',
          },
        ];
        Plotly.react('trendChart', traces, {
          ...PLOT_LAYOUT,
          xaxis: { ...PLOT_LAYOUT.xaxis, title: 'Year', tickangle: -45 },
          yaxis: { ...PLOT_LAYOUT.yaxis, title: 'Production (t) / Area (ha)', gridcolor: '#1f2a47' },
          yaxis2: {
            title: 'Avg Yield (t/ha)', overlaying: 'y', side: 'right',
            gridcolor: 'rgba(234, 179, 8, 0.15)', color: '#eab308',
            showgrid: false,
          },
          legend: { orientation: 'h', y: -0.32, font: { color: '#cbd5e1' } },
          margin: { l: 70, r: 70, t: 10, b: 80 },
          hovermode: 'x unified',
        }, PLOT_CONFIG);
      }
    } catch(e) {
      console.warn('Trend chart failed', e);
      $('#trendChart').innerHTML = '<p class="text-muted" style="text-align:center;padding-top:2rem;">Failed to load trend data.</p>';
    }
  }

  // Soil nutrient radar chart
  if ($('#soilRadarChart')) {
    const soil = profile.soil_nutrients;
    if (soil && soil.has_data) {
      const nutrients = ['Zn', 'Fe', 'Cu', 'Mn', 'B', 'S'];
      const values = nutrients.map(n => soil[n] ?? 0);
      values.push(values[0]); // close the polygon
      const labels = [...nutrients, nutrients[0]];
      Plotly.react('soilRadarChart', [{
        type: 'scatterpolar',
        r: values,
        theta: labels,
        fill: 'toself',
        name: 'Sufficiency %',
        line: { color: '#16a34a', width: 2 },
        fillcolor: 'rgba(22, 163, 74, 0.2)',
        marker: { size: 6, color: '#22c55e' },
        hovertemplate: '<b>%{theta}</b><br>Sufficiency: %{r:.1f}%<extra></extra>',
      }], {
        ...PLOT_LAYOUT,
        polar: {
          radialaxis: { range: [0, 100], gridcolor: '#1f2a47', color: '#64748b',
                        tickfont: { size: 9, color: '#64748b' } },
          angularaxis: { gridcolor: '#1f2a47', color: '#cbd5e1',
                         tickfont: { size: 12, color: '#cbd5e1' } },
        },
        margin: { l: 60, r: 60, t: 20, b: 40 },
      }, PLOT_CONFIG);
    } else {
      $('#soilRadarChart').innerHTML = '<p class="text-muted" style="text-align:center;padding-top:2rem;">Soil nutrient data not available for this district.</p>';
    }
  }

  // Water quality radar chart
  if ($('#waterRadarChart')) {
    const wq = profile.water_quality;
    if (wq && wq.has_data) {
      // Normalize all parameters to 0-100 scale for the radar
      // EC: 0-3000 (higher = worse, invert so high EC = low score)
      // SAR: 0-30 (higher = worse, invert)
      // Na: 0-1000 (higher = worse, invert)
      // Cl: 0-500 (higher = worse, invert)
      // F: 0-10 (higher = worse, invert)
      // pH: 6.5-8.5 is ideal, deviations are bad
      const params = [
        { label: 'EC\n(Salinity)', val: wq.EC, max: 3000, invert: true },
        { label: 'SAR\n(Sodicity)', val: wq.SAR, max: 30, invert: true },
        { label: 'Na\n(Sodium)', val: wq.Na, max: 1000, invert: true },
        { label: 'Cl\n(Chloride)', val: wq.Cl, max: 500, invert: true },
        { label: 'F\n(Fluoride)', val: wq.F, max: 10, invert: true },
        { label: 'pH\nBalance', val: wq.pH, max: 14, invert: false, ideal: [6.5, 8.5] },
      ];
      const values = params.map(p => {
        if (p.val == null) return 50;
        if (p.ideal) {
          // pH: 100 if in ideal range, drops off outside
          if (p.val >= p.ideal[0] && p.val <= p.ideal[1]) return 100;
          const dist = p.val < p.ideal[0] ? p.ideal[0] - p.val : p.val - p.ideal[1];
          return Math.max(0, 100 - dist * 30);
        }
        const pct = (p.val / p.max) * 100;
        return p.invert ? Math.max(0, 100 - pct) : Math.min(100, pct);
      });
      values.push(values[0]);
      const labels = [...params.map(p => p.label), params[0].label];

      Plotly.react('waterRadarChart', [{
        type: 'scatterpolar',
        r: values,
        theta: labels,
        fill: 'toself',
        name: 'Water Quality',
        line: { color: '#3b82f6', width: 2 },
        fillcolor: 'rgba(59, 130, 246, 0.2)',
        marker: { size: 6, color: '#60a5fa' },
        hovertemplate: '<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>',
      }], {
        ...PLOT_LAYOUT,
        polar: {
          radialaxis: { range: [0, 100], gridcolor: '#1f2a47', color: '#64748b',
                        tickfont: { size: 9, color: '#64748b' } },
          angularaxis: { gridcolor: '#1f2a47', color: '#cbd5e1',
                         tickfont: { size: 10, color: '#cbd5e1' } },
        },
        margin: { l: 60, r: 60, t: 20, b: 40 },
      }, PLOT_CONFIG);
    } else {
      $('#waterRadarChart').innerHTML = '<p class="text-muted" style="text-align:center;padding-top:2rem;">Water quality data not available for this district.</p>';
    }
  }
}

/* ---------------------- India Map ---------------------- */
async function loadIndiaMap() {
  const wrap = $('#indiaMap');
  if (!wrap) return;
  try {
    // Use district scatter (more granular)
    const spec = await fetchJSON(API.mapDistrict);
    Plotly.react('indiaMap', spec.data, spec.layout, { ...PLOT_CONFIG, scrollZoom: true });

    // Add click handler — load profile when district marker clicked
    wrap.on('plotly_click', (data) => {
      if (!data.points || !data.points.length) return;
      const text = data.points[0].text || '';
      const m = text.match(/^([^,]+), (.+?)<br>/);
      if (m) loadDistrictProfile(m[2], m[1]);
    });
  } catch(e) {
    console.error(e);
    wrap.innerHTML = `<p class="text-muted">Failed to load map.</p>`;
  }
}

/* ==========================================================================
   COMPARE PAGE
   ========================================================================== */
function initComparePage() {
  const sa = $('#stateA'), da = $('#districtA');
  const sb = $('#stateB'), db = $('#districtB');
  populateStateDropdown(sa); populateStateDropdown(sb);
  sa.addEventListener('change', () => populateDistrictDropdown(da, sa.value));
  sb.addEventListener('change', () => populateDistrictDropdown(db, sb.value));
  $('#compareBtn').addEventListener('click', async () => {
    if (!sa.value || !da.value || !sb.value || !db.value) {
      alert('Please select both districts.'); return;
    }
    if (sa.value === sb.value && da.value === db.value) {
      alert('Please choose two different districts.'); return;
    }
    await loadComparison(sa.value, da.value, sb.value, db.value);
  });

  // Preselect two well-known districts for demo
  sa.value = 'Tamil Nadu'; sa.dispatchEvent(new Event('change'));
  setTimeout(() => { da.value = 'Coimbatore'; }, 200);
  sb.value = 'Karnataka'; sb.dispatchEvent(new Event('change'));
  setTimeout(() => { db.value = 'Belagavi'; }, 200);
}

async function loadComparison(s1, d1, s2, d2) {
  const out = $('#compareOutput');
  out.classList.remove('hidden');
  out.innerHTML = `<div class="center"><div class="spinner"></div><p class="text-muted">Comparing…</p></div>`;
  try {
    const data = await fetchJSON(API.compare(s1, d1, s2, d2));
    renderComparison(data);
  } catch(e) {
    out.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Comparison failed</h3><p>${e.message}</p></div>`;
  }
}

function renderComparison(data) {
  const { a, b } = data;
  const out = $('#compareOutput');
  const winner = (av, bv, higher=true) => {
    if (av === bv) return ['', ''];
    const aWins = higher ? av > bv : av < bv;
    return aWins ? ['winner-a', ''] : ['', 'winner-b'];
  };

  out.innerHTML = `
    <div class="fade-in">
      <div class="compare-grid" style="margin-bottom: 1.5rem;">
        <div class="compare-side">
          <div class="compare-header" style="--score-color: ${categoryColor(a.category)};">
            <div>
              <h3 style="margin:0;">${a.district}</h3>
              <div class="text-muted" style="font-size:0.85rem;">${a.state}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:1.8rem;font-weight:800;color:${categoryColor(a.category)};">${a.score.toFixed(1)}</div>
              <span class="cat-${a.category}" style="padding:3px 10px;border-radius:999px;font-size:0.78rem;font-weight:700;">${a.category}</span>
            </div>
          </div>
          <div class="card">
            <div class="card-title">Top Crops</div>
            ${a.crops.map((c, i) => `
              <div class="crop-item" style="padding:0.5rem 0.7rem;">
                <div class="crop-rank" style="width:28px;height:28px;font-size:0.85rem;">${i+1}</div>
                <div class="crop-body"><div class="crop-name" style="font-size:0.92rem;">${c.crop}</div></div>
                <div class="crop-score"><div class="pct" style="font-size:1rem;">${c.suitability_pct.toFixed(1)}%</div></div>
              </div>`).join('')}
          </div>
        </div>
        <div class="compare-side">
          <div class="compare-header" style="--score-color: ${categoryColor(b.category)};">
            <div>
              <h3 style="margin:0;">${b.district}</h3>
              <div class="text-muted" style="font-size:0.85rem;">${b.state}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:1.8rem;font-weight:800;color:${categoryColor(b.category)};">${b.score.toFixed(1)}</div>
              <span class="cat-${b.category}" style="padding:3px 10px;border-radius:999px;font-size:0.78rem;font-weight:700;">${b.category}</span>
            </div>
          </div>
          <div class="card">
            <div class="card-title">Top Crops</div>
            ${b.crops.map((c, i) => `
              <div class="crop-item" style="padding:0.5rem 0.7rem;">
                <div class="crop-rank" style="width:28px;height:28px;font-size:0.85rem;">${i+1}</div>
                <div class="crop-body"><div class="crop-name" style="font-size:0.92rem;">${c.crop}</div></div>
                <div class="crop-score"><div class="pct" style="font-size:1rem;">${c.suitability_pct.toFixed(1)}%</div></div>
              </div>`).join('')}
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom: 1rem;">
        <h3 style="margin-bottom: 0.6rem;">Indicator Comparison</h3>
        ${(() => {
          const rows = [
            { label: 'Suitability Score', a: a.score, b: b.score, higher: true, digits: 1 },
            { label: 'Rainfall (mm)', a: a.rainfall_mm, b: b.rainfall_mm, higher: true, digits: 0 },
            { label: 'Soil Quality', a: a.soil_quality, b: b.soil_quality, higher: true, digits: 1 },
            { label: 'Temperature (°C)', a: a.temperature_c, b: b.temperature_c, higher: null, digits: 1 },
            { label: 'Irrigation Dependency', a: a.irrigation_dependency, b: b.irrigation_dependency, higher: false, digits: 1 },
            { label: 'Crops Grown (diversity)', a: a.n_crops_grown, b: b.n_crops_grown, higher: true, digits: 0 },
            { label: 'Yield Score', a: a.metrics.yield_score, b: b.metrics.yield_score, higher: true, digits: 1 },
            { label: 'Efficiency Score', a: a.metrics.efficiency_score, b: b.metrics.efficiency_score, higher: true, digits: 1 },
            { label: 'Diversity Score', a: a.metrics.diversity_score, b: b.metrics.diversity_score, higher: true, digits: 1 },
            { label: 'Scale Score', a: a.metrics.scale_score, b: b.metrics.scale_score, higher: true, digits: 1 },
          ];
          return rows.map(r => {
            const [wa, wb] = r.higher === null ? ['', ''] : winner(r.a, r.b, r.higher);
            return `
              <div class="metric-row">
                <div class="val-a ${wa}">${fmt(r.a, r.digits)}</div>
                <div class="label">${r.label}</div>
                <div class="val-b ${wb}">${fmt(r.b, r.digits)}</div>
              </div>`;
          }).join('');
        })()}
      </div>

      <div class="card-grid cols-2">
        <div class="card">
          <div class="card-title">District Comparison Radar</div>
          <div id="compareRadar" style="height: 400px;"></div>
        </div>
        <div class="card">
          <div class="card-title">Top-5 Crop Suitability</div>
          <div id="compareCropChart" style="height: 400px;"></div>
        </div>
      </div>

      <div class="card-grid cols-2" style="margin-top: 1rem;">
        <div class="card">
          <div class="card-title">Major Risks — ${a.district}</div>
          ${a.risks.map(r => `
            <div class="risk-card level-${r.level}" style="padding:0.7rem 0.9rem;margin-bottom:0.5rem;">
              <div class="risk-icon" style="width:32px;height:32px;font-size:0.8rem;">!</div>
              <div class="risk-body">
                <div class="risk-name" style="font-size:0.92rem;">${r.name} <span class="risk-level">${r.level}</span></div>
                <div class="risk-detail" style="font-size:0.82rem;">${r.detail}</div>
              </div>
            </div>`).join('')}
        </div>
        <div class="card">
          <div class="card-title">Major Risks — ${b.district}</div>
          ${b.risks.map(r => `
            <div class="risk-card level-${r.level}" style="padding:0.7rem 0.9rem;margin-bottom:0.5rem;">
              <div class="risk-icon" style="width:32px;height:32px;font-size:0.8rem;">!</div>
              <div class="risk-body">
                <div class="risk-name" style="font-size:0.92rem;">${r.name} <span class="risk-level">${r.level}</span></div>
                <div class="risk-detail" style="font-size:0.82rem;">${r.detail}</div>
              </div>
            </div>`).join('')}
        </div>
      </div>

      <div style="margin-top: 1rem; text-align: center;">
        <a class="btn btn-secondary" href="${API.report(a.state, a.district)}?cmp_state=${encodeURIComponent(b.state)}&cmp_district=${encodeURIComponent(b.district)}" target="_blank">⬇ Download Comparison Report (${a.district})</a>
      </div>
    </div>
  `;

  // Radar chart
  const metrics = ['Suitability','Yield Score','Efficiency','Diversity','Scale','Consistency'];
  Plotly.react('compareRadar', [
    {
      type: 'scatterpolar', r: [a.score, a.metrics.yield_score, a.metrics.efficiency_score, a.metrics.diversity_score, a.metrics.scale_score, a.metrics.consistency_score, a.score],
      theta: metrics.concat([metrics[0]]), fill: 'toself', name: a.district,
      line: { color: '#16a34a' }, opacity: 0.6,
    },
    {
      type: 'scatterpolar', r: [b.score, b.metrics.yield_score, b.metrics.efficiency_score, b.metrics.diversity_score, b.metrics.scale_score, b.metrics.consistency_score, b.score],
      theta: metrics.concat([metrics[0]]), fill: 'toself', name: b.district,
      line: { color: '#3b82f6' }, opacity: 0.6,
    },
  ], {
    ...PLOT_LAYOUT,
    polar: { radialaxis: { range: [0, 100], gridcolor: '#1f2a47', color: '#64748b' },
             angularaxis: { gridcolor: '#1f2a47', color: '#cbd5e1' } },
    legend: { orientation: 'h', y: -0.1, font: { color: '#cbd5e1' } },
    margin: { l: 30, r: 30, t: 10, b: 50 },
  }, PLOT_CONFIG);

  // Crop comparison grouped bar
  const allCrops = Array.from(new Set([...a.crops.map(c => c.crop), ...b.crops.map(c => c.crop)])).slice(0, 8);
  Plotly.react('compareCropChart', [
    { type: 'bar', name: a.district, x: allCrops,
      y: allCrops.map(c => a.crops.find(x => x.crop === c)?.suitability_pct ?? 0),
      marker: { color: '#16a34a' } },
    { type: 'bar', name: b.district, x: allCrops,
      y: allCrops.map(c => b.crops.find(x => x.crop === c)?.suitability_pct ?? 0),
      marker: { color: '#3b82f6' } },
  ], {
    ...PLOT_LAYOUT,
    barmode: 'group',
    yaxis: { ...PLOT_LAYOUT.yaxis, title: 'Suitability %', range: [0, 100] },
    legend: { orientation: 'h', y: -0.3, font: { color: '#cbd5e1' } },
    margin: { l: 40, r: 20, t: 10, b: 80 },
  }, PLOT_CONFIG);
}

/* ==========================================================================
   ADVISOR PAGE (full-screen)
   ========================================================================== */
function initAdvisorPage() {
  const stateSel = $('#advisorState');
  const districtSel = $('#advisorDistrict');
  if (stateSel) {
    populateStateDropdown(stateSel);
    stateSel.addEventListener('change', () => populateDistrictDropdown(districtSel, stateSel.value));
  }
  const sendBtn = $('#advisorSend');
  const input = $('#advisorInput');
  const sendAction = () => {
    const msg = input.value.trim();
    if (!msg) return;
    sendAdvisorMessage(msg, stateSel?.value, districtSel?.value);
    input.value = '';
  };
  sendBtn.addEventListener('click', sendAction);
  input.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendAction(); });

  $$('.advisor-suggested button').forEach(btn => {
    btn.addEventListener('click', () => {
      input.value = btn.textContent;
      sendAction();
    });
  });
}

/* ==========================================================================
   Floating Advisor (every page)
   ========================================================================== */
function initFloatingAdvisor() {
  const fab = $('#advisorFab');
  const panel = $('#advisorPanel');
  if (!fab || !panel) return;
  fab.addEventListener('click', () => panel.classList.toggle('show'));
  $('#advisorClose')?.addEventListener('click', () => panel.classList.remove('show'));

  const input = $('#advisorInputFab');
  const sendBtn = $('#advisorSendFab');
  const sendAction = () => {
    const msg = input.value.trim();
    if (!msg) return;
    sendFloatingAdvisorMessage(msg);
    input.value = '';
  };
  sendBtn.addEventListener('click', sendAction);
  input.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendAction(); });
}

function appendAdvisorMessage(container, role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  // Render simple **bold** markdown
  div.innerHTML = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

async function sendAdvisorMessage(msg, state, district) {
  const messages = $('#advisorMessages');
  appendAdvisorMessage(messages, 'user', msg);
  const typing = appendAdvisorMessage(messages, 'bot typing', 'Thinking…');
  try {
    const r = await fetch(API.advisor, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, state, district }),
    });
    const j = await r.json();
    typing.remove();
    appendAdvisorMessage(messages, 'bot', j.answer || 'Sorry, I could not answer that.');
    // If the advisor detected a different district, offer to load it
    if (j.detected_districts && j.detected_districts.length) {
      showDetectedDistrictPrompt(messages, j.detected_districts);
    }
  } catch(e) {
    typing.remove();
    appendAdvisorMessage(messages, 'bot', 'Connection error — please retry.');
  }
}

async function sendFloatingAdvisorMessage(msg) {
  const messages = $('#advisorMessagesFab');
  appendAdvisorMessage(messages, 'user', msg);
  const typing = appendAdvisorMessage(messages, 'bot typing', 'Thinking…');
  try {
    const r = await fetch(API.advisor, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, state: currentProfile?.state, district: currentProfile?.district }),
    });
    const j = await r.json();
    typing.remove();
    appendAdvisorMessage(messages, 'bot', j.answer || 'Sorry, I could not answer that.');
    // If the advisor detected a different district, offer to load it
    if (j.detected_districts && j.detected_districts.length) {
      showDetectedDistrictPrompt(messages, j.detected_districts);
    }
    // Update context label
    const ctx = $('#advisorCtxFab');
    if (ctx) {
      ctx.textContent = currentProfile ? `Context: ${currentProfile.district}, ${currentProfile.state}` : 'No district selected';
    }
  } catch(e) {
    typing.remove();
    appendAdvisorMessage(messages, 'bot', 'Connection error — please retry.');
  }
}

/* Show a small "click to load this district" prompt under the bot's reply */
function showDetectedDistrictPrompt(messagesEl, detected) {
  // Filter out the currently selected district
  const filtered = detected.filter(d => {
    if (!currentProfile) return true;
    return !(d.state === currentProfile.state && d.district === currentProfile.district);
  });
  if (!filtered.length) return;
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.style.background = 'rgba(34, 197, 94, 0.08)';
  div.style.borderColor = 'rgba(34, 197, 94, 0.3)';
  const district = filtered[0];
  div.innerHTML = `💡 Want to see the full profile for <strong>${district.district}</strong>? ` +
    `<a href="#" data-state="${district.state}" data-district="${district.district}" ` +
    `style="color:#22c55e;text-decoration:underline;cursor:pointer;">Click to load it</a>`;
  messagesEl.appendChild(div);
  // Wire the click handler
  const link = div.querySelector('a');
  link.addEventListener('click', (e) => {
    e.preventDefault();
    // If we're on the home page (has profileSection), load the profile inline
    if (document.getElementById('profileSection')) {
      loadDistrictProfile(district.state, district.district);
      // Sync the dropdowns on the home page
      const stateSel = document.getElementById('stateSelect');
      if (stateSel) {
        stateSel.value = district.state;
        stateSel.dispatchEvent(new Event('change'));
        setTimeout(() => {
          const dSel = document.getElementById('districtSelect');
          if (dSel) dSel.value = district.district;
        }, 150);
      }
    } else {
      // On the advisor page or compare page — navigate to home with the district
      window.location.href = '/#' + encodeURIComponent(district.state) + '/' + encodeURIComponent(district.district);
    }
  });
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// expose for inline onclick handlers
window.loadDistrictProfile = loadDistrictProfile;
