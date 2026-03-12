import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from mplsoccer import Pitch, FontManager
from supabase import create_client
from dotenv import load_dotenv

# ---------------- SETUP ---------------- #
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    robotto_regular = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Regular.ttf')
    robotto_bold = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Bold.ttf')
except:
    robotto_regular = None
    robotto_bold = None

def get_player_data(player_name, event_type="is_key_pass"):
    p_res = supabase.table("players_master").select("id").ilike("name", player_name).limit(1).execute()
    if not p_res.data: raise Exception(f"Player '{player_name}' not found.")
    player_id = p_res.data[0]["id"]

    e_res = supabase.table("match_events").select("x, y, period").eq("player_id", player_id).eq(event_type, True).execute()
    df = pd.DataFrame(e_res.data)
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    
    df['x'] = pd.to_numeric(df['x'])
    df['y'] = pd.to_numeric(df['y'])
    return df[df['period'] == 'FirstHalf'].copy(), df[df['period'] == 'SecondHalf'].copy()

# ---------------- PLOT FUNCTION ---------------- #

def plot_spatial_delta(player_name, event_label="Key Passes"):
    df1, df2 = get_player_data(player_name, "is_key_pass")
    if df1.empty and df2.empty:
        print(f"⚠️ No data for {player_name}.")
        return

    # 1. Setup Pitch
    pitch = Pitch(pitch_type='opta', line_zorder=2, pitch_color='#1a1a1a', line_color='#444444')
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.set_facecolor('#1a1a1a')

    # 2. Binning logic
    bin1 = pitch.bin_statistic(df1.x, df1.y, statistic='count', bins=(6, 3))
    bin2 = pitch.bin_statistic(df2.x, df2.y, statistic='count', bins=(6, 3))

    # Calculate Percentages
    total1, total2 = bin1['statistic'].sum(), bin2['statistic'].sum()
    pct1 = (bin1['statistic'] / total1 * 100) if total1 > 0 else np.zeros_like(bin1['statistic'])
    pct2 = (bin2['statistic'] / total2 * 100) if total2 > 0 else np.zeros_like(bin2['statistic'])

    # 3. Calculate Delta and Replace Statistic in bin object
    delta_pct = pct2 - pct1
    bin1['statistic'] = delta_pct # We use bin1 as the template for coordinates

    # 4. Corrected Heatmap call
    # Use modern colormap call to avoid deprecation warning
    cmap = plt.get_cmap('RdYlGn')
    pcm = pitch.heatmap(bin1, cmap=cmap, ax=ax, alpha=0.7, edgecolor='#1a1a1a')

    # Add labels to zones
    path_effects_glow = [path_effects.withStroke(linewidth=2, foreground='#1a1a1a')]
    for i in range(bin1['cx'].shape[1]):
        for j in range(bin1['cx'].shape[0]):
            val = delta_pct[j, i]
            if abs(val) > 0.1:
                ax.text(bin1['cx'][j, i], bin1['cy'][j, i], f"{val:+.1f}%", 
                        color='white', ha='center', va='center', fontsize=12,
                        fontproperties=robotto_regular.prop if robotto_regular else None,
                        path_effects=path_effects_glow)

    # 5. Professional Titles & Watermark
    title_font = robotto_bold.prop if robotto_bold else None
    ax.set_title(f"{player_name.upper()}: SPATIAL {event_label.upper()} DELTA", 
                 fontsize=22, color='white', fontproperties=title_font, pad=30)

    # Subtitle
    delta_val = int(total2 - total1)
    fig.text(0.5, 0.88, f"Second Half vs. First Half | Total Change: {'+' if delta_val >= 0 else ''}{delta_val}",
             ha='center', fontsize=14, color='#c7d5e0', fontproperties=robotto_regular.prop if robotto_regular else None)

    # Pro Watermark (Large, centered, 10% opacity)
    fig.text(0.5, 0.5, 'LENSPRO ANALYTICS', fontsize=70, color='white', ha='center', va='center', 
             alpha=0.08, rotation=25, fontproperties=title_font)

    plt.show()

if __name__ == "__main__":
    run_name = "Bruno Fernandes" # Ensure this player has match_events data!
    plot_spatial_delta(run_name, "Key Passes")