import os
import pandas as pd
import unicodedata
from thefuzz import process, fuzz

# Helper to remove accents
def normalize_name(name):
    if not name: return ""
    return unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

def run_diagnostic():
    csv_path = "../data/players_data-2025_2026.csv"
    if not os.path.exists(csv_path):
        print("❌ CSV ERROR: File not found at ../data/players_data-2025_2026.csv")
        return

    # Load and peek at headers
    df = pd.read_csv(csv_path).fillna(0)
    print("📋 CSV HEADERS FOUND:", list(df.columns[:15])) # Print first 15 columns
    
    # We will test 5 specific "0 min" stars from your list
    test_players = [
        {"name": "Michele Di Gregorio", "club": "Juventus FC"},
        {"name": "Jonathan David", "club": "Juventus FC"},
        {"name": "Victor Nelsson", "club": "Hellas Verona"},
        {"name": "Abdou Harroui", "club": "Hellas Verona"},
        {"name": "Kenan Yıldız", "club": "Juventus FC"}
    ]

    team_mapping = {
        "Juventus FC": "Juventus",
        "Hellas Verona": "Verona",
        "VfL Wolfsburg": "Wolfsburg",
        "RB Leipzig": "Leipzig"
    }

    print(f"\n{'[DB PLAYER]':<25} | {'[SQUAD SEARCH]':<15} | {'[CSV MATCH]':<22} | {'[SCORE]':<5} | {'[MINS]'}")
    print("-" * 100)

    for p in test_players:
        tm_name = p['name']
        tm_club = p['club']
        tm_norm = normalize_name(tm_name)
        mapped_club = team_mapping.get(tm_club, tm_club)

        # 🔍 STEP 1: Squad Filter
        search_df = df[df['Squad'].str.contains(mapped_club, case=False, na=False)]
        squad_status = "FOUND" if not search_df.empty else "EMPTY"

        # 🔍 STEP 2: Matching
        if not search_df.empty:
            choices = search_df['Player'].tolist()
            pool_df = search_df
        else:
            choices = df['Player'].tolist()
            pool_df = df

        match, score = process.extractOne(tm_name, choices, scorer=fuzz.WRatio)
        
        # 🔍 STEP 3: Data Extraction
        p_row = pool_df[pool_df['Player'] == match].iloc[0]
        
        # We check multiple common variations of 'Minutes' columns
        mins_val = p_row.get('Min', 'MISSING')
        alt_mins = p_row.get('Minutes', 'MISSING')
        print("DEBUG:", normalize("Paris Saint-Germain"))
        print(f"{tm_name:<25} | {mapped_club:<15} ({squad_status}) | {match:<22} | {score:<5} | Min: {mins_val}, Minutes: {alt_mins}")

if __name__ == "__main__":
    run_diagnostic()