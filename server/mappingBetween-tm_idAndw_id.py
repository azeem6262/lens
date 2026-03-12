import os
import soccerdata as sd
import pandas as pd
import unicodedata
import re
from rapidfuzz import fuzz
from supabase import create_client
from dotenv import load_dotenv

# ---------------- SETUP ---------------- #
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ws = sd.WhoScored(leagues="FRA-Ligue 1", seasons="2025")

# Comprehensive aliases — maps WhoScored club names → clubs_master name_normalized
TEAM_ALIASES = {
    # EPL
    "man utd":                   "manchester united",
    "man united":                "manchester united",
    "manchester utd":            "manchester united",
    "man city":                  "manchester city",
    "manchester city":           "manchester city",
    "spurs":                     "tottenham hotspur",
    "tottenham":                 "tottenham hotspur",
    "wolves":                    "wolverhampton wanderers",
    "wolverhampton":             "wolverhampton wanderers",
    "newcastle utd":             "newcastle united",
    "newcastle":                 "newcastle united",
    "nott'm forest":             "nottingham forest",
    "nottm forest":              "nottingham forest",
    "sheffield utd":             "sheffield united",
    "sheffield wednesday":       "sheffield wednesday",
    "west brom":                 "west bromwich albion",
    "west ham":                  "west ham united",
    "luton":                     "luton town",
    "brighton":                  "brighton hove albion",
    # La Liga
    "fc barcelona":              "barcelona",
    "atletico madrid":           "atletico de madrid",
    "atletico":                  "atletico de madrid",
    "real madrid":               "real madrid",
    "deportivo alaves":          "deportivo alaves",
    "alaves":                    "deportivo alaves",
    "rayo":                      "rayo vallecano",
    "betis":                     "real betis",
    "real betis":                "real betis",
    "sociedad":                  "real sociedad",
    "real sociedad":             "real sociedad",
    "athletic bilbao":           "athletic club",
    "athletic":                  "athletic club",
    "celta":                     "celta vigo",
    "celta vigo":                "celta vigo",
    "espanyol":                  "rcd espanyol",
    "rcd espanyol":              "rcd espanyol",
    "valladolid":                "real valladolid",
    # Bundesliga
    "bayer leverkusen":          "bayer 04 leverkusen",
    "leverkusen":                "bayer 04 leverkusen",
    "dortmund":                  "borussia dortmund",
    "bvb":                       "borussia dortmund",
    "gladbach":                  "borussia monchengladbach",
    "m'gladbach":                "borussia monchengladbach",
    "monchengladbach":           "borussia monchengladbach",
    "rb leipzig":                "rb leipzig",
    "leipzig":                   "rb leipzig",
    "hertha":                    "hertha bsc",
    "hertha berlin":             "hertha bsc",
    "frankfurt":                 "eintracht frankfurt",
    "eintracht frankfurt":       "eintracht frankfurt",
    "stuttgart":                 "vfb stuttgart",
    "vfb stuttgart":             "vfb stuttgart",
    "wolfsburg":                 "vfl wolfsburg",
    "vfl wolfsburg":             "vfl wolfsburg",
    "freiburg":                  "sc freiburg",
    "sc freiburg":               "sc freiburg",
    "augsburg":                  "fc augsburg",
    "mainz":                     "1. fsv mainz 05",
    "mainz 05":                  "1. fsv mainz 05",
    "hoffenheim":                "tsg hoffenheim",
    "tsg hoffenheim":            "tsg hoffenheim",
    "union berlin":              "1. fc union berlin",
    "cologne":                   "1. fc koln",
    "koln":                      "1. fc koln",
    "fc koln":                   "1. fc koln",
    "heidenheim":                "1. fc heidenheim",
    "werder":                    "sv werder bremen",
    "werder bremen":             "sv werder bremen",
    "bochum":                    "vfl bochum",
    "vfl bochum":                "vfl bochum",
    "hamburg":                   "hamburger sv",
    "hsv":                       "hamburger sv",
    "st pauli":                  "fc st. pauli",
    "holstein kiel":             "holstein kiel",
    # Serie A
    "ac milan":                  "milan",
    "inter milan":               "inter",
    "inter":                     "inter",
    "internazionale":            "inter",
    "juventus":                  "juventus",
    "napoli":                    "ssc napoli",
    "ssc napoli":                "ssc napoli",
    "roma":                      "as roma",
    "as roma":                   "as roma",
    "lazio":                     "ss lazio",
    "ss lazio":                  "ss lazio",
    "atalanta":                  "atalanta bc",
    "fiorentina":                "acf fiorentina",
    "acf fiorentina":            "acf fiorentina",
    "torino":                    "torino fc",
    "bologna":                   "bologna fc",
    "monza":                     "ac monza",
    "udinese":                   "udinese calcio",
    "sassuolo":                  "us sassuolo",
    "empoli":                    "empoli fc",
    "lecce":                     "us lecce",
    "cagliari":                  "cagliari calcio",
    "hellas verona":             "hellas verona",
    "verona":                    "hellas verona",
    "genoa":                     "genoa cfc",
    "frosinone":                 "frosinone calcio",
    "salernitana":               "us salernitana",
    "venezia":                   "venezia fc",
    "como":                      "como 1907",
    "parma":                     "parma calcio",
    # Ligue 1
    "psg":                       "paris saint-germain",
    "paris sg":                  "paris saint-germain",
    "paris saint germain":       "paris saint-germain",
    "marseille":                 "olympique de marseille",
    "olympique marseille":       "olympique de marseille",
    "lyon":                      "olympique lyonnais",
    "olympique lyonnais":        "olympique lyonnais",
    "monaco":                    "as monaco",
    "as monaco":                 "as monaco",
    "lille":                     "losc lille",
    "losc":                      "losc lille",
    "losc lille":                "losc lille",
    "nice":                      "ogc nice",
    "ogc nice":                  "ogc nice",
    "lens":                      "rc lens",
    "rc lens":                   "rc lens",
    "rennes":                    "stade rennais",
    "stade rennais":             "stade rennais",
    "nantes":                    "fc nantes",
    "fc nantes":                 "fc nantes",
    "strasbourg":                "rc strasbourg",
    "rc strasbourg":             "rc strasbourg",
    "montpellier":               "montpellier hsc",
    "brest":                     "stade brestois",
    "stade brestois":            "stade brestois",
    "reims":                     "stade de reims",
    "stade de reims":            "stade de reims",
    "toulouse":                  "toulouse fc",
    "lorient":                   "fc lorient",
    "metz":                      "fc metz",
    "clermont":                  "clermont foot",
    "le havre":                  "le havre ac",
    "st etienne":                "as saint-etienne",
    "saint-etienne":             "as saint-etienne",
    "auxerre":                   "aj auxerre",
    "angers":                    "angers sco",
}


# ---------------- NORMALIZATION UTILS ---------------- #
def normalize_text(text: str):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text)


def normalize_team(team_name: str):
    team = normalize_text(team_name)
    team = re.sub(r"\b(fc|afc|cf|rcd|rc|cd|sc|ac|as|ss|bv|sv|vfb)\b", "", team)
    team = re.sub(r"\s+", " ", team).strip()
    return TEAM_ALIASES.get(team, team)


def get_position_group(raw_position: str):
    if not raw_position:
        return "Unknown", None
    pos = raw_position.lower()
    if any(x in pos for x in ["striker", "winger", "forward", "centre-forward"]):
        return "Attacker", "stats_attackers"
    if any(x in pos for x in ["midfield", "amc", "dmc", "cm", "mezzala"]):
        return "Midfielder", "stats_midfielders"
    if any(x in pos for x in ["back", "defender", "sweeper", "cb", "lb", "rb"]):
        return "Defender", "stats_defenders"
    if "goalkeeper" in pos:
        return "Goalkeeper", "stats_goalkeepers"
    return "Unknown", None


# ---------------- CLUB RESOLUTION ---------------- #

# Preloaded once at startup to avoid N+1 queries
_all_clubs_cache = None

def preload_all_clubs():
    global _all_clubs_cache
    if _all_clubs_cache is None:
        res = supabase.table("clubs_master").select("id, name, name_normalized").execute()
        _all_clubs_cache = res.data
        print(f"✅ Preloaded {len(_all_clubs_cache)} clubs")
    return _all_clubs_cache


def get_or_create_club(normalized_team_name: str, club_cache: dict):
    if normalized_team_name in club_cache:
        return club_cache[normalized_team_name]

    all_clubs = preload_all_clubs()

    # 1. Exact match on name_normalized
    for club in all_clubs:
        if club["name_normalized"] == normalized_team_name:
            club_cache[normalized_team_name] = club["id"]
            return club["id"]

    # 2. Fuzzy match against all existing clubs (catches aliases the dict missed)
    best_match = None
    best_score = 0
    for club in all_clubs:
        score = fuzz.ratio(normalized_team_name, club["name_normalized"])
        if score > best_score:
            best_score = score
            best_match = club

    if best_score >= 80 and best_match:
        print(f"🔍 Fuzzy club match: '{normalized_team_name}' → '{best_match['name']}' ({best_score}%)")
        club_cache[normalized_team_name] = best_match["id"]
        return best_match["id"]

    # 3. Create new club only if no fuzzy match found
    new_club = supabase.table("clubs_master").insert({
        "name": normalized_team_name,
        "name_normalized": normalized_team_name
    }).execute()

    club_id = new_club.data[0]["id"]
    club_cache[normalized_team_name] = club_id
    _all_clubs_cache.append({"id": club_id, "name": normalized_team_name, "name_normalized": normalized_team_name})
    print(f"🏟️ Created new club: {normalized_team_name}")
    return club_id


# ---------------- TM_ID LOOKUP ---------------- #
def build_tm_id_lookup():
    print("🔗 Building tm_id lookup from players_master...")
    master_res = supabase.table("players_master").select("id, name, tm_id").execute().data
    id_to_tmid = {p["id"]: p["tm_id"] for p in master_res if p.get("tm_id")}
    print(f"✅ Found {len(id_to_tmid)} existing tm_id mappings in players_master")
    return id_to_tmid


# ---------------- DATA FETCHING ---------------- #
def get_whoscored_roster():
    print("📡 Fetching FULL WhoScored roster for season...")
    schedule = ws.read_schedule().reset_index()
    all_match_ids = schedule["game_id"].unique()
    df = ws.read_events(match_id=all_match_ids).reset_index()
    df = df.dropna(subset=["player", "player_id", "team"])
    df = df.drop_duplicates(subset=["player_id"])
    pos_col = next((c for c in ["position", "player_position"] if c in df.columns), None)
    if pos_col:
        df = df.rename(columns={pos_col: "position"})
    else:
        df["position"] = None
    print(f"✅ Found {len(df)} unique players")
    return df[["player", "player_id", "team", "position"]]


# ---------------- THE MASTER SYNC ---------------- #
def run_identity_sync():
    print("🚀 Initializing LensPro Neural Identity Sync...")

    ws_data = get_whoscored_roster()

    master_players = supabase.table("players_master")\
        .select("id, name, club_id, tm_id")\
        .execute().data

    mapping_res = supabase.table("player_mappings").select("whoscored_id, tm_id").execute().data
    existing_ws_ids = {int(m["whoscored_id"]) for m in mapping_res if m["whoscored_id"]}

    id_to_tmid = build_tm_id_lookup()

    club_cache = {}
    stats = {"created": 0, "reused": 0, "skipped": 0, "no_tmid": 0}

    for _, row in ws_data.iterrows():

        ws_id        = int(row["player_id"])
        ws_name      = row["player"]
        ws_name_norm = normalize_text(ws_name)
        ws_team_norm = normalize_team(row["team"])

        if ws_id in existing_ws_ids:
            stats["skipped"] += 1
            continue

        club_id = get_or_create_club(ws_team_norm, club_cache)

        matched_uuid = None

        # -------- STEP 1: Exact name match --------
        name_matches = [
            p for p in master_players
            if normalize_text(p["name"]) == ws_name_norm
        ]

        if len(name_matches) == 0:
            # -------- STEP 1b: Fuzzy name match --------
            fuzzy_matches = [
                p for p in master_players
                if fuzz.ratio(normalize_text(p["name"]), ws_name_norm) >= 88
            ]
            if len(fuzzy_matches) == 1:
                matched_uuid = fuzzy_matches[0]["id"]
                print(f"🧠 Fuzzy matched: {ws_name} → {fuzzy_matches[0]['name']}")
            elif len(fuzzy_matches) > 1:
                for p in fuzzy_matches:
                    if p["club_id"] == club_id:
                        matched_uuid = p["id"]
                        print(f"🧠 Fuzzy+Club matched: {ws_name} → {p['name']}")
                        break

        elif len(name_matches) == 1:
            candidate = name_matches[0]
            if candidate["club_id"] == club_id:
                matched_uuid = candidate["id"]
                print(f"🔁 Linked (Name + Club): {ws_name}")
            else:
                matched_uuid = None

        else:
            print(f"⚠ Multiple players named {ws_name}, disambiguating...")
            for p in name_matches:
                if p["club_id"] == club_id:
                    matched_uuid = p["id"]
                    print(f"🎯 Linked (Correct Club): {ws_name}")
                    break
            if not matched_uuid:
                for p in name_matches:
                    score = fuzz.ratio(ws_name_norm, normalize_text(p["name"]))
                    if score >= 95:
                        matched_uuid = p["id"]
                        print(f"🧠 Linked (Fuzzy {score}%): {ws_name}")
                        break

        # -------- STEP 2: Create if still unmatched --------
        if not matched_uuid:
            existing_check = supabase.table("players_master") \
                .select("id") \
                .ilike("name", ws_name) \
                .eq("club_id", club_id) \
                .execute()

            if existing_check.data:
                matched_uuid = existing_check.data[0]["id"]
                print(f"🛡️ DB Duplicate Prevented: {ws_name}")
            else:
                pos_group, _ = get_position_group(str(row["position"] or ""))
                new_p = supabase.table("players_master").insert({
                    "name": ws_name,
                    "club_id": club_id,
                    "position_group": pos_group
                }).execute()
                matched_uuid = new_p.data[0]["id"]
                stats["created"] += 1
                print(f"🆕 Created: {ws_name}")
                master_players.append({
                    "id": matched_uuid,
                    "name": ws_name,
                    "club_id": club_id,
                    "tm_id": None
                })

        # -------- STEP 3: Resolve tm_id --------
        if matched_uuid:
            tm_id = id_to_tmid.get(matched_uuid)
            if not tm_id:
                master_row = next((p for p in master_players if p["id"] == matched_uuid), None)
                if master_row:
                    tm_id = master_row.get("tm_id")

            if not tm_id:
                stats["no_tmid"] += 1
                print(f"⚠️  No tm_id found for {ws_name} — inserting without tm_id")

            # -------- STEP 4: Insert mapping --------
            supabase.table("player_mappings").upsert({
                "player_id": matched_uuid,
                "whoscored_id": ws_id,
                "tm_id": tm_id
            }, on_conflict="whoscored_id").execute()

            stats["reused"] += 1

    print(f"""
📊 SYNC SUMMARY
Created:  {stats['created']}
Linked:   {stats['reused']}
Skipped:  {stats['skipped']}
No tm_id: {stats['no_tmid']}
✅ Bridge is stable.
""")


if __name__ == "__main__":
    run_identity_sync()