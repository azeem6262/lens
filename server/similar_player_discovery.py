import os
import pandas as pd
import numpy as np
from supabase import create_client
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def run_clone_discovery():
    print("🧠 Initializing Neural Clone Discovery...")
    
    # 1. Fetch current stats (Starting with Midfielders)
    res = supabase.table("stats_midfielders").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if df.empty: return print("❌ Database is empty. Sync data first.")

    # 2. Select "Style-Defining" Columns
    # We use these to calculate the 'Genetic Match'
    style_features = [
        'progressive_passes_per_90', 'pass_completion_pct', 
        'sca_per_90', 'touches_per_90', 'xa_per_90'
    ]
    
    # 3. Standardize & Calculate Similarity
    scaler = StandardScaler()
    matrix = scaler.fit_transform(df[style_features].fillna(0))
    sim_scores = cosine_similarity(matrix)
    
    payload = []

    for i, row in df.iterrows():
        # Find 3 most similar players (excluding self)
        # We sort the similarity scores for that player and pick the top indices
        top_indices = sim_scores[i].argsort()[-4:-1][::-1]
        
        clones = []
        for idx in top_indices:
            match = df.iloc[idx]
            clones.append({
                "tm_id": int(match['tm_id']),
                "match_score": round(float(sim_scores[i][idx]) * 100, 1)
            })
            
        payload.append({
            "tm_id": int(row['tm_id']),
            "similarity_clones": clones,
            "tactical_dna_flags": ["High-Volume Pivot"] if row['touches_per_90'] > 75 else ["Advanced Creator"]
        })

    # 4. Push to Intelligence Layer
    print(f"📤 Pushing intelligence profiles for {len(payload)} players...")
    supabase.table("player_intelligence").upsert(payload).execute()
    print("✅ Clone Engine Complete.")

if __name__ == "__main__":
    run_clone_discovery()