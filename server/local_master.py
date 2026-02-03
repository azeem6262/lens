import soccerdata as sd
import pandas as pd
import os

def generate_master_files_understat():
    # 1. Initialize Understat (Much less likely to throw 403 errors)
    # We'll target the Big 5 leagues
    leagues = ["ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A", "FRA-Ligue 1"]
    
    try:
        print("--- Initializing Understat Global Scraper ---")
        us = sd.Understat(leagues=leagues, seasons="2025")
        
        # 2. Pull player season stats (One command gets everything: xG, xA, shots, etc.)
        print("Downloading all player stats from Understat...")
        players_df = us.read_player_season_stats().reset_index()

        # 3. Clean and Format for your Supabase DB
        # Understat columns are slightly different: 'expected_goals', 'expected_assists'
        print("Formatting data for Supabase...")
        
        # We rename to match your existing database field names
        master = players_df.rename(columns={
            'player': 'name',
            'expected_goals': 'npxg_per_90', # Understat npxG is very reliable
            'expected_assists': 'xa_per_90',
            'key_passes': 'sca_per_90' # Good proxy for shot creation
        })

        # 4. Save to Parquet
        os.makedirs("../data", exist_ok=True)
        output_path = "../data/master_stats_attackers.parquet"
        master.to_parquet(output_path, engine='pyarrow')
        
        print(f"--- SUCCESS ---")
        print(f"Saved {len(master)} players to {output_path}")

    except Exception as e:
        print(f"Understat Scrape Failed: {e}")

if __name__ == "__main__":
    generate_master_files_understat()