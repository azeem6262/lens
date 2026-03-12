import os
import pandas as pd
import unicodedata
from supabase import create_client
from dotenv import load_dotenv
from thefuzz import process, fuzz

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- UPGRADE 1: Helper to remove accents ---
def normalize_name(name):
    if not name: return ""
    return unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def safe_num(val, func=float):
    try:
        if pd.isna(val) or val == '' or val == 'N/A':
            return 0.0
        return func(float(val))
    except:
        return 0.0
        
def parse_market_value(val_str):
    """
    Robustly handles Transfermarkt strings: €65.00m, €400k, 1.5, etc.
    Returns a clean BIGINT for Supabase.
    """
    if not val_str or pd.isna(val_str) or val_str == '-' or val_str == 0:
        return 0
    
    # Remove symbols and convert to lowercase for uniform processing
    clean_val = str(val_str).replace('€', '').strip().lower()
    
    multiplier = 1
    if 'm' in clean_val:
        multiplier = 1_000_000
        clean_val = clean_val.replace('m', '')
    elif 'k' in clean_val:
        multiplier = 1_000
        clean_val = clean_val.replace('k', '')
        
    try:
        # float() handles decimals like "1.50"; multiplier scales it up
        return int(float(clean_val) * multiplier)
    except (ValueError, TypeError):
        return 0

def run_master_fusion():
    csv_path = "../data/players_data-2025_2026.csv" 
    if not os.path.exists(csv_path): 
        print(f"❌ CSV not found at {csv_path}")
        return

    # Load and prepare CSV
    df = pd.read_csv(csv_path).fillna(0)
    df.columns = df.columns.str.strip() 
    df['Squad'] = df['Squad'].astype(str).str.strip()
    df['normalized_player'] = df['Player'].apply(normalize_name)

    team_mapping = {
        "Juventus FC": "Juventus", "FC Toulouse": "Toulouse", "Atalanta BC": "Atalanta",
        "Borussia Mönchengladbach": "Gladbach", "Paris Saint-Germain": "Paris S-G",
        "Eintracht Frankfurt": "Eint Frankfurt", "Manchester United": "Manchester Utd",
        "Newcastle United": "Newcastle Utd", "Nottingham Forest": "Nott'ham Forest",
        "Athletic Bilbao": "Athletic Club", "Wolverhampton Wanderers": "Wolves",
        "Real Betis Balompié": "Betis", "Celta de Vigo": "Celta Vigo",
        "AC Milan": "Milan", "Inter Milan": "Inter",
        "Hellas Verona": "Verona", "VfL Wolfsburg": "Wolfsburg", "RB Leipzig": "Leipzig"
    }

    # --- UPGRADE 2: Pagination Logic (Fetch > 1000 players) ---
    print("📡 Fetching all players from database...")
    all_players = []
    chunk_size = 1000
    start = 0

    while True:
        res = supabase.table("players").select("tm_id, name, club, position_group").range(start, start + chunk_size - 1).execute()
        chunk = res.data
        all_players.extend(chunk)
        if len(chunk) < chunk_size:
            break
        start += chunk_size

    db_players = pd.DataFrame(all_players)
    print(f"📊 Total database players fetched: {len(db_players)}")

    final_payloads = {"Attacker": [], "Midfielder": [], "Defender": [], "Goalkeeper": []}
    match_count = 0

    for _, row in db_players.iterrows():
        tm_name, tm_id, tm_club, target_group = str(row['name']), row['tm_id'], str(row['club']), str(row['position_group'])
        
        # --- THE TRUTH LOG (Strict Match for Audit) ---
        if tm_name == "Jonathan David":
            print(f"🎯 FOUND IN DB: {tm_name} | ID: {tm_id} | Group: {target_group}")

        if target_group not in final_payloads: 
            continue

        tm_norm = normalize_name(tm_name)
        mapped_club = team_mapping.get(tm_club.strip(), tm_club.strip())
        
        # SQUAD SEARCH
        search_df = df[df['Squad'].str.contains(mapped_club, case=False, na=False)]
        
        if not search_df.empty:
            choices = search_df['normalized_player'].tolist()
            original_names = search_df['Player'].tolist()
            pool_df = search_df
            threshold = 65 
        else:
            choices = df['normalized_player'].tolist()
            original_names = df['Player'].tolist()
            pool_df = df
            threshold = 85

        match_norm, score = process.extractOne(tm_norm, choices, scorer=fuzz.WRatio)

        if score >= threshold:
            idx = choices.index(match_norm)
            p = pool_df[pool_df['Player'] == original_names[idx]].iloc[0]
            
            
            if tm_name == "Jonathan David":
                print(f"✅ MATCH SUCCESS: {tm_name} matched in CSV with {original_names[idx]} (Score: {score})")
                print(f"📈 DATA CHECK: Mins in CSV for this player: {p.get('Min')}")

            nineties = safe_num(p.get('90s', 0))
            if nineties < 0.1: nineties = 0.1

            
            # Push age update immediately
            supabase.table("players") \
                .update({
                    "age": safe_num(p.get('Age', 0), int),
                    "name": tm_name
                }) \
               .eq("tm_id", tm_id) \
            .execute()
            
            # Extract goals and assists (CRITICAL FIX)
            gls = safe_num(p.get('Gls', 0))
            ast = safe_num(p.get('Ast', 0))
            sh = safe_num(p.get('Sh', 0))
            
            record = {
                "tm_id": tm_id,
                "scraped_at": "now()",
                "total_minutes": safe_num(p.get('Min', 0)),
                "nineties": round(nineties, 2),
                "yellow_cards": safe_num(p.get('CrdY', 0)),
                "red_cards": safe_num(p.get('CrdR', 0)),
            }
            
            # COMMON FIELDS FOR ATTACKERS, MIDFIELDERS, DEFENDERS
            if target_group in ["Attacker", "Midfielder", "Defender"]:
                record.update({
                    "goals_scored": int(gls),  # Total goals
                    "assists_provided": int(ast),  # Total assists
                    "npxg": safe_num(p.get('npxG', 0)),
                    "xa": safe_num(p.get('xAG', 0)),
                    "progressive_passes_per_90": round(safe_num(p.get('PrgP', 0)) / nineties, 3),
                    "key_passes_per_90": round(safe_num(p.get('KP', 0)) / nineties, 3),
                    "pass_completion_pct": safe_num(p.get('Cmp%', 0))
                })

            # POSITION-SPECIFIC FIELDS
            if target_group == "Attacker":
                record.update({
                    "goals_per_90": round(gls / nineties, 3),  # CRITICAL: Per-90 for scatter plot
                    "assists_per_90": round(ast / nineties, 3),  # CRITICAL: Per-90 for scatter plot
                    "xa_per_90": round(safe_num(p.get('xAG', 0)) / nineties, 3),
                    "conversion_rate": round((gls / max(sh, 1)) * 100, 2),
                    "npxg_per_90": round(safe_num(p.get('npxG', 0)) / nineties, 3),
                    "shots_per_90": round(sh / nineties, 3),
                    "passes_into_penalty_area_per_90": round(safe_num(p.get('PPA', 0)) / nineties, 3),
                    "miscontrols_per_90": round(safe_num(p.get('Mis', 0)) / nineties, 3),
                    "progressive_runs_per_90": round(safe_num(p.get('PrgR', 0)) / nineties, 3),
                    "sca_per_90": round(safe_num(p.get('SCA', 0)) / nineties, 3)
                })
                
            elif target_group == "Midfielder":
                record.update({
                    "goals_per_90": round(gls / nineties, 3),  # CRITICAL: Per-90 for scatter plot
                    "assists_per_90": round(ast / nineties, 3),  # CRITICAL: Per-90 for scatter plot
                    "xa_per_90": round(safe_num(p.get('xAG', 0)) / nineties, 3),
                    "npxg_per_90": round(safe_num(p.get('npxG', 0)) / nineties, 3),
                    "conversion_rate": round((gls / max(sh, 1)) * 100, 2),
                    "passes_into_penalty_area_per_90": round(safe_num(p.get('PPA', 0)) / nineties, 3),
                    "progressive_runs_per_90": round(safe_num(p.get('PrgR', 0)) / nineties, 3),
                    "miscontrols_per_90": round(safe_num(p.get('Mis', 0)) / nineties, 3),
                    "blocks_per_90": round(safe_num(p.get('Blocks', 0)) / nineties, 3),
                    "clearances_per_90": round(safe_num(p.get('Clr', 0)) / nineties, 3),
                    "penalties_won": safe_num(p.get('PKwon', 0)),
                    "errors_leading_to_goal_per_90": round(safe_num(p.get('Err', 0)) / nineties, 3)
                })
                
            elif target_group == "Defender":
                aw, al = safe_num(p.get('Won_stats_miscellaneous', 0)), safe_num(p.get('Lost_stats_miscellaneous', 0))
                tk, it = safe_num(p.get('Tkl_stats_defensive_actions', 0)), safe_num(p.get('Int_stats_defensive_actions', 0))
                record.update({
                    "aerial_duel_win_pct": round((aw / max(aw + al, 1)) * 100, 2),
                    "tackles_interceptions_per_90": round((tk + it) / nineties, 3),
                    "progressive_runs_per_90": round(safe_num(p.get('PrgR', 0)) / nineties, 3),
                    "miscontrols_per_90": round(safe_num(p.get('Mis', 0)) / nineties, 3),
                    "tackles_per_90": round(tk / nineties, 3),
                    "interceptions_per_90": round(it / nineties, 3),
                    "clearances_per_90": round(safe_num(p.get('Clr', 0)) / nineties, 3),
                    "errors_leading_to_goal_per_90": round(safe_num(p.get('Err', 0)) / nineties, 3)
                })
                
            elif target_group == "Goalkeeper":
                mp, cs = safe_num(p.get('MP', 0)), safe_num(p.get('CS', 0))
                record.update({
                    "save_pct": safe_num(p.get('Save%', 0)),
                    "clean_sheets": cs,
                    "clean_sheets_pct": round((cs / max(mp, 1)) * 100, 2),
                    "goals_conceded_per_90": round(safe_num(p.get('GA', 0)) / nineties, 3),
                    "psxg_minus_ga": round(safe_num(p.get('PSxG+/-', 0)) / nineties, 3),
                    "penalties_faced": safe_num(p.get('PKatt', 0)),
                    "penalties_saved": safe_num(p.get('PKsv', 0)),
                    "errors_leading_to_goal_per_90": round(safe_num(p.get('Err', 0)) / nineties, 3)
                })

            final_payloads[target_group].append(record)
            match_count += 1

    # Batch Upsert
    for group, records in final_payloads.items():
        if records:
            table_name = f"stats_{group.lower()}s"
            print(f"📤 Pushing {len(records)} {group}s to {table_name}...")
            for i in range(0, len(records), 500):
                supabase.table(table_name).upsert(records[i:i+500], on_conflict="tm_id").execute()

    print(f"✅ Master Fusion Complete. Updated {match_count} players.")

if __name__ == "__main__":
    run_master_fusion()