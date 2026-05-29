'use strict';
// ============================================================
// CMHK VIP Race Intelligence System — Data Layer
// ============================================================

const AUTH_USERS = [
  { username: 'admin', password: 'cmhkvip2026', role: 'admin',  name: '系統管理員' },
  { username: 'vip',   password: 'vip888',       role: 'viewer', name: 'VIP 操作員'  },
];

// Jockey performance tier (0-100)
const JOCKEY_RATING = {
  '莫雷拉': 96, '布文': 92, '田泰安': 90, '霍宏聲': 86, '潘頓': 84,
  '艾光禧': 81, '奧賢民': 78, '布浩榮': 75, '楊明綸': 73,
  '黃智弘(-3)': 72, '袁幸亮(-10)': 71, '巴度': 70, '黃寶妮(-7)': 68,
  '鐘易禧(-2)': 70, '何澤堯': 71, '巫顯東(-2)': 68, '周俊樂(-2)': 67, '潘明輝': 65,
};

// Trainer performance tier (0-100)
const TRAINER_RATING = {
  '告東尼': 96, '方嘉柏': 93, '葉楚航': 91, '文家良': 88, '蔡約翰': 86,
  '游逢榮': 83, '姚本輝': 81, '桂福特': 79, '伍鵬志': 76, '徐雨石': 75,
  '蘇偉賢': 73, '丁冠豪': 72, '大衛希斯': 70, '鄭俊偉': 68,
  '呂健威': 72, '沈集成': 70, '賀賢': 69,
};

// ============================================================
// Race Day Meta
// ============================================================
const DEFAULT_RACE_DAY = {
  date:           '2026-05-06',
  dayOfWeek:      '星期三',
  venue:          '沙田',
  venueEn:        'Sha Tin',
  venueCode:      'ST',
  weather:        '多雲',
  weatherEn:      'Cloudy',
  trackCondition: '濕慢地',
  trackConditionEn: 'Wet Slow',
  firstRaceTime:  '18:45',
  totalRaces:     9,
  updated:        '05/05/2026 18:30',
};

// ============================================================
// Race 1 — 桂花讓賽 (Full Data from HKJC, 2026-05-06 沙田)
// ============================================================
const R1_HORSES = [
  { no:1,  name:'光輝歲月', nameEn:'Glorious Days',     gate:7,  weight:135, jockey:'霍宏聲',      trainer:'游逢榮',   rating:40, ratingDiff:0,  bodyWeight:1121, priority:'+1', gear:'B/TT',             recentForm:[4,1,8,4,7,7],     winOdds:36,  placeOdds:9.5  },
  { no:2,  name:'君智盛',   nameEn:'Chun Chi Sing',    gate:6,  weight:134, jockey:'潘頓',        trainer:'姚本輝',  rating:39, ratingDiff:-2, bodyWeight:1128, priority:'+1', gear:'CP/XB',            recentForm:[10,6,3,4,3,4],    winOdds:8.5, placeOdds:2.8  },
  { no:3,  name:'歡樂老撻', nameEn:'Happy Old Buck',   gate:11, weight:131, jockey:'艾光禧',      trainer:'桂福特',  rating:36, ratingDiff:-2, bodyWeight:1035, priority:'+1', gear:'TT',               recentForm:[7,11,9,14,11,7],  winOdds:45,  placeOdds:12.0 },
  { no:4,  name:'十力',     nameEn:'Ten Power',        gate:3,  weight:131, jockey:'奧賢民',      trainer:'伍鵬志',  rating:36, ratingDiff:-2, bodyWeight:1127, priority:'1',  gear:'B2/TT',            recentForm:[8,5,12,10,7,12],  winOdds:22,  placeOdds:6.5  },
  { no:5,  name:'閃耀威龍', nameEn:'Dazzling Dragon',  gate:10, weight:131, jockey:'袁幸亮(-10)', trainer:'文家良',  rating:36, ratingDiff:-2, bodyWeight:1101, priority:'1',  gear:'B/TT',             recentForm:[9,12,13,8,5,3],   winOdds:18,  placeOdds:5.5  },
  { no:6,  name:'幸運傳承', nameEn:'Lucky Legacy',     gate:12, weight:130, jockey:'莫雷拉',      trainer:'方嘉柏',  rating:35, ratingDiff:0,  bodyWeight:1065, priority:'+1', gear:'B',                recentForm:[7,10,1,7,11,1],   winOdds:5.5, placeOdds:1.9  },
  { no:7,  name:'歷陸大將', nameEn:'Land General',     gate:9,  weight:129, jockey:'布浩榮',      trainer:'徐雨石',  rating:34, ratingDiff:-2, bodyWeight:1047, priority:'1',  gear:'P1/TT',            recentForm:[8,8,7,7,2,1],     winOdds:6.0, placeOdds:2.1  },
  { no:8,  name:'還來勇士', nameEn:'Come Back Hero',   gate:5,  weight:129, jockey:'黃智弘(-3)',  trainer:'葉楚航',  rating:34, ratingDiff:-3, bodyWeight:1115, priority:'1',  gear:'B-/XB-/CP2/TT-',  recentForm:[12,12,10,10,11,11],winOdds:55, placeOdds:14.0 },
  { no:9,  name:'大利好運', nameEn:'Great Fortune',    gate:2,  weight:128, jockey:'布文',        trainer:'蔡約翰',  rating:33, ratingDiff:0,  bodyWeight:1101, priority:'1',  gear:'E/PC/TT',          recentForm:[5,2,2,5,9,11],    winOdds:9.0, placeOdds:3.0  },
  { no:10, name:'一鹿歡騰', nameEn:'Joyful Deer',      gate:1,  weight:125, jockey:'鐘易禧(-2)',  trainer:'告東尼',  rating:30, ratingDiff:-3, bodyWeight:1099, priority:'1',  gear:'V/TT',             recentForm:[13,11,9,7,13,2],  winOdds:28,  placeOdds:8.0  },
  { no:11, name:'上市魅力', nameEn:'Market Charm',     gate:4,  weight:121, jockey:'田泰安',      trainer:'蘇偉賢',  rating:26, ratingDiff:0,  bodyWeight:1120, priority:'+1', gear:'PC/TT',            recentForm:[5,1,10,4,6,5],    winOdds:7.5, placeOdds:2.5  },
  { no:12, name:'幻影旋風', nameEn:'Phantom Typhoon',  gate:8,  weight:119, jockey:'巴度',        trainer:'丁冠豪',  rating:24, ratingDiff:-2, bodyWeight:1093, priority:'*1', gear:'V',                recentForm:[8,4,2,5,3,10],    winOdds:12,  placeOdds:4.0  },
  { no:13, name:'東方魅影', nameEn:'Eastern Shadow',   gate:13, weight:118, jockey:'黃寶妮(-7)',  trainer:'大衛希斯',rating:23, ratingDiff:-2, bodyWeight:1059, priority:'*1', gear:'B/TT',             recentForm:[8,9,5,2,9,6],     winOdds:33,  placeOdds:9.0  },
  { no:14, name:'樂曜心機', nameEn:'Lucky Schemer',    gate:14, weight:115, jockey:'楊明綸',      trainer:'鄭俊偉',  rating:15, ratingDiff:-1, bodyWeight:1099, priority:'+1', gear:'-',                recentForm:[11,9,3,4,10,11],  winOdds:42,  placeOdds:11.0 },
];

const R1_RESERVES = [
  { no:1, name:'香港精神', bodyWeight:1073, weight:131, rating:36, recentForm:[10,10,1,2,6,1], trainer:'葉楚航', priority:2, gear:'B/TT'     },
  { no:2, name:'神煤金剛', bodyWeight:1148, weight:127, rating:32, recentForm:[8,9,10,5,10,14], trainer:'葉楚航', priority:3, gear:'CP2/TT'  },
];

// ============================================================
// Race 2 — 茉莉花讓賽 (Full Data)
// ============================================================
const R2_HORSES = [
  { no:1,  name:'贏得威楓', nameEn:'Win The Wind',      gate:1,  weight:133, jockey:'霍宏聲',      trainer:'告東尼',  rating:58, ratingDiff:0,  bodyWeight:1105, priority:'1',  gear:'B/TT',  recentForm:[3,1,2,4,3,1],    winOdds:36,  placeOdds:9.5 },
  { no:2,  name:'星火燎原', nameEn:'Blazing Star',       gate:10, weight:134, jockey:'袁幸亮(-10)', trainer:'徐雨石',  rating:59, ratingDiff:-2, bodyWeight:1134, priority:'1',  gear:'B/TT',  recentForm:[2,1,3,5,2,4],    winOdds:5.7, placeOdds:1.5 },
  { no:3,  name:'巧眼光',   nameEn:'Smart Eyes',         gate:9,  weight:131, jockey:'田泰安',      trainer:'蔡約翰',  rating:56, ratingDiff:0,  bodyWeight:1098, priority:'+1', gear:'TT',    recentForm:[5,3,1,8,4,2],    winOdds:13,  placeOdds:4.4 },
  { no:4,  name:'快樂神駒', nameEn:'Happy Steed',        gate:12, weight:128, jockey:'莫雷拉',      trainer:'方嘉柏',  rating:53, ratingDiff:-1, bodyWeight:1087, priority:'+1', gear:'B',     recentForm:[1,4,3,6,2,5],    winOdds:6.2, placeOdds:2.5 },
  { no:5,  name:'鉛主角',   nameEn:'Lead Star',          gate:7,  weight:127, jockey:'楊明綸',      trainer:'大衛希斯',rating:52, ratingDiff:0,  bodyWeight:1076, priority:'1',  gear:'P1/TT', recentForm:[3,6,4,7,1,9],    winOdds:9.7, placeOdds:2.4 },
  { no:6,  name:'文明戰士', nameEn:'Civilised Fighter',  gate:6,  weight:127, jockey:'布文',        trainer:'葉楚航',  rating:52, ratingDiff:-2, bodyWeight:1068, priority:'1',  gear:'B/TT',  recentForm:[7,2,5,3,8,1],    winOdds:7.0, placeOdds:3.4 },
  { no:7,  name:'起舞奏樂', nameEn:'Dance And Play',     gate:5,  weight:126, jockey:'艾光禧',      trainer:'文家良',  rating:51, ratingDiff:0,  bodyWeight:1055, priority:'+1', gear:'TT',    recentForm:[2,1,4,3,2,1],    winOdds:4.1, placeOdds:1.5 },
  { no:8,  name:'精彩勇將', nameEn:'Great Warrior',      gate:8,  weight:124, jockey:'巴度',        trainer:'丁冠豪',  rating:49, ratingDiff:-1, bodyWeight:1042, priority:'1',  gear:'V/TT',  recentForm:[6,8,3,10,5,7],   winOdds:10,  placeOdds:4.4 },
  { no:9,  name:'尚旋',     nameEn:'Shang Xuan',         gate:1,  weight:123, jockey:'何澤堯',      trainer:'呂健威',  rating:48, ratingDiff:0,  bodyWeight:1038, priority:'1',  gear:'B/TT',  recentForm:[9,4,7,2,11,6],   winOdds:28,  placeOdds:7.7 },
  { no:10, name:'喜樂之星', nameEn:'Joy Star',           gate:11, weight:121, jockey:'巫顯東(-2)',  trainer:'沈集成',  rating:46, ratingDiff:-2, bodyWeight:1024, priority:'1',  gear:'B/TT',  recentForm:[11,7,9,12,8,10], winOdds:24,  placeOdds:6.3 },
  { no:11, name:'精算奕然', nameEn:'Smart Calculator',   gate:3,  weight:121, jockey:'周俊樂(-2)',  trainer:'鄭俊偉',  rating:46, ratingDiff:-1, bodyWeight:1018, priority:'1',  gear:'TT',    recentForm:[12,10,8,13,9,11],winOdds:44,  placeOdds:9.8 },
  { no:12, name:'翠湖烈鳳', nameEn:'Jade Phoenix',       gate:2,  weight:117, jockey:'潘明輝',      trainer:'賀賢',    rating:42, ratingDiff:0,  bodyWeight:1009, priority:'1',  gear:'B/TT',  recentForm:[8,5,11,4,7,3],   winOdds:10,  placeOdds:3.6 },
];

// ============================================================
// All Races
// ============================================================
const DEFAULT_RACES = [
  {
    id: 1, name: '桂花讓賽',   nameEn: 'Osmanthus Handicap',     time: '18:45',
    grade: '第五班', gradeEn: 'Class 5', distance: 1650,
    trackType: '全天候跑道', trackTypeEn: 'AWT',
    condition: '濕慢地', conditionEn: 'Wet Slow',
    prize: 875000, ratingRange: '40-0', totalRunners: 14,
    horses: R1_HORSES, reserves: R1_RESERVES,
  },
  {
    id: 2, name: '茉莉花讓賽', nameEn: 'Jasmine Handicap',       time: '19:15',
    grade: '第四班', gradeEn: 'Class 4', distance: 1200,
    trackType: '全天候跑道', trackTypeEn: 'AWT',
    condition: '濕慢地', conditionEn: 'Wet Slow',
    prize: 1000000, ratingRange: '60-40', totalRunners: 12,
    horses: R2_HORSES, reserves: [],
  },
  { id: 3, name: '玫瑰讓賽',   nameEn: 'Rose Handicap',          time: '19:45', grade: '第三班', gradeEn: 'Class 3', distance: 1200, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1250000, ratingRange: '80-60', totalRunners: 10, horses: [], reserves: [] },
  { id: 4, name: '薰衣草讓賽', nameEn: 'Lavender Handicap',      time: '20:15', grade: '第三班', gradeEn: 'Class 3', distance: 1400, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1250000, ratingRange: '80-60', totalRunners: 11, horses: [], reserves: [] },
  { id: 5, name: '水仙讓賽',   nameEn: 'Narcissus Handicap',     time: '20:50', grade: '第二班', gradeEn: 'Class 2', distance: 1600, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1600000, ratingRange: '100-80', totalRunners: 9, horses: [], reserves: [] },
  { id: 6, name: '紫荊讓賽',   nameEn: 'Bauhinia Handicap',      time: '21:20', grade: '第三班', gradeEn: 'Class 3', distance: 1400, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1250000, ratingRange: '80-60', totalRunners: 12, horses: [], reserves: [] },
  { id: 7, name: '荷花讓賽',   nameEn: 'Lotus Handicap',         time: '21:50', grade: '第四班', gradeEn: 'Class 4', distance: 1650, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1000000, ratingRange: '60-40', totalRunners: 10, horses: [], reserves: [] },
  { id: 8, name: '蘭花讓賽',   nameEn: 'Orchid Handicap',        time: '22:20', grade: '第四班', gradeEn: 'Class 4', distance: 1200, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 1000000, ratingRange: '60-40', totalRunners: 11, horses: [], reserves: [] },
  { id: 9, name: '菊花讓賽',   nameEn: 'Chrysanthemum Handicap', time: '22:55', grade: '第五班', gradeEn: 'Class 5', distance: 2000, trackType: '全天候跑道', trackTypeEn: 'AWT', condition: '濕慢地', conditionEn: 'Wet Slow', prize: 875000, ratingRange: '40-0', totalRunners: 9, horses: [], reserves: [] },
];

// ============================================================
// Scoring Engine
// ============================================================
function calcFormScore(form) {
  if (!form || form.length === 0) return 50;
  const weights = [3, 2.5, 2, 1.5, 1, 1];
  let totalScore = 0, totalWeight = 0;
  form.slice(0, 6).forEach((pos, i) => {
    const w = weights[i] || 1;
    const s = pos === 1 ? 100 : pos === 2 ? 88 : pos === 3 ? 76 :
              pos === 4 ? 62 : pos === 5 ? 48 : Math.max(5, 60 - pos * 5);
    totalScore += s * w; totalWeight += w;
  });
  return Math.round(totalScore / totalWeight);
}

function calcHorseScore(horse, allHorses) {
  const maxRating  = Math.max(...allHorses.map(h => h.rating), 1);
  const ratingScore  = Math.round((horse.rating / maxRating) * 100);
  const formScore    = calcFormScore(horse.recentForm);
  const jockeyScore  = JOCKEY_RATING[horse.jockey]  || 65;
  const trainerScore = TRAINER_RATING[horse.trainer] || 65;
  const gateScore    = Math.max(40, 100 - Math.abs(horse.gate - 4) * 4);
  return Math.min(99, Math.max(10, Math.round(
    formScore    * 0.35 +
    ratingScore  * 0.25 +
    jockeyScore  * 0.22 +
    trainerScore * 0.10 +
    gateScore    * 0.08
  )));
}

function calcHorseRadar(horse, allHorses) {
  const maxRating = Math.max(...allHorses.map(h => h.rating), 1);
  return {
    '近期狀態':   calcFormScore(horse.recentForm),
    '賽事評分':   Math.round((horse.rating / maxRating) * 100),
    '騎師評級':   Math.round(((JOCKEY_RATING[horse.jockey]  || 65) / 96) * 100),
    '訓練師評級': Math.round(((TRAINER_RATING[horse.trainer] || 65) / 96) * 100),
    '檔位優勢':   Math.max(40, 100 - Math.abs(horse.gate - 4) * 4),
    '負磅輕重':   Math.min(100, Math.max(30, 100 - (horse.weight - 115) * 2.5)),
  };
}

function generateAIText(horse, race, allHorses) {
  const score  = calcHorseScore(horse, allHorses);
  const jScore = JOCKEY_RATING[horse.jockey]  || 65;
  const tScore = TRAINER_RATING[horse.trainer] || 65;
  const form   = horse.recentForm || [];
  const recentStr = form.slice(0, 3).join('-');

  const formVerdict  = form[0] <= 2 ? '近況極佳' : form[0] <= 4 ? '近況不俗' : form[0] <= 6 ? '狀態一般' : '近況欠佳';
  const jockeyTier   = jScore >= 90 ? '一線名師' : jScore >= 80 ? '實力騎師' : '中堅騎師';
  const trainerTier  = tScore >= 90 ? '頂級訓練師' : tScore >= 80 ? '資深訓練師' : '中堅訓練師';
  const gateComment  = horse.gate <= 3 ? '內圍位置理想' : horse.gate <= 7 ? '中圍位置均衡' : horse.gate <= 10 ? '外圍稍遜' : '外圍劣勢明顯';
  const weightComment = horse.weight <= 120 ? '磅重輕盈，衝刺有力' : horse.weight <= 127 ? '磅重適中，均衡發揮' : '磅重偏高，體力消耗較大';

  let verdict, tag, tagClass;
  if      (score >= 78) { verdict = '強力推介'; tag = '強烈推薦'; tagClass = 'border-trading-up text-trading-up'; }
  else if (score >= 65) { verdict = '值得留意'; tag = '值得留意'; tagClass = 'border-primary-container text-primary-container'; }
  else if (score >= 50) { verdict = '冷門機會'; tag = '冷門機會'; tagClass = 'border-outline text-on-surface-variant'; }
  else                  { verdict = '觀望';     tag = '觀望';     tagClass = 'border-muted text-muted'; }

  const strengths = [
    form[0] <= 2 ? `近戰成績${recentStr}，佳績連連` : null,
    jScore >= 90 ? `一線騎師${horse.jockey}操刀` : null,
    tScore >= 90 ? `名廄${horse.trainer}調教` : null,
    horse.gate <= 3 ? `內圍第${horse.gate}檔起閘` : null,
    horse.weight <= 120 ? `輕磅${horse.weight}磅優勢` : null,
    horse.ratingDiff > 0 ? '評分近期上升' : null,
  ].filter(Boolean);

  const weaknesses = [
    form[0] >= 8 ? `近況低迷，最近一場第${form[0]}` : null,
    horse.gate >= 11 ? `外圍第${horse.gate}檔劣勢` : null,
    horse.weight >= 130 ? `重磅${horse.weight}磅消耗大` : null,
    horse.ratingDiff <= -3 ? '評分連續下調，波動偏大' : null,
  ].filter(Boolean);

  return {
    score, verdict, tag, tagClass,
    text: `${horse.name}近三場成績 ${recentStr}，${formVerdict}。` +
          `由${jockeyTier}${horse.jockey}上陣，受${trainerTier}${horse.trainer}調教。` +
          `起閘第${horse.gate}檔，${gateComment}。${weightComment}。` +
          `本場全天候跑道${race.condition}，綜合評估：${verdict}。`,
    strengths: strengths.length ? strengths : ['資料完整後可生成分析'],
    weaknesses: weaknesses.length ? weaknesses : ['暫無明顯弱點'],
  };
}
