import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from playwright.sync_api import sync_playwright

# ---------------- CONFIG ---------------- #

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

LEAGUE_SLUG = "Ligue_1"    # EPL, La_Liga, Bundesliga, Serie_A, Ligue_1
SEASON      = "2025"
COMPETITION = "Ligue 1"    # "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"

# Applied AFTER normalization (normalized string → normalized string)
TEAM_ALIASES = {
    "borussia m.gladbach": "borussia monchengladbach",
    "m.gladbach":          "borussia monchengladbach",
    "cologne":             "koln",
    "fc cologne":          "koln",
    "paris saint germain":  "paris saint germain",
}

# Applied BEFORE normalization (raw Understat name → raw correct name)
RAW_ALIASES = {
    "Borussia Dortmund":    "Borussia Dortmund",
    "Borussia M.Gladbach":  "Borussia Mönchengladbach",
    "FC Cologne":           "1.FC Köln",
    "Paris Saint Germain":  "Paris Saint-Germain",
    "Paris Saint-Germain":  "Paris Saint-Germain",
    "Rennes":               "Stade Rennais FC",
    "Brest":                "Stade Brestois 29",
}

# ---------------- NORMALIZE ---------------- #

def normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"\b(fc|afc|cf|ac|as|rc|sc|sv|rcd|club|football club)\b", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return TEAM_ALIASES.get(text, text)  # alias lookup runs correctly now

# ---------------- FETCH VIA PLAYWRIGHT ---------------- #

def fetch_understat_matches():
    url = f"https://understat.com/league/{LEAGUE_SLUG}/{SEASON}"
    print(f"📡 Launching headless browser → {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(3000)

        data = page.evaluate("""
            () => {
                if (typeof datesData !== 'undefined') return datesData;
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const match = s.textContent.match(/datesData\\s*=\\s*JSON\\.parse\\('(.+?)'/);
                    if (match) {
                        return JSON.parse(match[1].replace(/\\\\x/g, '\\\\u00'));
                    }
                }
                return null;
            }
        """)
        browser.close()

    if not data:
        raise Exception("Could not extract datesData from page")

    print(f"✅ Got {len(data)} match entries")

    matches = []
    for item in data:
        try:
            matches.append({
                "understat_id": int(item["id"]),
                "home_team":    item["h"]["title"],
                "away_team":    item["a"]["title"],
                "datetime":     item["datetime"],
                "home_xg":      float(item["xG"]["h"]) if item.get("xG", {}).get("h") else None,
                "away_xg":      float(item["xG"]["a"]) if item.get("xG", {}).get("a") else None,
                "home_goals":   int(item["goals"]["h"]) if item.get("goals", {}).get("h") is not None else None,
                "away_goals":   int(item["goals"]["a"]) if item.get("goals", {}).get("a") is not None else None,
            })
        except (KeyError, TypeError, ValueError) as e:
            print(f"  ⚠️  Skipping malformed entry: {e}")
            continue

    print(f"✅ Parsed {len(matches)} matches")
    return matches

# ---------------- CLUB RESOLUTION (auto-create if missing) ---------------- #

def get_or_create_club_id(name: str, club_map: dict) -> str:
    # Apply raw alias before normalization
    name = RAW_ALIASES.get(name, name)
    norm = normalize(name)

    # 1. Exact match
    if norm in club_map:
        return club_map[norm]

    # 2. Jaccard similarity — avoids short common words stealing matches
    best_id = None
    best_score = 0.0
    best_norm = None
    norm_words = set(norm.split())
    for existing_norm, existing_id in club_map.items():
        existing_words = set(existing_norm.split())
        overlap = len(norm_words & existing_words)
        if overlap == 0:
            continue
        score = overlap / len(norm_words | existing_words)  # Jaccard
        if score > best_score:
            best_score = score
            best_id = existing_id
            best_norm = existing_norm

    if best_id and best_score >= 0.3:
        print(f"  🔍 Fuzzy matched '{name}' → '{best_norm}' ({best_score:.2f})")
        club_map[norm] = best_id
        return best_id

    # 3. Create new club
    res = supabase.table("clubs_master").insert({
        "name": name,
        "name_normalized": norm
    }).execute()
    new_id = res.data[0]["id"]
    club_map[norm] = new_id
    print(f"  🏟️  Created club: {name} (normalized: {norm})")
    return new_id

# ---------------- MAIN ---------------- #

def run():
    print("DEBUG:", normalize("Paris Saint-Germain"))
    print(f"🚀 Understat Match Scraper — {COMPETITION} {SEASON}/{int(SEASON)+1}")

    matches = fetch_understat_matches()

    clubs_res = supabase.table("clubs_master").select("id, name_normalized").execute()
    club_map = {c["name_normalized"]: c["id"] for c in clubs_res.data}
    print(f"✅ Loaded {len(club_map)} existing clubs")

    payloads = []
    clubs_created = 0

    for m in matches:
        size_before = len(club_map)
        home_id = get_or_create_club_id(m["home_team"], club_map)
        away_id = get_or_create_club_id(m["away_team"], club_map)
        clubs_created += len(club_map) - size_before

        try:
            match_date = datetime.strptime(
                m["datetime"], "%Y-%m-%d %H:%M:%S"
            ).date().isoformat()

            payloads.append({
                "home_club_id":                home_id,
                "away_club_id":                away_id,
                "match_date":                  match_date,
                "competition":                 COMPETITION,
                "provider_understat_match_id": str(m["understat_id"]),
                "home_xg":                     m["home_xg"],
                "away_xg":                     m["away_xg"],
                "home_goals":                  m["home_goals"],
                "away_goals":                  m["away_goals"],
            })
        except ValueError:
            continue

    if payloads:
        print(f"📡 Upserting {len(payloads)} matches...")
        supabase.table("matches_master").upsert(
            payloads,
            on_conflict="home_club_id, away_club_id, match_date"
        ).execute()

    print(f"""DONE Matches processed : {len(payloads)} Clubs created  : {clubs_created}""")

if __name__ == "__main__":
    run()