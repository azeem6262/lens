import soccerdata as sd
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import os
import time
import random

# ---------------- SETUP ---------------- #

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

ws = sd.WhoScored(
    leagues="GER-Bundesliga",
    seasons="2025",
    no_cache=False  # cache the schedule
)



# ---------------- HELPERS ---------------- #

def clean_value(val):
    if pd.isna(val):
        return None
    return val


def safe_float(val):
    if pd.isna(val):
        return None
    try:
        return float(val)
    except:
        return None


# ---------------- LOAD SCHEDULE ONCE (SAFE) ---------------- #

def load_schedule():

    print("📡 Fetching schedule once (safe mode)...")

    try:
        schedule = ws.read_schedule(force_cache=False).reset_index()
    except Exception as e:

        print("⚠ Schedule fetch failed, retrying in 60s...")
        time.sleep(60)

        schedule = ws.read_schedule(force_cache=False).reset_index()

    schedule_map = {
        int(row["game_id"]): row
        for _, row in schedule.iterrows()
    }

    match_ids = list(schedule_map.keys())

    print(f"⚽ Found {len(match_ids)} matches")

    return match_ids, schedule_map


# ---------------- INSERT MATCH ---------------- #

def insert_match(match_row):

    payload = {
        "whoscored_match_id": int(match_row["game_id"]),
        "competition": "Bundesliga",
        "season": "2025",
        "match_date": match_row["date"].isoformat()
        if pd.notna(match_row["date"])
        else None,
        "home_team": str(match_row["home_team"])
        if pd.notna(match_row["home_team"])
        else None,
        "away_team": str(match_row["away_team"])
        if pd.notna(match_row["away_team"])
        else None
    }

    res = supabase.table("matches") \
        .upsert(payload, on_conflict="whoscored_match_id") \
        .execute()

    return res.data[0]["id"]


# ---------------- PRELOAD PLAYER MAP ---------------- #

def preload_player_map():

    print("📡 Loading player mappings once...")

    mapping_res = supabase.table("player_mappings") \
        .select("player_id, whoscored_id") \
        .execute()

    player_map = {
        int(m["whoscored_id"]): m["player_id"]
        for m in mapping_res.data
        if m["whoscored_id"] is not None
    }

    print(f"✅ Loaded {len(player_map)} mappings")

    return player_map


# ---------------- RESUME PROTECTION ---------------- #

def get_existing_matches():
    existing = set()
    offset = 0
    while True:
        res = supabase.table("matches") \
            .select("whoscored_match_id") \
            .range(offset, offset + 999) \
            .execute()
        if not res.data:
            break
        for m in res.data:
            existing.add(int(m["whoscored_match_id"]))
        if len(res.data) < 1000:
            break
        offset += 1000
    print(f"📊 Already have {len(existing)} matches")
    return existing


# ---------------- PROCESS MATCH (BLOCK-SAFE) ---------------- #

def process_match(game_id, match_row, player_map):

    print(f"\n⚽ Processing {game_id}")

    # Retry-safe event fetch
    try:
        events = ws.read_events(match_id=[game_id]).reset_index(drop=True)

    except Exception:

        print("⚠ Rate limited. Sleeping 90 seconds...")
        time.sleep(90)

        try:
            events = ws.read_events(match_id=[game_id]).reset_index(drop=True)

        except Exception:
            print(f"❌ Skipping blocked match {game_id}")
            return

    if len(events) == 0:
        print(f"⏭️  Skipping {game_id} — no events (future fixture?)")
        return

    match_uuid = insert_match(match_row)

    payload = []

    for idx, e in events.iterrows():

        

        player_uuid = (
            player_map.get(int(e["player_id"]))
            if pd.notna(e.get("player_id"))
            else None
        )

        quals = e.get('qualifiers', [])
        is_key_pass = False
        is_progressive = False

        for q in quals:
            q_type = q.get('type', {}).get('displayName', '')
            if q_type == 'KeyPass':
                is_key_pass = True

        if e.get('type') == 'Pass' and pd.notna(e.get('end_x')):
            start_dist = ((100 - e['x'])**2 + (50 - e['y'])**2)**0.5
            end_dist = ((100 - e['end_x'])**2 + (50 - e['end_y'])**2)**0.5
            if end_dist < (0.75 * start_dist):
                is_progressive = True

        payload.append({

            "match_id": match_uuid, 
            "whoscored_event_id": f"{game_id}_{idx}", 
            "minute": int(e["minute"]) if pd.notna(e.get("minute")) else None, 
            "second": int(e["second"]) if pd.notna(e.get("second")) else None, 
            "period": clean_value(str(e["period"])) if pd.notna(e.get("period")) else None, 
            "team": clean_value(e.get("team")), 
            "player_id": player_uuid, "event_type": clean_value(e.get("type")), 
            "outcome": clean_value(e.get("outcome_type")), 
            "x": safe_float(e.get("x")), 
            "y": safe_float(e.get("y")), 
            "end_x": safe_float(e.get("end_x")), 
            "end_y": safe_float(e.get("end_y")), 
            "is_goal": bool(e["is_goal"]) if pd.notna(e.get("is_goal")) else False, 
            "card_type": clean_value(e.get("card_type")),
            "is_key_pass": is_key_pass,
            "is_progressive": is_progressive,
            "is_shot_assist": is_key_pass
        })

    # Batch insert
    for i in range(0, len(payload), 500):

        supabase.table("match_events") \
            .upsert(payload[i:i+500],
                    on_conflict="whoscored_event_id") \
            .execute()

    print(f"✅ Inserted {len(payload)} events")

    # CRITICAL: Rate limiting
    sleep_time = random.uniform(4, 7)

    print(f"⏳ Sleeping {sleep_time:.1f}s")
    time.sleep(sleep_time)


# ---------------- MAIN RUNNER ---------------- #

def run():

    match_ids, schedule_map = load_schedule()

    player_map = preload_player_map()

    existing_matches = get_existing_matches()

    remaining = [m for m in match_ids if m not in existing_matches]  #CRITICAL: CHANGE IT TO: remaining = [m for m in match_ids if m not in existing_matches]

    print(f"🚀 Remaining matches: {len(remaining)}")

    for game_id in remaining:

        process_match(
            game_id,
            schedule_map[game_id],
            player_map
        )

    print("\n🎉 DONE — FULL SEASON INGESTED")


# ---------------- ENTRY ---------------- #

if __name__ == "__main__":
    run()
