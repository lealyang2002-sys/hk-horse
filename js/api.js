'use strict';
/**
 * CMHK VIP — Frontend API Client
 * Replaces the hardcoded DEFAULT_RACES / localStorage approach.
 * All pages call these functions instead of directly using data.js globals.
 *
 * Falls back to data.js sample data if the backend is unreachable
 * (useful during local development without the Flask server running).
 */

// ---- Config ---------------------------------------------------------
const API_BASE   = '';               // same origin (Flask serves HTML + API)
const CACHE_TTL  = 5 * 60 * 1000;   // 5 min client-side cache

// ---- In-memory page cache -------------------------------------------
const _cache = {};

function _cacheGet(key) {
  const item = _cache[key];
  if (!item) return null;
  if (Date.now() - item.ts > CACHE_TTL) { delete _cache[key]; return null; }
  return item.data;
}
function _cacheSet(key, data) {
  _cache[key] = { ts: Date.now(), data };
  return data;
}

// ---- Low-level fetch ------------------------------------------------
async function _apiFetch(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

// ---- Public API -----------------------------------------------------

/**
 * Get race day metadata (venue, date, weather, etc.)
 * Returns DEFAULT_RACE_DAY from data.js as fallback.
 */
async function apiGetRaceDay() {
  const key = 'raceday';
  const hit = _cacheGet(key);
  if (hit) return hit;
  try {
    const data = await _apiFetch('/api/raceday');
    if (data && data.date) _cacheSet(key, data);
    return data;
  } catch (_) {
    console.warn('[API] /api/raceday failed, using sample data');
    return DEFAULT_RACE_DAY;
  }
}

/**
 * Get summary list of all races (no horse detail).
 */
async function apiGetRaces() {
  const key = 'races';
  const hit = _cacheGet(key);
  if (hit) return hit;
  try {
    const data = await _apiFetch('/api/races');
    // Don't cache empty results — server may still be fetching
    if (data && data.length > 0) _cacheSet(key, data);
    return data;
  } catch (_) {
    console.warn('[API] /api/races failed, using sample data');
    return DEFAULT_RACES.map(r => ({
      id: r.id, name: r.name, nameEn: r.nameEn,
      time: r.time, grade: r.grade, gradeEn: r.gradeEn,
      distance: r.distance, trackType: r.trackType,
      condition: r.condition, prize: r.prize,
      ratingRange: r.ratingRange,
      totalRunners: r.horses?.length || r.totalRunners || 0,
    }));
  }
}

/**
 * Get full race detail including all horses.
 */
async function apiGetRace(id) {
  const key = `race_${id}`;
  const hit = _cacheGet(key);
  if (hit) return hit;
  try {
    const data = await _apiFetch(`/api/race/${id}`);
    return _cacheSet(key, data);
  } catch (_) {
    console.warn(`[API] /api/race/${id} failed, using sample data`);
    return DEFAULT_RACES.find(r => r.id === +id) || null;
  }
}

/**
 * Trigger a server-side data refresh.
 * @param {string|null} raceDate  "YYYY-MM-DD" or null for auto
 * @param {string|null} venue     "ST" | "HV" or null for auto
 */
async function apiTriggerFetch(raceDate = null, venue = null) {
  const data = await _apiFetch('/api/fetch', {
    method: 'POST',
    body: JSON.stringify({ date: raceDate, venue }),
  });
  // Clear all caches so next read is fresh
  Object.keys(_cache).forEach(k => delete _cache[k]);
  return data;
}

/**
 * Get server status (last fetch time, errors, etc.)
 */
async function apiGetStatus() {
  return _apiFetch('/api/status');
}

/**
 * Save horse data overrides to the server (replaces PUT /api/admin/race/:id/horses)
 */
async function apiSaveHorses(raceId, horses) {
  return _apiFetch(`/api/admin/race/${raceId}/horses`, {
    method: 'PUT',
    body: JSON.stringify(horses),
  });
}

// ---- Compatibility shim (old synchronous API → async) ---------------
// Pages that used to call getRaceDay() / getAllRaces() / getRace(id)
// can now call the async versions. But we keep the synchronous stubs
// pointing at sample data so pages still work if loaded without the server.

function getRaceDayMeta()   { return DEFAULT_RACE_DAY; }
function getAllRaces()       { return DEFAULT_RACES; }
function getRace(id)        { return DEFAULT_RACES.find(r => r.id === +id) || null; }

/**
 * Helper: init a page with live API data, then re-render.
 * Usage: initWithAPI(renderFn)  — renderFn receives (meta, races)
 */
async function initWithAPI(renderFn) {
  try {
    const [meta, races] = await Promise.all([apiGetRaceDay(), apiGetRaces()]);
    renderFn(meta, races);
  } catch (e) {
    console.error('[API] initWithAPI failed:', e);
    renderFn(DEFAULT_RACE_DAY, DEFAULT_RACES);
  }
}

/**
 * Helper: init a race detail page.
 * renderFn receives the full race object.
 */
async function initRaceWithAPI(id, renderFn) {
  try {
    const race = await apiGetRace(id);
    if (race) renderFn(race);
  } catch (e) {
    console.error('[API] initRaceWithAPI failed:', e);
    const fallback = DEFAULT_RACES.find(r => r.id === +id);
    if (fallback) renderFn(fallback);
  }
}
