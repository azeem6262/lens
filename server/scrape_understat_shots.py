import os
import re
import time
import random
import html
import unicodedata
from dotenv import load_dotenv
from supabase import create_client
from playwright.sync_api import sync_playwright

# ---------------- CONFIG ---------------- #

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

COMPETITION       = "Premier League"
RESTART_EVERY     = 40
DELAY_MIN         = 5
DELAY_MAX         = 9
BLOCK_THRESHOLD   = 3
BLOCK_PAUSE_SHORT = 5 * 60
BLOCK_PAUSE_LONG  = 15 * 60

# ---------------- MATCH IDS OVERRIDE ---------------- #
# Set to a list of understat match IDs to re-scrape only those matches.
# Set to None to scrape all unscraped matches for COMPETITION as normal.

MATCH_IDS_OVERRIDE = [
    28783, 28784, 28798, 28800, 28815, 28823, 28842, 28855, 28876, 28878,
    28891, 28908, 28913, 28914, 28918, 28927, 28931, 28938, 28949, 28951,
    28961, 28971, 28989, 28998, 29017, 29024, 29028, 29029, 29031, 29033,
    29034, 29035, 29037, 29038, 29040, 29041, 29042, 29043, 29044, 29047,
    29048, 29049, 29050, 29051, 29053, 29055, 29058, 29062, 29064, 29067,
    29087,
]

# ---------------- PLAYER NAME ALIASES ---------------- #
# Maps Understat player name (lowercased) → exact name in players_master
# Add entries here whenever a player's shot map is missing due to name mismatch.

PLAYER_NAME_ALIASES = {
    "hugo ekitike":         "Hugo Ekitiké",
    "mathis cherki":        "Rayan Cherki",
    "thiago":               "Igor Thiago",
    "amad diallo traore":   "Amad Diallo",
    "martin odegaard":      "Martin Ødegaard",
    "tomas soucek":         "Tomáš Souček",
    "viktor gyokeres":      "Viktor Gyökeres",
    "naif aguerd":          "Nayef Aguerd",
    "ibrahim sangare":      "Ibrahim Sangaré",
    "rayan ait nouri":      "Rayan Aït-Nouri",
    "chimuanya ugochukwu":  "Lesley Ugochukwu",
    "yehor yarmolyuk":      "Yehor Yarmoliuk",
    "pape sarr":            "Pape Matar Sarr",
    "ismaila sarr":         "Ismaïla Sarr",
    "marc guehi":           "Marc Guéhi",
    "gabriel":              "Gabriel Magalhães",
    "jamie bynoe-gittens":  "Jamie Bynoe-Gittens",
    "fernando lopez":       "Fernando López",
    "nikola milenkovic":    "Nikola Milenković",
    "matthew cash":         "Matty Cash",
    "yeremi pino":            "Yéremy Pino",
    "emile smith-rowe":     "Emile Smith Rowe",
    "fabio carvalho":       "Fábio Carvalho",
    "joshua king":          "Josh King",
    "iyenoma destiny udogie": "Destiny Udogie",
    "max kilman":                  "Maximilian Kilman",
    "arnaud kalimuendo muinga":    "Arnaud Kalimuendo",
    "jeremy doku":                 "Jérémy Doku",
    "eli junior kroupi":           "Eli Kroupi",
    "ben doak":                    "Ben Gannon-Doak",
    "savio":                       "Savinho",
    "ezri konsa ngoyo":            "Ezri Konsa",
    "vitalii mykolenko":           "Vitaliy Mykolenko",
    "florentino luís":             "Florentino",
    "valentino livramento":        "Tino Livramento",
    "bafode diakite":              "Bafodé Diakité",
}

# ---------------- NORMALIZE ---------------- #

def normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"\b(fc|afc|cf|ac|as|rc|sc|sv|rcd|club|football club)\b", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ---------------- CACHES ---------------- #

_player_cache = {}
_match_cache  = {}

def get_player_id(understat_player_id, player_name):
    player_name = html.unescape(player_name)
    key = str(understat_player_id)

    # Check alias FIRST before cache
    alias_name = PLAYER_NAME_ALIASES.get(player_name.lower()) or \
                 PLAYER_NAME_ALIASES.get(normalize(player_name))

    if not alias_name and key in _player_cache:
        return _player_cache[key]

    lookup_name = alias_name if alias_name else player_name

    res = supabase.table("players_master")\
        .select("id")\
        .ilike("name", lookup_name)\
        .limit(1)\
        .execute()

    if res.data:
        _player_cache[key] = res.data[0]["id"]
        if alias_name:
            print(f"  ✅ Alias resolved '{player_name}' → '{alias_name}'")
        return _player_cache[key]

    # Fallback: normalized fuzzy match
    norm = normalize(player_name)
    if len(norm) > 5:
        res2 = supabase.table("players_master")\
            .select("id, name")\
            .ilike("name", f"%{norm}%")\
            .limit(1)\
            .execute()

        if res2.data:
            match_name = res2.data[0]['name'].lower()
            if player_name.lower() in match_name.split():
                _player_cache[key] = res2.data[0]["id"]
                print(f"  ⚠️  Fuzzy player match '{player_name}' → '{res2.data[0]['name']}'")
                return _player_cache[key]

    _player_cache[key] = None
    return None

def get_match_id(understat_match_id):
    key = str(understat_match_id)
    if key in _match_cache:
        return _match_cache[key]

    res = supabase.table("matches_master")\
        .select("id")\
        .eq("provider_understat_match_id", str(understat_match_id))\
        .execute()

    if res.data:
        _match_cache[key] = res.data[0]["id"]
        return _match_cache[key]

    _match_cache[key] = None
    return None

# ---------------- FETCH SHOTS ---------------- #

def fetch_shots_for_match(page, understat_match_id):
    url = f"https://understat.com/match/{understat_match_id}"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_function("typeof shotsData !== 'undefined'", timeout=15000)
    except Exception as e:
        return None, str(e)

    data = page.evaluate("""
        () => {
            if (typeof shotsData !== 'undefined') return shotsData;
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                const m = s.textContent.match(/shotsData\\s*=\\s*JSON\\.parse\\('(.+?)'/);
                if (m) {
                    try { return JSON.parse(m[1]); }
                    catch(e) { return null; }
                }
            }
            return null;
        }
    """)

    return data, None

# ---------------- GET MATCHES TO PROCESS ---------------- #

def get_matches_to_process():
    # Override mode: re-scrape specific match IDs
    if MATCH_IDS_OVERRIDE is not None:
        print(f"🎯 Override mode: re-scraping {len(MATCH_IDS_OVERRIDE)} specific matches")
        matches = []
        for understat_mid in MATCH_IDS_OVERRIDE:
            canonical_id = get_match_id(understat_mid)
            if canonical_id:
                matches.append({
                    "id": canonical_id,
                    "provider_understat_match_id": str(understat_mid)
                })
            else:
                print(f"  ⚠️  No match found for understat ID {understat_mid}")
        print(f"📊 {len(matches)} matches resolved and ready to re-scrape")
        return matches

    # Normal mode: scrape all unscraped matches for COMPETITION
    res = supabase.table("matches_master")\
        .select("id, provider_understat_match_id")\
        .eq("competition", COMPETITION)\
        .not_.is_("provider_understat_match_id", "null")\
        .execute()

    if not res.data:
        return []

    all_matches = res.data

    # Paginate through ALL understat_shots to get every done match_id
    already_done = set()
    offset = 0
    while True:
        shot_res = supabase.table("understat_shots")\
            .select("match_id")\
            .range(offset, offset + 999)\
            .execute()
        if not shot_res.data:
            break
        for r in shot_res.data:
            already_done.add(r["match_id"])
        if len(shot_res.data) < 1000:
            break
        offset += 1000

    remaining = [m for m in all_matches if m["id"] not in already_done]

    print(f"📊 {len(all_matches)} total, {len(already_done)} done, {len(remaining)} remaining")
    return remaining

# ---------------- INSERT SHOTS ---------------- #

def insert_shots(shots_payload):
    if not shots_payload:
        return
    for i in range(0, len(shots_payload), 500):
        supabase.table("understat_shots")\
            .upsert(shots_payload[i:i+500], on_conflict="understat_shot_id")\
            .execute()

# ---------------- PROCESS ONE MATCH ---------------- #

def process_match(page, match):
    canonical_id  = match["id"]
    understat_mid = match["provider_understat_match_id"]

    data, err = fetch_shots_for_match(page, understat_mid)

    if err:
        return 0, "timeout"

    if not data:
        return 0, "no_data"

    shots_payload = []
    for side in ["h", "a"]:
        for shot in data.get(side, []):
            try:
                player_uuid = get_player_id(shot.get("player_id"), shot.get("player", ""))
                if not player_uuid:
                    print(f"  ❌ UNMATCHED: '{shot.get('player', '')}' (match {understat_mid})")
                assist_uuid = get_player_id(shot.get("assist_player_id"), shot.get("assist", "")) \
                              if shot.get("assist_player_id") else None

                shots_payload.append({
                    "understat_shot_id":  f"{understat_mid}_{shot['id']}",
                    "match_id":           canonical_id,
                    "player_id":          player_uuid,
                    "player_assisted_id": assist_uuid,
                    "minute":             int(shot.get("minute", 0)),
                    "x":                  float(shot.get("X", 0)),
                    "y":                  float(shot.get("Y", 0)),
                    "xg":                 float(shot.get("xG", 0)),
                    "result":             shot.get("result"),
                    "situation":          shot.get("situation"),
                    "shot_type":          shot.get("shotType"),
                    "last_action":        shot.get("lastAction"),
                    "side":               side,
                })
            except (KeyError, TypeError, ValueError):
                continue

    insert_shots(shots_payload)
    return len(shots_payload), "ok"

# ---------------- BROWSER HELPER ---------------- #

def new_browser_page(p):
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    return browser, context.new_page()

# ---------------- ADAPTIVE PAUSE ---------------- #

def adaptive_pause(consecutive_failures, p, browser, page):
    if consecutive_failures < BLOCK_THRESHOLD:
        return browser, page

    mins = BLOCK_PAUSE_SHORT // 60
    print(f"\n  🚫 {consecutive_failures} consecutive timeouts — likely rate limited.")
    print(f"  ⏸️  Pausing {mins} minutes before retrying...")

    try:
        browser.close()
    except:
        pass

    for remaining in range(BLOCK_PAUSE_SHORT, 0, -30):
        print(f"     ...{remaining}s remaining")
        time.sleep(30)

    print("  🔄 Resuming with fresh browser...")
    browser, page = new_browser_page(p)
    return browser, page

# ---------------- MAIN ---------------- #

def run():
    mode = "OVERRIDE" if MATCH_IDS_OVERRIDE is not None else "NORMAL"
    print(f"🚀 Understat Shot Scraper — {COMPETITION} [{mode} MODE]")
    print(f"   Delays: {DELAY_MIN}-{DELAY_MAX}s per match")
    print(f"   Block detection: pause after {BLOCK_THRESHOLD} consecutive timeouts\n")

    matches = get_matches_to_process()
    if not matches:
        print("✅ Nothing to scrape.")
        return

    total_shots       = 0
    total_failed      = 0
    consecutive_fails = 0

    with sync_playwright() as p:
        browser, page = new_browser_page(p)

        for i, match in enumerate(matches):
            mid = match["provider_understat_match_id"]
            print(f"[{i+1}/{len(matches)}] Match {mid}", end=" ... ", flush=True)

            if consecutive_fails >= BLOCK_THRESHOLD:
                browser, page = adaptive_pause(consecutive_fails, p, browser, page)
                consecutive_fails = 0

            if i > 0 and i % RESTART_EVERY == 0:
                print(f"\n  🔄 Proactive restart at match {i+1}...")
                try:
                    browser.close()
                except:
                    pass
                time.sleep(5)
                browser, page = new_browser_page(p)

            try:
                count, status = process_match(page, match)

                if status == "timeout":
                    consecutive_fails += 1
                    print(f"⏱️  timeout ({consecutive_fails} consecutive)")
                elif status == "no_data":
                    consecutive_fails = 0
                    print(f"— no data (future fixture?)")
                else:
                    consecutive_fails = 0
                    total_shots += count
                    print(f"✅ {count} shots")

            except Exception as e:
                consecutive_fails += 1
                total_failed += 1
                print(f"❌ error: {e}")
                try:
                    browser.close()
                except:
                    pass
                time.sleep(8)
                browser, page = new_browser_page(p)

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        try:
            browser.close()
        except:
            pass

    print(f"""
DONE
Total shots upserted : {total_shots}
Hard errors          : {total_failed}
""")

if __name__ == "__main__":
    run()