'use strict';
// ============================================================
// CMHK VIP Race Intelligence System — App Utilities
// ============================================================

const STORAGE_KEY  = 'cmhk_race_data';
const AUTH_KEY     = 'cmhk_auth_user';

// ---- Auth -------------------------------------------------------
function login(username, password) {
  const user = AUTH_USERS.find(u => u.username === username && u.password === password);
  if (user) {
    sessionStorage.setItem(AUTH_KEY, JSON.stringify({ username: user.username, role: user.role, name: user.name }));
    return user;
  }
  return null;
}

function logout() {
  sessionStorage.removeItem(AUTH_KEY);
  window.location.href = 'login.html';
}

function getCurrentUser() {
  const raw = sessionStorage.getItem(AUTH_KEY);
  return raw ? JSON.parse(raw) : null;
}

function isAuthenticated() {
  return !!getCurrentUser();
}

function requireAuth() {
  if (!isAuthenticated()) window.location.href = 'login.html';
}

function requireAdmin() {
  requireAuth();
  if (getCurrentUser().role !== 'admin') window.location.href = 'index.html';
}

// ---- Data Management --------------------------------------------
function saveRaceDay(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function loadRaceDay() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try { return JSON.parse(raw); } catch (_) {}
  }
  return { meta: DEFAULT_RACE_DAY, races: DEFAULT_RACES };
}

function getRaceDayMeta() { return loadRaceDay().meta; }

function getAllRaces()     { return loadRaceDay().races; }

function getRace(id) {
  return getAllRaces().find(r => r.id === +id) || null;
}

function saveHorseData(raceId, horses) {
  const data = loadRaceDay();
  const race = data.races.find(r => r.id === +raceId);
  if (race) { race.horses = horses; saveRaceDay(data); }
}

function saveRaceMeta(raceId, meta) {
  const data = loadRaceDay();
  const race = data.races.find(r => r.id === +raceId);
  if (race) { Object.assign(race, meta); saveRaceDay(data); }
}

// ---- URL Helpers ------------------------------------------------
function getUrlParam(key) {
  return new URLSearchParams(window.location.search).get(key);
}

function goToRace(id) {
  window.location.href = `race.html?id=${id}`;
}

function goToAnalysis(id) {
  window.location.href = `analysis.html?id=${id}`;
}

// ---- Formatting ------------------------------------------------
function formatOdds(v) {
  if (v == null) return '—';
  return Number(v).toFixed(1);
}

function formatCurrency(v) {
  return '$' + Number(v).toLocaleString();
}

function formBadge(pos) {
  if (pos === 1) return '<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-trading-up text-ink text-[10px] font-bold">1</span>';
  if (pos === 2) return '<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary-container text-ink text-[10px] font-bold">2</span>';
  if (pos === 3) return '<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-secondary text-ink text-[10px] font-bold">3</span>';
  return `<span class="inline-flex items-center justify-center w-5 h-5 rounded bg-surface-elevated-dark text-muted text-[10px]">${pos}</span>`;
}

function gradeColor(grade) {
  const g = grade.replace('第', '').replace('班', '');
  if (g === '一' || g === '1') return 'text-trading-down';
  if (g === '二' || g === '2') return 'text-[#ff9f1c]';
  if (g === '三' || g === '3') return 'text-primary-container';
  return 'text-muted';
}

function scoreColor(score) {
  if (score >= 78) return 'text-trading-up';
  if (score >= 65) return 'text-primary-container';
  if (score >= 50) return 'text-on-surface';
  return 'text-muted';
}

function scoreBar(score) {
  const color = score >= 78 ? 'bg-trading-up' : score >= 65 ? 'bg-primary-container' : score >= 50 ? 'bg-outline' : 'bg-surface-elevated-dark';
  return `<div class="w-full bg-canvas-dark rounded-full h-1.5"><div class="${color} h-1.5 rounded-full transition-all" style="width:${score}%"></div></div>`;
}

// ---- Sidebar Active State ---------------------------------------
function activateSidebarLink() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('[data-nav]').forEach(el => {
    const href = el.getAttribute('data-nav');
    if (href === path) {
      el.classList.add('bg-[#2b3139]', 'text-[#FCD535]', 'border-l-4', 'border-[#FCD535]');
      el.classList.remove('text-gray-500', 'hover:text-gray-200');
    }
  });
}

// ---- Countdown Timer -------------------------------------------
function startCountdown(targetTime, elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  function tick() {
    const now  = new Date();
    const [h, m] = targetTime.split(':').map(Number);
    const target = new Date(now);
    target.setHours(h, m, 0, 0);
    if (target < now) target.setDate(target.getDate() + 1);
    const diff = Math.max(0, target - now);
    const hh = String(Math.floor(diff / 3600000)).padStart(2, '0');
    const mm = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0');
    const ss = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0');
    el.textContent = `${hh}:${mm}:${ss}`;
  }
  tick(); setInterval(tick, 1000);
}

// ---- On-page init helper ----------------------------------------
function initPage(requireAdminRole) {
  if (requireAdminRole) requireAdmin(); else requireAuth();
  activateSidebarLink();
  const user = getCurrentUser();
  const nameEls = document.querySelectorAll('[data-user-name]');
  const roleEls = document.querySelectorAll('[data-user-role]');
  nameEls.forEach(el => el.textContent = user.name);
  roleEls.forEach(el => el.textContent = user.role === 'admin' ? '管理員' : 'VIP 操作員');
  // Hide admin sidebar link for non-admin users
  if (user.role !== 'admin') {
    document.querySelectorAll('[data-nav="admin.html"]').forEach(el => el.style.display = 'none');
  }
}
