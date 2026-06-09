"""
CMHK VIP Race Intelligence — Flask backend
Run:  python server.py
Open: http://localhost:8080
"""

import json
import os
import threading
import copy
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import anthropic

try:
    from dateutil.parser import parse as _parse_dt
except ImportError:
    _parse_dt = None

load_dotenv()

import fetcher as F

# Anthropic singleton — created once, reused across all requests
_anthropic_client: anthropic.Anthropic | None = None

def _get_anthropic_client() -> anthropic.Anthropic | None:
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client

# ------------------------------------------------------------------ #
# App setup
# ------------------------------------------------------------------ #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# In-memory state
_state = {
    "data":        None,   # current race day data
    "race_date":   None,
    "venue":       None,
    "last_fetch":  None,
    "fetch_error": None,
    "fetching":    False,
}
_lock = threading.Lock()


# ------------------------------------------------------------------ #
# Data access helpers
# ------------------------------------------------------------------ #
def _current_data() -> dict:
    with _lock:
        return _state["data"] or {}


def _get_races() -> list:
    return _current_data().get("races", [])


def _get_meta() -> dict:
    return _current_data().get("meta", {})


def _get_race(race_id: int) -> dict | None:
    return next((r for r in _get_races() if r["id"] == race_id), None)


# ------------------------------------------------------------------ #
# Fetch logic (runs on startup + schedule + manual trigger)
# ------------------------------------------------------------------ #
def _do_fetch(race_date: str = None, venue: str = None, force: bool = False):
    with _lock:
        if _state["fetching"]:
            return
        _state["fetching"] = True

    try:
        today = date.today().strftime("%Y-%m-%d")

        # Build candidate list
        if race_date:
            candidates = [{"date": race_date, "venue": venue or "ST"}]
        else:
            candidates = F.get_upcoming_race_days(from_date=today, days_ahead=10)
            if not candidates:
                candidates = [{"date": today, "venue": venue or "ST"}]

        for candidate in candidates:
            t_date  = candidate["date"]
            t_venue = candidate["venue"]

            # 1. Cache check (skip if force=True, or cache is stale >4h)
            cached = None
            if not force:
                cached = F.load_cached(t_date, t_venue)
                if cached:
                    fetched_at = cached.get("_fetched_at", "")
                    if _parse_dt:
                        try:
                            age_hours = (datetime.now() - _parse_dt(fetched_at)).total_seconds() / 3600
                            if age_hours > 4:
                                print(f"[Server] Cache stale ({age_hours:.1f}h), re-fetching {t_date} {t_venue}")
                                cached = None
                        except Exception:
                            pass
            else:
                print(f"[Server] Force refresh: skipping cache for {t_date} {t_venue}")

            if cached:
                total = sum(len(r.get("horses", [])) for r in cached.get("races", []))
                if total > 0:
                    with _lock:
                        _state["data"]        = cached
                        _state["race_date"]   = t_date
                        _state["venue"]       = t_venue
                        _state["last_fetch"]  = cached.get("_fetched_at", "cached")
                        _state["fetch_error"] = None
                    print(f"[Server] Loaded from cache: {t_date} {t_venue} ({total} horses)")
                    return

            # 2. Quick probe — only Race 1 (~7s) to avoid wasting 70s on an empty day
            print(f"[Server] Probing {t_date} {t_venue}...")
            if F.probe_race_day(t_date, t_venue) == 0:
                print(f"[Server] No entries yet for {t_date}, skipping...")
                continue

            # 3. Full fetch — entries confirmed, scrape all races (5 min hard cap)
            print(f"[Server] Full fetch: {t_date} {t_venue}")
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(F.fetch_full_day, t_date, t_venue)
                try:
                    data = fut.result(timeout=300)
                except FuturesTimeoutError:
                    raise RuntimeError("全量抓取超時（5分鐘），請稍後重試")
            total = sum(len(r.get("horses", [])) for r in data.get("races", []))

            if total > 0:
                F.save_cache(data, t_date, t_venue)
                with _lock:
                    _state["data"]        = data
                    _state["race_date"]   = t_date
                    _state["venue"]       = t_venue
                    _state["last_fetch"]  = data.get("_fetched_at")
                    _state["fetch_error"] = None
                print(f"[Server] Fetch complete: {t_date} {t_venue} ({total} horses)")
                return

            print(f"[Server] Probe passed but full fetch returned 0 for {t_date}")

        # All candidates exhausted
        with _lock:
            _state["fetch_error"] = "排位表尚未開放"
        print("[Server] No horse data found in any candidate date")

    except Exception as e:
        err = str(e)
        print(f"[Server] Fetch error: {err}")
        with _lock:
            _state["fetch_error"] = err
    finally:
        with _lock:
            _state["fetching"] = False


def _preload_cache():
    """Instantly load the most recent valid cache so the page is not empty on startup."""
    today = date.today().strftime("%Y-%m-%d")
    candidates = F.get_upcoming_race_days(from_date=today, days_ahead=10)
    for c in candidates:
        cached = F.load_cached(c["date"], c["venue"])
        if cached and sum(len(r.get("horses", [])) for r in cached.get("races", [])) > 0:
            with _lock:
                _state["data"]       = cached
                _state["race_date"]  = c["date"]
                _state["venue"]      = c["venue"]
                _state["last_fetch"] = cached.get("_fetched_at", "cached")
            print(f"[Server] Pre-loaded cache: {c['date']} {c['venue']} (will force-refresh)")
            return
    print("[Server] No valid cache found, waiting for background fetch...")


def _sample_fallback() -> dict:
    """Load embedded sample data from data.js via JSON (if exists) or minimal stub."""
    sample_path = os.path.join(BASE_DIR, "data", "sample.json")
    if os.path.exists(sample_path):
        with open(sample_path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "meta": {
            "date": date.today().strftime("%Y-%m-%d"),
            "venue": "沙田", "venueEn": "Sha Tin", "venueCode": "ST",
            "weather": "—", "trackCondition": "—",
            "firstRaceTime": "—", "totalRaces": 0,
            "updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
        "races": [],
        "_fetched_at": datetime.now().isoformat(),
        "_fallback": True,
    }


# ------------------------------------------------------------------ #
# Static file serving (HTML / JS / CSS)
# ------------------------------------------------------------------ #
@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/<path:filename>")
def static_files(filename):
    # Prevent directory traversal
    safe = os.path.normpath(filename)
    if safe.startswith(".."):
        return "", 403
    full = os.path.join(BASE_DIR, safe)
    if os.path.isdir(full):
        return "", 403
    return send_from_directory(BASE_DIR, safe)


# ------------------------------------------------------------------ #
# REST API
# ------------------------------------------------------------------ #
@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({
            "ok":        not _state["fetch_error"],
            "fetching":  _state["fetching"],
            "lastFetch": _state["last_fetch"],
            "error":     _state["fetch_error"],
            "raceDate":  _state["race_date"],
            "venue":     _state["venue"],
        })


@app.route("/api/raceday")
def api_raceday():
    return jsonify(_get_meta())


@app.route("/api/races")
def api_races():
    """Return race list (summary, no horses) for the sidebar/overview."""
    races = _get_races()
    summary = [{
        "id":          r["id"],
        "name":        r.get("name", ""),
        "nameEn":      r.get("nameEn", ""),
        "time":        r.get("time", ""),
        "grade":       r.get("grade", ""),
        "gradeEn":     r.get("gradeEn", ""),
        "distance":    r.get("distance", 0),
        "trackType":   r.get("trackType", ""),
        "condition":   r.get("condition", ""),
        "prize":       r.get("prize", 0),
        "ratingRange": r.get("ratingRange", ""),
        "totalRunners":len(r.get("horses", [])) or r.get("totalRunners", 0),
    } for r in races]
    return jsonify(summary)


@app.route("/api/race/<int:race_id>")
def api_race(race_id):
    race = _get_race(race_id)
    if not race:
        return jsonify({"error": f"Race {race_id} not found"}), 404
    return jsonify(race)


@app.route("/api/race/<int:race_id>/horses")
def api_horses(race_id):
    race = _get_race(race_id)
    if not race:
        return jsonify({"error": "Not found"}), 404
    return jsonify(race.get("horses", []))


@app.route("/api/race/<int:race_id>/odds")
def api_odds(race_id):
    race = _get_race(race_id)
    if not race:
        return jsonify({"error": "Not found"}), 404
    horses = race.get("horses", [])
    return jsonify([
        {"no": h["no"], "name": h.get("name",""), "winOdds": h.get("winOdds"), "placeOdds": h.get("placeOdds")}
        for h in horses
    ])


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    """Manually trigger a data refresh. Body: { "date": "YYYY-MM-DD", "venue": "ST", "force": true }"""
    body      = request.get_json(silent=True) or {}
    race_date = body.get("date")
    venue     = body.get("venue")
    force     = bool(body.get("force", False))

    t = threading.Thread(target=_do_fetch, args=(race_date, venue, force), daemon=True)
    t.start()

    msg = "強制重新抓取已啟動，請稍後刷新。" if force else "資料抓取已啟動，請稍後刷新。"
    return jsonify({"ok": True, "message": msg})


@app.route("/api/admin/race/<int:race_id>", methods=["PATCH"])
def api_admin_update_race(race_id):
    """Manually override race meta (e.g. condition, prize)."""
    body = request.get_json(silent=True) or {}
    with _lock:
        races = _state["data"].get("races", []) if _state["data"] else []
        race  = next((r for r in races if r["id"] == race_id), None)
        if not race:
            return jsonify({"error": "Not found"}), 404
        allowed = {"name","nameEn","time","grade","distance","trackType","condition","prize","ratingRange"}
        for k, v in body.items():
            if k in allowed:
                race[k] = v
    return jsonify({"ok": True})


@app.route("/api/admin/race/<int:race_id>/horses", methods=["PUT"])
def api_admin_set_horses(race_id):
    """Fully replace a race's horse list (manual override)."""
    horses = request.get_json(silent=True)
    if not isinstance(horses, list):
        return jsonify({"error": "Expected JSON array"}), 400
    snapshot = None
    with _lock:
        if not _state["data"]:
            return jsonify({"error": "No data loaded"}), 503
        race = next((r for r in _state["data"]["races"] if r["id"] == race_id), None)
        if not race:
            return jsonify({"error": "Not found"}), 404
        race["horses"] = horses
        snapshot = copy.deepcopy(_state["data"])
    # Persist outside lock using a local snapshot — safe from concurrent state changes
    meta = snapshot.get("meta", {})
    F.save_cache(snapshot, meta.get("date", ""), meta.get("venueCode", "ST"))
    return jsonify({"ok": True, "count": len(horses)})


@app.route("/api/analysis/<int:race_id>", methods=["POST"])
def api_analysis(race_id):
    """Call Claude to generate AI analysis for a race (always live, no cache)."""
    race = _get_race(race_id)
    if not race:
        return jsonify({"error": "Race not found"}), 404

    horses = race.get("horses", [])
    if not horses:
        return jsonify({"error": "No horses"}), 400

    client = _get_anthropic_client()
    if not client:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 503

    # Build prompt
    horse_lines = "\n".join(
        f"#{h['no']} {h['name']} | 負磅:{h.get('weight','—')} | 騎師:{h.get('jockey','—')} | "
        f"練馬師:{h.get('trainer','—')} | 官方評分:{h.get('rating','—')} | "
        f"近6績:{'/'.join(str(x) for x in h.get('recentForm',[]))} | "
        f"檔位:{h.get('gate','—')} | 賠率:{h.get('winOdds','—')}"
        for h in horses
    )
    prompt = f"""你是資深香港賽馬分析師，為VIP客戶提供本場賽事專業分析。

## 賽事資料
第{race_id}場 {race.get('name','')}
班次：{race.get('grade','')} | 距離：{race.get('distance','')}m {race.get('trackType','')}
場地狀況：{race.get('condition','')} | 獎金：HK${race.get('prize',0):,}

## 參賽馬匹
（馬號 | 馬名 | 負磅 | 騎師 | 練馬師 | 官方評分 | 近6績 | 檔位 | 賠率）
{horse_lines}

## 評分標準（score字段）
85–99：強烈推薦 — 本場最具勝出條件，多項指標領先同場
70–84：值得留意 — 具備競爭力，值得納入投注組合
50–69：冷門機會 — 有一定條件但存在明顯疑問
10–49：觀望 — 勝出希望渺茫，不建議投注

## 分析要求
1. 綜合考量：近績趨勢、官方評分高低、騎師/練馬師配搭、檔位優劣、負磅輕重、賠率市場信號
2. 分數層次分明：同場馬匹分數需有顯著差異，清晰反映競爭力排序
3. 強烈推薦每場最多2匹；觀望可有多匹
4. text評語必須詳盡，涵蓋：近績走勢分析、騎師/練馬師評價、檔位影響、負磅優劣、市場賠率解讀、整體勝出機率評估，行文流暢自然

## 輸出格式（純JSON，不含markdown或其他文字）
{{
  "horses": [
    {{
      "no": 馬號整數,
      "score": 整數(10–99),
      "tag": "強烈推薦" 或 "值得留意" 或 "冷門機會" 或 "觀望",
      "text": "100–150字詳細評語（繁體中文），需具體引用數據",
      "strengths": ["優勢描述，20字以內", "..."],
      "weaknesses": ["劣勢描述，20字以內", "..."]
    }}
  ]
}}
strengths 2–4條，weaknesses 1–3條。"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        # Add tagClass for frontend styling
        tag_class = {
            "強烈推薦": "border-trading-up text-trading-up",
            "值得留意": "border-primary-container text-primary-container",
            "冷門機會": "border-outline text-on-surface-variant",
            "觀望":     "border-muted text-muted",
        }
        for h in data.get("horses", []):
            h["tagClass"] = tag_class.get(h.get("tag", ""), "border-muted text-muted")

        return jsonify({"ok": True, "horses": data["horses"]})

    except Exception as e:
        print(f"[Claude] Analysis error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/voice-chat", methods=["POST"])
def api_voice_chat():
    """Receive raw PCM (16 kHz / 16-bit / mono), return OGG/Opus audio."""
    import volcano_client as vc

    app_id  = os.environ.get("VOLCANO_APP_ID")
    api_key = os.environ.get("VOLCANO_API_KEY")
    if not app_id or not api_key:
        return jsonify({"error": "VOLCANO_APP_ID / VOLCANO_API_KEY not configured"}), 503

    pcm = request.data
    if not pcm:
        return jsonify({"error": "Empty audio payload"}), 400

    try:
        audio = vc.volcano_chat_sync(pcm, app_id, api_key)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Volcano] Error: {type(e).__name__}: {e}")
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500

    if not audio:
        return jsonify({"error": "未能識別語音，請重新嘗試"}), 400

    return app.response_class(response=audio, status=200, mimetype="audio/ogg")


@app.route("/api/admin/export")
def api_export():
    """Download full race day JSON."""
    data = _current_data()
    resp = app.response_class(
        response=json.dumps(data, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json",
    )
    fname = f"cmhk_race_{data.get('meta',{}).get('date','unknown')}.json"
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    return resp


# ------------------------------------------------------------------ #
# Startup
# ------------------------------------------------------------------ #
def start_scheduler():
    sched = BackgroundScheduler(daemon=True)
    # Race hours: force-fetch every 15 min to keep odds current
    sched.add_job(lambda: _do_fetch(force=True), "cron", hour="17-23", minute="*/15",
                  id="race_hours_fetch", replace_existing=True)
    # Daytime: force-fetch every 2 hours to pick up new entries / schedule changes
    sched.add_job(lambda: _do_fetch(force=True), "cron", hour="8,10,12,14,16", minute="0",
                  id="daytime_fetch", replace_existing=True)
    sched.start()
    return sched


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CMHK VIP Race Intelligence Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--date", default=None, help="Race date YYYY-MM-DD (default: auto-detect)")
    parser.add_argument("--venue", default=None, help="ST or HV (default: auto-detect)")
    parser.add_argument("--no-fetch", action="store_true", help="Skip initial fetch (use cache/sample)")
    args = parser.parse_args()

    print("=" * 60)
    print("  CMHK VIP Race Intelligence System")
    print(f"  http://{args.host}:{args.port}")
    print("=" * 60)

    if args.no_fetch:
        _state["data"] = _sample_fallback()
        print("[Server] Skipping fetch, using cached/sample data")
    else:
        # Step 1: pre-load cache so the page is not empty while fetching
        _preload_cache()
        # Step 2: always force-refresh from HKJC in background for latest data
        print("[Server] Background force-refresh started...")
        t = threading.Thread(target=_do_fetch, args=(args.date, args.venue, True), daemon=True)
        t.start()

    sched = start_scheduler()
    print(f"[Scheduler] Auto-refresh every 15 min during race hours")

    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
