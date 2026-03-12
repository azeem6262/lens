import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv

from mplsoccer import Pitch, FontManager
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec

# ---------------- SETUP ---------------- #

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    font_bold = FontManager('https://raw.githubusercontent.com/google/fonts/main/ofl/Anton/Anton-Regular.ttf')
    font_regular = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Regular.ttf')
except Exception as e:
    print(f"⚠️ Font loading failed: {e}")
    font_bold = None
    font_regular = None

# ---------------- COLORMAP ---------------- #
# CRITICAL: No black/dark at any point. Goes straight from transparent
# to green, then yellow, orange, red. This gives the smooth reference look.

heatmap_cmap = LinearSegmentedColormap.from_list(
    "smooth_heat",
    [
        (0.00, (0.18, 0.55, 0.24, 0.0)),   # fully transparent (pitch green, alpha=0)
        (0.20, (0.18, 0.55, 0.24, 0.0)),   # still transparent up to 20% density
        (0.35, (1.00, 1.00, 0.00, 0.7)),   # yellow, semi-transparent
        (0.60, (1.00, 0.50, 0.00, 0.85)),  # orange
        (0.80, (1.00, 0.10, 0.00, 0.95)),  # red
        (1.00, (0.80, 0.00, 0.00, 1.00)),  # deep red
    ],
    N=512
)

# ---------------- FETCH DATA ---------------- #

def get_player_uuid(player_name):
    res = supabase.table("players_master").select("id, name").ilike("name", player_name).limit(1).execute()
    if not res.data:
        raise Exception(f"Player '{player_name}' not found.")
    return res.data[0]["id"], res.data[0]["name"]

def get_player_events(player_uuid):
    res = supabase.table("match_events").select("x, y").eq("player_id", player_uuid).execute()
    df = pd.DataFrame(res.data)
    df = df.dropna(subset=["x", "y"])
    df['x'] = pd.to_numeric(df['x'])
    df['y'] = pd.to_numeric(df['y'])
    return df

def get_player_club(player_uuid):
    res = supabase.table("players_master")\
        .select("club_id, clubs_master(name)")\
        .eq("id", player_uuid)\
        .limit(1)\
        .execute()
    try:
        return res.data[0]["clubs_master"]["name"].upper()
    except:
        return ""

# ---------------- VISUALIZATION ---------------- #

def plot_heatmap(df, player_name, club_name="", season="2024/25"):
    if df.empty:
        print(f"⚠️ No event data found for {player_name}.")
        return

    bold_prop = font_bold.prop if font_bold else None
    reg_prop = font_regular.prop if font_regular else None

    BG_COLOR     = '#ffffff'
    TEXT_COLOR   = '#111111'
    SUBTEXT_COLOR= '#444444'
    ACCENT_COLOR = '#cc0000'
    PITCH_LINE   = '#ffffff'
    PITCH_COLOR  = '#1e6b2e'  # darker green so cool regions contrast

    fig = plt.figure(figsize=(10, 13), facecolor=BG_COLOR)
    gs  = GridSpec(3, 1, figure=fig, height_ratios=[1.4, 5, 0.6], hspace=0.05)

    ax_title  = fig.add_subplot(gs[0])
    ax_pitch  = fig.add_subplot(gs[1])
    ax_footer = fig.add_subplot(gs[2])

    for ax in [ax_title, ax_footer]:
        ax.set_facecolor(BG_COLOR)
        ax.axis('off')

    # ---------------- TITLE ---------------- #

    ax_title.text(0.5, 0.78, "HEAT MAP",
        fontproperties=bold_prop, fontsize=56,
        color=TEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes, fontweight='bold')

    subtitle = player_name.upper()
    if club_name:
        subtitle += f"  |  {club_name}"

    ax_title.text(0.5, 0.38, subtitle,
        fontproperties=reg_prop, fontsize=15,
        color=SUBTEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes)

    ax_title.text(0.5, 0.10, f"{season}  •  {len(df)} Actions",
        fontproperties=reg_prop, fontsize=10,
        color=SUBTEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes, alpha=0.7)

    ax_title.axhline(y=0.0, color='#dddddd', linewidth=1, xmin=0.05, xmax=0.95)

    # ---------------- PITCH + HEATMAP ---------------- #


    pitch = Pitch(
        pitch_type='opta',
        pitch_color=PITCH_COLOR,
        line_color='#ffffff',
        linewidth=2.5,
        goal_type='box',
        corner_arcs=True
    )
    pitch.draw(ax=ax_pitch)
    ax_pitch.set_facecolor(PITCH_COLOR)

    # Draw heatmap (zorder=2 so it sits above pitch base)
    pitch.kdeplot(
        df['x'], df['y'],
        ax=ax_pitch,
        cmap=heatmap_cmap,
        fill=True,
        levels=200,
        alpha=1.0,
        zorder=2,
        bw_adjust=0.9,
        thresh=0.20
    )

    # After kdeplot, force ALL existing lines back to zorder=5 so they
    # are always visible on top of the heatmap
    for line in ax_pitch.get_lines():
        line.set_zorder(5)
        line.set_linewidth(2.5)
        line.set_color('#ffffff')

    # Also bring any patch/collection elements (goals, arcs) to front
    for patch in ax_pitch.patches:
        patch.set_zorder(5)
    for collection in ax_pitch.collections:
        if collection.get_zorder() < 3:
            collection.set_zorder(5)

    for spine in ax_pitch.spines.values():
        spine.set_visible(False)

    # ---------------- FOOTER ---------------- #

    ax_footer.set_facecolor(BG_COLOR)
    ax_footer.axhline(y=1.0, color='#dddddd', linewidth=1, xmin=0.05, xmax=0.95)

    ax_footer.text(0.5, 0.55,
        "LensPro Analytics  •  Data via WhoScored / Opta",
        fontproperties=reg_prop, fontsize=9,
        color=SUBTEXT_COLOR, ha='center', va='center',
        transform=ax_footer.transAxes, style='italic')

    ax_footer.text(0.5, 0.15, "LENSPRO",
        fontproperties=bold_prop, fontsize=11,
        color=ACCENT_COLOR, ha='center', va='center',
        transform=ax_footer.transAxes)

    plt.savefig("heatmap_output.png", dpi=150,
        bbox_inches='tight', facecolor=BG_COLOR, edgecolor='none')
    print("✅ Saved to heatmap_output.png")
    plt.show()


# ---------------- MAIN ---------------- #

def run(player_name, season="2024/25"):
    try:
        print(f"🔎 Searching for {player_name}...")
        uuid, full_name = get_player_uuid(player_name)
        print(f"✅ Found: {full_name} ({uuid})")
        club = get_player_club(uuid)
        print("📡 Fetching event locations...")
        df = get_player_events(uuid)
        print(f"✅ Loaded {len(df)} events")
        print("🎨 Generating heatmap...")
        plot_heatmap(df, full_name, club_name=club, season=season)
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    run("Dani Olmo")