"""
HKJC public data fetcher — Playwright / DOM edition.

The race card page at racing.hkjc.com/zh-hk/local/information/racecard is
server-rendered HTML (ASP.NET). Playwright loads it, then we extract the
horse table from the DOM.

Setup (once):
    pip install playwright && playwright install chromium
"""

import json
import os
import re
from datetime import datetime, date, timedelta

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("[Fetcher] WARNING: playwright not installed.\n"
          "  Run: pip install playwright && playwright install chromium")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")

# Default race times for a standard ST/HV evening meeting
_RACE_TIMES_DEFAULT = [
    "18:45", "19:15", "19:45", "20:15", "20:50",
    "21:20", "21:50", "22:20", "22:55",
]

# The page route — params: racedate=YYYY/MM/DD  Racecourse=ST|HV  RaceNo=N
RACECARD_URL = "https://racing.hkjc.com/zh-hk/local/information/racecard"
GENERALINFO_URL = "https://racing.hkjc.com/contentAsset/api/getGeneralInfo"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Jockey claim allowance pattern, e.g. " (-10)" or " (+3)"
_CLAIM_RE = re.compile(r"\s*\([+-]?\d+\)\s*$")


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _weekday_zh(date_str: str) -> str:
    days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    try:
        return days[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except Exception:
        return ""


def _cache_path(race_date: str, venue: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"races_{race_date}_{venue}.json")


def _int(val) -> int:
    if val is None:
        return 0
    try:
        return int(re.sub(r"[^\d]", "", str(val)) or "0")
    except Exception:
        return 0


def _float_or_none(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(str(val).strip())
        return f if f > 0 else None
    except Exception:
        return None


def _fmt_date(race_date: str) -> str:
    """'2026-05-06'  →  '2026/05/06'  (HKJC URL format)"""
    return race_date.replace("-", "/")


# ------------------------------------------------------------------ #
# Odds fetching via Playwright (HKJC GraphQL requires browser session)
# ------------------------------------------------------------------ #
def _fetch_all_odds(race_date: str, venue: str) -> tuple[dict, dict, dict, dict]:
    """
    Fetch all per-race odds pools via the HKJC Forecast page (/fct/).
    That page's GraphQL responses contain WIN, PLA, QIN, FCT, and TRITop pools.

    Returns:
      win_place : {race_no: {horse_no: {"win": float|None, "place": float|None}}}
      quinella  : {race_no: {"h1,h2": float}}          — h1 < h2 (int-sorted)
      forecast  : {race_no: {"h1,h2": float}}          — ordered: h1=1st, h2=2nd
      tierce    : {race_no: {"h1,h2,h3": float}}       — sorted numerically
    """
    if not HAS_PLAYWRIGHT:
        return {}, {}, {}, {}

    wp:  dict[str, dict] = {}
    qin: dict[str, dict] = {}
    fct: dict[str, dict] = {}
    tri: dict[str, dict] = {}

    def _extract_pools(data: dict):
        meetings = (data.get("data") or {}).get("raceMeetings") or []
        for m in meetings:
            if not m:
                continue
            m_date, m_venue = m.get("date"), m.get("venueCode")
            if m_date and m_date != race_date:
                continue
            if m_venue and m_venue != venue:
                continue
            for pool in (m.get("pmPools") or []):
                ot = pool.get("oddsType")
                race_nos = (pool.get("leg") or {}).get("races") or []
                if not race_nos:
                    continue
                rn = str(race_nos[0])
                nodes = pool.get("oddsNodes") or []

                if ot == "WIN":
                    for node in nodes:
                        raw = node.get("combString") or ""
                        hn = str(int(raw)) if raw.isdigit() else ""
                        odds = _float_or_none(node.get("oddsValue"))
                        if hn and odds:
                            wp.setdefault(rn, {}).setdefault(hn, {"win": None, "place": None})
                            wp[rn][hn]["win"] = odds

                elif ot == "PLA":
                    for node in nodes:
                        raw = node.get("combString") or ""
                        hn = str(int(raw)) if raw.isdigit() else ""
                        odds = _float_or_none(node.get("oddsValue"))
                        if hn and odds:
                            wp.setdefault(rn, {}).setdefault(hn, {"win": None, "place": None})
                            wp[rn][hn]["place"] = odds

                elif ot == "QIN":
                    for node in nodes:
                        parts = (node.get("combString") or "").split(",")
                        if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
                            h1, h2 = sorted(int(p.strip()) for p in parts)
                            odds = _float_or_none(node.get("oddsValue"))
                            if odds:
                                qin.setdefault(rn, {})[f"{h1},{h2}"] = odds

                elif ot == "FCT":
                    for node in nodes:
                        parts = (node.get("combString") or "").split(",")
                        if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
                            h1, h2 = int(parts[0].strip()), int(parts[1].strip())
                            odds = _float_or_none(node.get("oddsValue"))
                            if odds:
                                fct.setdefault(rn, {})[f"{h1},{h2}"] = odds

                elif ot == "TRITop":
                    for node in nodes:
                        parts = (node.get("combString") or "").split(",")
                        if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
                            key = ",".join(str(x) for x in sorted(int(p.strip()) for p in parts))
                            odds = _float_or_none(node.get("oddsValue"))
                            if odds:
                                tri.setdefault(rn, {})[key] = odds

            # Fallback: winOdds on runner objects (usually empty)
            for race in (m.get("races") or []):
                rn = str(race.get("no", ""))
                if not rn:
                    continue
                for runner in (race.get("runners") or []):
                    hn = str(runner.get("no", ""))
                    win = _float_or_none(runner.get("winOdds"))
                    if hn and win:
                        wp.setdefault(rn, {}).setdefault(hn, {"win": None, "place": None})
                        if wp[rn][hn]["win"] is None:
                            wp[rn][hn]["win"] = win

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                locale="zh-TW", user_agent=_UA,
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

            def on_response(response):
                if "info.cld.hkjc.com/graphql" not in response.url:
                    return
                try:
                    _extract_pools(response.json())
                except Exception:
                    pass

            page.on("response", on_response)

            def _visit_pages(path_prefix: str, sentinel: dict, label: str):
                """Navigate through each race URL; stop when no new data arrives."""
                for race_no in range(1, 15):
                    url = f"https://bet.hkjc.com/en/racing/{path_prefix}/{race_date}/{venue}/{race_no}"
                    if race_no == 1:
                        print(f"[Fetcher] {label}: {url} ...")
                    before = len(sentinel)
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(1500)
                    if race_no > 1 and len(sentinel) == before:
                        break

            _visit_pages("wpq", wp,  "WIN+PLA+QIN")   # WIN, PLA, QIN, QPL
            _visit_pages("fct", fct, "FCT")            # FCT (二重彩)
            _visit_pages("tri", tri, "TRITop")         # TRITop (三重彩)

            browser.close()

    except Exception as e:
        print(f"[Fetcher] Odds fetch error: {e}")
        return {}, {}, {}, {}

    print(
        f"[Fetcher] WIN/PLA: {len(wp)} races, {sum(len(v) for v in wp.values())} horses"
        f"  |  QIN: {sum(len(v) for v in qin.values())} combos"
        f"  |  FCT: {sum(len(v) for v in fct.values())} combos"
        f"  |  TRI: {sum(len(v) for v in tri.values())} combos"
    )
    return wp, qin, fct, tri


# ------------------------------------------------------------------ #
# Get next race day from HKJC API (POST, needs no browser)
# ------------------------------------------------------------------ #
def _fetch_generalinfo_json() -> dict | None:
    """Call getGeneralInfo with a browser session so cookies are valid."""
    if not HAS_PLAYWRIGHT:
        return None
    try:
        import requests as _req
        # Attempt direct POST (works when called from a live browser session)
        r = _req.post(GENERALINFO_URL,
                      json={},
                      headers={"User-Agent": _UA,
                               "Referer": "https://racing.hkjc.com/"},
                      timeout=10)
        if r.status_code == 200:
            body = r.json()
            if body.get("data") and body["data"] is not False:
                return body["data"]
    except Exception:
        pass
    return None


def get_upcoming_race_days(from_date: str = None, days_ahead: int = 10) -> list[dict]:
    """
    Return all candidate race days from from_date up to days_ahead days out,
    as a list of {date, venue} dicts ordered nearest-first.

    Tries the HKJC getGeneralInfo API first (authoritative schedule).
    Falls back to a weekday heuristic (Wed=2, Sat=5, Sun=6) when the API
    is unavailable — this may include days HKJC has no meeting scheduled,
    but _do_fetch will skip those via probe.
    """
    start_str = from_date or _today()
    cutoff_str = (datetime.strptime(start_str, "%Y-%m-%d") + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Authoritative: HKJC meeting schedule API
    info = _fetch_generalinfo_json()
    if info and info.get("MeetingInfos"):
        results = [
            {"date": m["MeetingDate"], "venue": m.get("Venue", "ST")}
            for m in sorted(info["MeetingInfos"], key=lambda x: x.get("MeetingDate", ""))
            if start_str <= m.get("MeetingDate", "") <= cutoff_str
        ]
        if results:
            return results

    # Heuristic fallback: Wed=HV, Sat/Sun=ST (standard HKJC pattern)
    RACE_WEEKDAY_VENUE = {2: "HV", 5: "ST", 6: "ST"}
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    return [
        {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
         "venue": RACE_WEEKDAY_VENUE[(start + timedelta(days=i)).weekday()]}
        for i in range(days_ahead + 1)
        if (start + timedelta(days=i)).weekday() in RACE_WEEKDAY_VENUE
    ]


def get_next_race_day(from_date: str = None) -> dict:
    """Return the single nearest upcoming race day. Used by fetch_full_day."""
    results = get_upcoming_race_days(from_date=from_date, days_ahead=14)
    return results[0] if results else {"date": _today(), "venue": "ST"}


def probe_race_day(race_date: str, venue: str = "ST") -> int:
    """
    Quick check: fetch only Race 1 and return its horse count.
    Takes ~7s instead of ~70s for a full day scrape.
    Returns 0 if entries are not yet published or on error.
    """
    if not HAS_PLAYWRIGHT:
        return 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(locale="zh-TW", user_agent=_UA,
                                      viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            r1 = _fetch_one_race(page, race_date, venue, 1)
            browser.close()
        count = len(r1.get("horses", []))
        print(f"[Fetcher] Probe {race_date} {venue}: {count} horses in Race 1")
        return count
    except Exception as e:
        print(f"[Fetcher] Probe error for {race_date}: {e}")
        return 0


# ------------------------------------------------------------------ #
# DOM extraction helpers
# ------------------------------------------------------------------ #
def _parse_recent_form(raw: str) -> list[int]:
    """'4/1/8/4/7/7' or '4-1-8-4-7-7' → [4,1,8,4,7,7]"""
    nums = re.findall(r"\d+", raw)
    return [int(n) for n in nums if int(n) <= 20][:6]


def _clean_jockey(raw: str) -> str:
    return _CLAIM_RE.sub("", raw).strip()


def _parse_priority(raw: str) -> str:
    """'+ 1' → '+1', '1' → '1'"""
    return re.sub(r"\s+", "", raw).replace("+", "+ ")


def _find_horse_table(page):
    """Return the table element that contains the horse runner list."""
    for tbl in page.query_selector_all("table"):
        header = tbl.query_selector("tr:first-child")
        if header and "馬匹編號" in header.inner_text():
            return tbl
    return None


def _extract_horses_from_table(tbl) -> list[dict]:
    """
    Actual column layout for the default HKJC race card table (27 cells/row):
      [0]  馬匹編號   [1]  6次近績   [2]  綵衣(img)  [3]  馬名
      [4]  馬匹編碼   [5]  負磅      [6]  騎師        [7]  (empty)
      [8]  檔位       [9]  練馬師    [10] (dash)       [11] 評分
      [12] 評分+/-    [13] 排位體重  [14] 排位體重+/-  [15] 最佳時間
      [16] 馬齡       [17] (dash)    [18] 性別         [19] 今季獎金
      [20] 優先參賽次序 [21] 讓磅    [22] 配備         [23] 馬主
      [24] 父系       [25] 母系     [26] 進口類別
    """
    horses = []
    rows = tbl.query_selector_all("tr")
    for row in rows[1:]:  # skip header
        cells = row.query_selector_all("td")
        if len(cells) < 10:
            continue
        texts = [c.inner_text().strip() for c in cells]

        no_str = texts[0]
        if not no_str.isdigit():
            continue
        no = int(no_str)
        if not (1 <= no <= 20):
            continue

        def t(i, default=""):
            return texts[i] if len(texts) > i else default

        horses.append({
            "no":          no,
            "name":        t(3) or f"馬{no}",
            "nameEn":      "",
            "jockey":      _clean_jockey(t(6)) or "—",
            "jockeyCode":  "",
            "trainer":     t(9) or "—",
            "trainerCode": "",
            "weight":      _int(t(5)) or 126,
            "gate":        _int(t(8)) or 1,
            "rating":      _int(t(11)),
            "ratingDiff":  _int(t(12)),
            "bodyWeight":  _int(t(13)),
            "priority":    _parse_priority(t(20)) or "1",
            "gear":        t(22),
            "recentForm":  _parse_recent_form(t(1)),
            "winOdds":     None,
            "placeOdds":   None,
        })
    return horses


def _extract_race_meta(page, race_no: int) -> dict:
    """
    Pull race name, distance, class, condition from page HTML.
    The HKJC race card page contains a text block like:
      '第 1 場 - 桂花讓賽'
      '2026年5月6日, 星期三, 沙田, 18:45'
      '全天候跑道, 1650米, 濕慢地'
      '獎金: $875,000, 評分: 40-0, 第五班'
    """
    html = page.content()
    meta = {}

    # Race name: "第 N 場 - 桂花讓賽" pattern
    name_m = re.search(
        r'第\s*' + str(race_no) + r'\s*場\s*[-—]\s*([^<\n\r\t]+)',
        html
    )
    if name_m:
        meta["name"] = name_m.group(1).strip()

    # Distance — "1650米"
    dist_m = re.search(r'(\d{3,4})\s*米', html)
    if dist_m:
        meta["distance"] = int(dist_m.group(1))

    # Condition — text after distance, e.g. "1650米, 濕慢地"
    cond_m = re.search(r'\d{3,4}\s*米[,，\s]+([^\s<,，\n]{2,10})', html)
    if cond_m:
        meta["condition"] = cond_m.group(1).strip()

    # Grade — "第五班" / "第一班"
    grade_m = re.search(r'第([一二三四五六1-6])班', html)
    if grade_m:
        meta["grade"] = f"第{grade_m.group(1)}班"

    # Track type
    if "全天候跑道" in html:
        meta["trackType"] = "全天候跑道"
    elif "草地" in html:
        meta["trackType"] = "草地"

    # Prize — "獎金: $875,000"
    prize_m = re.search(r'獎金[：:]\s*\$?([\d,]+)', html)
    if prize_m:
        meta["prize"] = int(prize_m.group(1).replace(",", ""))

    # Rating range — "評分: 40-0"
    rating_m = re.search(r'評分[：:]\s*([\d]+-[\d]+)', html)
    if rating_m:
        meta["ratingRange"] = rating_m.group(1)

    # Start time — "18:45"
    time_m = re.search(r'(\d{2}:\d{2})', html)
    if time_m:
        meta["time"] = time_m.group(1)

    return meta


# ------------------------------------------------------------------ #
# Core fetch: single race page
# ------------------------------------------------------------------ #
def _fetch_one_race(page, race_date: str, venue: str, race_no: int) -> dict:
    """Navigate to race card page and extract horse data + meta."""
    url = (f"{RACECARD_URL}"
           f"?racedate={_fmt_date(race_date)}&Racecourse={venue}&RaceNo={race_no}")
    try:
        page.goto(url, wait_until="load", timeout=40000)
        page.wait_for_timeout(7000)
    except Exception as e:
        print(f"[Fetcher]   Race {race_no}: navigation error: {e}")

    meta = _extract_race_meta(page, race_no)
    tbl = _find_horse_table(page)
    horses = _extract_horses_from_table(tbl) if tbl else []

    result = {
        "id":          race_no,
        "name":        meta.get("name", f"第{race_no}場讓賽"),
        "nameEn":      "",
        "distance":    meta.get("distance", 1200),
        "grade":       meta.get("grade", "—"),
        "trackType":   meta.get("trackType", "全天候跑道"),
        "condition":   meta.get("condition", "—"),
        "prize":       meta.get("prize", 0),
        "ratingRange": meta.get("ratingRange", "—"),
        "time":        meta.get("time"),
        "horses":      horses,
    }
    print(f"[Fetcher]   Race {race_no}: {len(horses)} horses — {result['name']}")
    return result


def _detect_total_races(page) -> int:
    """Count race tabs from the loaded page."""
    try:
        # The race tab row uses image links like racecard_rt_N.gif
        imgs = page.query_selector_all("img[src*='racecard_rt_']")
        nums = []
        for img in imgs:
            src = img.get_attribute("src") or ""
            m = re.search(r"racecard_rt_(\d+)", src)
            if m:
                nums.append(int(m.group(1)))
        if nums:
            return max(nums)
    except Exception:
        pass
    return 9


# ------------------------------------------------------------------ #
# Main entry
# ------------------------------------------------------------------ #
def fetch_full_day(race_date: str = None, venue: str = None) -> dict:
    """
    Fetch a full race day.  Returns standard { meta, races } envelope.
    """
    if not HAS_PLAYWRIGHT:
        raise RuntimeError(
            "Playwright not installed.\n"
            "  pip install playwright && playwright install chromium"
        )

    if not race_date:
        nd = get_next_race_day()
        race_date = nd["date"]
        venue = venue or nd.get("venue", "ST")

    venue = venue or "ST"
    venue_name = "跑馬地" if venue == "HV" else "沙田"
    print(f"[Fetcher] Target: {race_date} {venue} ({venue_name})")

    races_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(locale="zh-TW", user_agent=_UA,
                                  viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # Load Race 1 — also detect total race count
        r1 = _fetch_one_race(page, race_date, venue, 1)
        total_races = _detect_total_races(page) or 9
        print(f"[Fetcher] Total races: {total_races}")
        races_raw.append(r1)

        for n in range(2, total_races + 1):
            races_raw.append(_fetch_one_race(page, race_date, venue, n))

        browser.close()

    # Merge in all odds pools (WIN/PLA per horse; QIN/FCT/TRI per race)
    wp_map, qin_map, fct_map, tri_map = _fetch_all_odds(race_date, venue)
    if wp_map:
        for race in races_raw:
            rn = str(race["id"])
            race_odds = wp_map.get(rn, {})
            for h in race.get("horses", []):
                ho = race_odds.get(str(h["no"]), {})
                h["winOdds"]   = ho.get("win")
                h["placeOdds"] = ho.get("place")

    envelope = _build_envelope(races_raw, race_date, venue)
    for race in envelope["races"]:
        rn = str(race["id"])
        race["quinella"] = qin_map.get(rn, {})
        race["forecast"]  = fct_map.get(rn, {})
        race["tierce"]    = tri_map.get(rn, {})
    return envelope


def _build_envelope(races_raw: list[dict], race_date: str, venue: str) -> dict:
    races = []
    for raw in races_raw:
        n = raw["id"]
        race = {
            "id":           n,
            "name":         raw.get("name", f"第{n}場讓賽"),
            "nameEn":       raw.get("nameEn", f"Race {n} Handicap"),
            "time":         raw.get("time") or (_RACE_TIMES_DEFAULT[n - 1] if n <= len(_RACE_TIMES_DEFAULT) else "—"),
            "grade":        raw.get("grade", "—"),
            "gradeEn":      "",
            "distance":     raw.get("distance", 1200),
            "trackType":    raw.get("trackType", "全天候跑道"),
            "trackTypeEn":  "AWT",
            "condition":    raw.get("condition", "—"),
            "conditionEn":  "",
            "prize":        raw.get("prize", 0),
            "ratingRange":  raw.get("ratingRange", "—"),
            "totalRunners": len(raw.get("horses", [])),
            "horses":       raw.get("horses", []),
            "quinella":     {},
            "forecast":     {},
            "tierce":       {},
            "reserves":     [],
        }
        races.append(race)

    venue_name = "跑馬地" if venue == "HV" else "沙田"
    meta = {
        "date":           race_date,
        "dayOfWeek":      _weekday_zh(race_date),
        "venue":          venue_name,
        "venueEn":        "Happy Valley" if venue == "HV" else "Sha Tin",
        "venueCode":      venue,
        "weather":        "—",
        "trackCondition": races[0]["condition"] if races else "—",
        "firstRaceTime":  races[0]["time"] if races else "—",
        "totalRaces":     len(races),
        "updated":        datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

    return {"meta": meta, "races": races, "_fetched_at": datetime.now().isoformat()}


# ------------------------------------------------------------------ #
# Cache helpers
# ------------------------------------------------------------------ #
def load_cached(race_date: str, venue: str) -> dict | None:
    path = _cache_path(race_date, venue)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_cache(data: dict, race_date: str, venue: str):
    path = _cache_path(race_date, venue)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[Cache] Saved → {path}")


# ------------------------------------------------------------------ #
# CLI
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import sys
    date_arg  = sys.argv[1] if len(sys.argv) > 1 else None
    venue_arg = sys.argv[2] if len(sys.argv) > 2 else None
    data = fetch_full_day(date_arg, venue_arg)
    save_cache(data, data["meta"]["date"], data["meta"]["venueCode"])
    print(json.dumps(data["meta"], ensure_ascii=False, indent=2))
    for r in data["races"]:
        print(f"  Race {r['id']}: {r['name']}  {len(r['horses'])} horses")
