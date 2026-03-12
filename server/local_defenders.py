import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from thefuzz import process, fuzz

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def run_master_fusion():
    # 1. Load Data Sources
    # We use these to fill the gaps
    us_path = "../data/master_stats_attackers.parquet"
    sf_path = "../data/sofifa_attributes.parquet"
    
    us_df = pd.read_parquet(us_path) if os.path.exists(us_path) else None
    sf_df = pd.read_parquet(sf_path) if os.path.exists(sf_path) else None

    if sf_df is not None and isinstance(sf_df.columns, pd.MultiIndex):
        sf_df.columns = ['_'.join(col).strip() for col in sf_df.columns.values]

    # 2. Get Skeleton
    res = supabase.table("players").select("tm_id, name, position_group").execute()
    db_players = pd.DataFrame(res.data)

    final_payloads = {"Attacker": [], "Midfielder": [], "Defender": []}
    
    us_names = us_df['name'].tolist() if us_df is not None else []
    sf_names = sf_df['name'].tolist() if sf_df is not None else []

    print(f"🚀 Starting Smart Fusion...")

    for _, row in db_players.iterrows():
        tm_name, tm_id, group = row['name'], row['tm_id'], row['position_group']
        if not group or group not in final_payloads: continue

        # The 'record' only contains tm_id and the NEW fields we want to add/update
        record = {"tm_id": tm_id, "scraped_at": "now()"}

        # --- FILL DEFENSIVE GAPS (from SoFIFA) ---
        if sf_df is not None:
            sf_match, sf_score = process.extractOne(tm_name, sf_names, scorer=fuzz.token_sort_ratio)
            if sf_score >= 80:
                p_sf = sf_df[sf_df['name'] == sf_match].iloc[0]
                
                # Fill technical skills for Mids and Defs
                if group in ["Midfielder", "Defender"]:
                    # These are usually NULL right now
                    record["tackles_per_90"] = float(p_sf.get('standing_tackle', 0))
                    record["interceptions_per_90"] = float(p_sf.get('interceptions', 0))
                
                # For attackers, maybe you want to add 'finishing' or 'sprint_speed' later?
                # record["finishing"] = float(p_sf.get('finishing', 0))

        # --- FILL ATTACKING GAPS (from Understat - if not already done) ---
        if us_df is not None:
            us_match, us_score = process.extractOne(tm_name, us_names, scorer=fuzz.token_sort_ratio)
            if us_score >= 80:
                p_us = us_df[us_df['name'] == us_match].iloc[0]
                mins = float(p_us.get('minutes', 1))
                
                # Only map if record doesn't have it or to ensure accuracy
                if group == "Attacker":
                    record["npxg_per_90"] = round((float(p_us.get('np_xg', 0)) / mins) * 90, 3)
                    record["shots_per_90"] = round((float(p_us.get('shots', 0)) / mins) * 90, 3)
                
                record["xa_per_90"] = round((float(p_us.get('xa', 0)) / mins) * 90, 3)

        if len(record) > 2:
            final_payloads[group].append(record)

    # 3. Push Updates
    for group, records in final_payloads.items():
        if records:
            table_name = f"stats_{group.lower()}s"
            print(f"📤 Updating {len(records)} records in {table_name}...")
            # This UPSERT will only change the columns present in 'record'
            supabase.table(table_name).upsert(records, on_conflict="tm_id").execute()

    print("✅ Fusion Complete! Your Attacker stats are safe, and Mid/Def stats are now filled.")

if __name__ == "__main__":
    run_master_fusion()