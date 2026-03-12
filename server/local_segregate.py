import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_position_group(raw_position: str):
    pos = str(raw_position).lower()
    if any(x in pos for x in ["striker", "winger", "forward", "centre-forward"]):
        return "Attacker", "stats_attackers"
    if any(x in pos for x in ["midfield", "amc", "dmc", "cm", "mezzala"]):
        return "Midfielder", "stats_midfielders"
    if any(x in pos for x in ["back", "defender", "sweeper", "cb", "lb", "rb"]):
        return "Defender", "stats_defenders"
    if "goalkeeper" in pos:
        return "Goalkeeper", "stats_goalkeepers"
    return "Unknown", None

def run_industrial_segregation():
    print("Fetching player list from Supabase...")
    # 1. Pull the whole player list at once
    res = supabase.table("players")\
        .select("tm_id, position")\
        .is_("position_group", "null")\
        .execute()
    
    players = res.data

    if not players:
        print("🎉 No remaining players to segregate! You are 100% synced.")
        return

    print(f"Categorizing {len(players)} new players locally...")
    # Tables to populate
    groups = {
        "stats_attackers": [],
        "stats_midfielders": [],
        "stats_defenders": [],
        "stats_goalkeepers": []
    }
    
    # List for updating the master 'players' table
    master_updates = []

    print(f"Categorizing {len(players)} players locally...")
    for p in players:
        group, table_name = get_position_group(p['position'])
        
        if table_name:
            groups[table_name].append({"tm_id": p['tm_id']})
            master_updates.append({"tm_id": p['tm_id'], "position_group": group})

    # 2. Bulk Push to Specialized Tables
    for table, records in groups.items():
        if records:
            # Chunking to stay safe
            for i in range(0, len(records), 1000):
                chunk = records[i:i+1000]
                supabase.table(table).upsert(chunk, on_conflict="tm_id").execute()
            print(f"✅ Synced {len(records)} to {table}")

    # 3. Bulk Update the Master 'players' table
    if master_updates:
        print(f"Updating position groups for {len(master_updates)} players...")
        for p_update in master_updates:
            try:
                # We use .update() instead of .upsert() 
                # This only touches the position_group column and leaves 'name' alone
                supabase.table("players")\
                    .update({"position_group": p_update["position_group"]})\
                    .eq("tm_id", p_update["tm_id"])\
                    .execute()
            except Exception as e:
                print(f"Error updating tm_id {p_update['tm_id']}: {e}")
                continue
        print(f"🚀 Master 'players' table updated with position groups.")

if __name__ == "__main__":
    run_industrial_segregation()