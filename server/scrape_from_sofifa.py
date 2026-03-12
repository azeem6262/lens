import soccerdata as sd
import pandas as pd

# 1. Initialize for the 'Combined' leagues (MUCH more efficient)
fbref = sd.FBref(leagues="Big 5 European Leagues Combined", seasons="25-26")

print("🚀 Scraping FBref (Using 'Combined' mode to avoid bans)...")
try:
    # 2. Get Defensive stats (Tackles, Interceptions)
    defense_df = fbref.read_player_season_stats(stat_type='defense')
    defense_df.to_parquet("../data/fbref_defense.parquet")
    print(f"✅ Defense data saved ({len(defense_df)} players).")

    # 3. Get Standard stats (Minutes, to normalize the data)
    standard_df = fbref.read_player_season_stats(stat_type='standard')
    standard_df.to_parquet("../data/fbref_standard.parquet")
    print(f"✅ Standard data saved ({len(standard_df)} players).")

except Exception as e:
    print(f"❌ FBref still blocking: {e}")