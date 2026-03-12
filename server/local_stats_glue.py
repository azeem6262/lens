import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from thefuzz import process, fuzz

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def run_smart_stats_glue():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filename = "master_stats_attackers.parquet" 
    stats_path = os.path.join(base_dir, "data", filename)
    
    if not os.path.exists(stats_path):
        print(f"❌ Error: File not found at {stats_path}")
        return
    
    # 1. Load Data
    stats_df = pd.read_parquet(stats_path)
    print(f"📊 Loaded {len(stats_df)} players from Parquet.")

    # 2. Fetch from Supabase
    res = supabase.table("players").select("tm_id, name, position_group").execute()
    db_players = pd.DataFrame(res.data)
    print(f"🏠 Fetched {len(db_players)} players from Supabase.")

    # 3. Precision Mapping (Matching your exact Parquet columns)
    schema_map = {
        "Attacker": {"npxg_per_90": "np_xg", "xa_per_90": "xa", "shots_per_90": "shots"},
        "Midfielder": {"xa_per_90": "xa", "sca_per_90": "sca_per_90", "xg_chain_per_90": "xg_chain"},
        "Defender": {"xg_buildup_per_90": "xg_buildup", "xg_chain_per_90": "xg_chain"}
    }

    final_payloads = {"Attacker": [], "Midfielder": [], "Defender": []}
    understat_names = stats_df['name'].astype(str).tolist()
    match_count = 0

    print("🔍 Matching & Normalizing...")
    for _, row in db_players.iterrows():
        tm_name, tm_id, group = row['name'], row['tm_id'], row['position_group']
        if not group or group not in schema_map: continue

        best_match, score = process.extractOne(tm_name, understat_names, scorer=fuzz.token_sort_ratio)

        if score >= 75:
            p_stats = stats_df[stats_df['name'] == best_match].iloc[0]
            
            # Use the exact 'minutes' column we found
            mins = float(p_stats.get('minutes', 0))
            if mins < 45: continue 

            record = {"tm_id": tm_id, "scraped_at": "now()"}
            
            for db_col, us_col in schema_map[group].items():
                if us_col in p_stats:
                    val = float(p_stats[us_col]) if pd.notnull(p_stats[us_col]) else 0.0
                    
                    # If column name already contains 'per_90', don't divide!
                    if "_per_90" in us_col and us_col != "sca_per_90":
                        record[db_col] = round(val, 3)
                    else:
                        # Force normalization for SCA and any other total-based columns
                        record[db_col] = round((val / mins) * 90, 3)
            
            final_payloads[group].append(record)
            match_count += 1

    # 4. Push
    for group, records in final_payloads.items():
        if records:
            table_name = f"stats_{group.lower()}s"
            print(f"📤 Pushing {len(records)} {group}s to {table_name}...")
            try:
                for i in range(0, len(records), 500):
                    supabase.table(table_name).upsert(records[i:i+500], on_conflict="tm_id").execute()
            except Exception as e:
                print(f"⚠️ Error in {table_name}: {e}")

    print(f"✅ Mission Complete! Matched and normalized {match_count} players.")

if __name__ == "__main__":
    run_smart_stats_glue()