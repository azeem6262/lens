import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from mplsoccer import Pitch, FontManager
from supabase import create_client
from dotenv import load_dotenv

# ---------------- SETUP ---------------- #
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    font_bold    = FontManager('https://raw.githubusercontent.com/google/fonts/main/ofl/Anton/Anton-Regular.ttf')
    font_regular = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Regular.ttf')
except Exception as e:
    print(f"⚠️ Font loading failed: {e}")
    font_bold    = None
    font_regular = None

# ---------------- THEME ---------------- #
BG_COLOR      = '#ffffff'
TEXT_COLOR    = '#111111'
SUBTEXT_COLOR = '#444444'
ACCENT_COLOR  = '#cc0000'
PITCH_COLOR   = '#1e6b2e'
PITCH_LINE    = '#ffffff'
SUCC_COLOR    = '#00c853'   # clean green for successful
FAIL_COLOR    = '#cc0000'   # red for unsuccessful

# ---------------- DATA ---------------- #

def get_player_info(player_name):
    res = supabase.table("players_master")\
        .select("id, name, club_id, clubs_master(name)")\
        .ilike("name", player_name).limit(1).execute()
    if not res.data:
        raise Exception(f"Player '{player_name}' not found.")
    row = res.data[0]
    club = ""
    try:
        club = row["clubs_master"]["name"].upper()
    except:
        pass
    return row["id"], row["name"], club

def get_pass_data(player_id):
    res = supabase.table("match_events")\
        .select("x, y, end_x, end_y, outcome")\
        .eq("player_id", player_id)\
        .eq("event_type", "Pass")\
        .execute()

    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df.dropna(subset=['x', 'y', 'end_x', 'end_y'])
    df[['x','y','end_x','end_y']] = df[['x','y','end_x','end_y']].apply(pd.to_numeric)

    succ = df[df['outcome'] == 'Successful'].copy()
    fail = df[df['outcome'] == 'Unsuccessful'].copy()
    return succ, fail

# ---------------- PLOT ---------------- #

def plot_pass_map(player_name, season="2024/25"):
    player_id, full_name, club_name = get_player_info(player_name)
    succ_df, fail_df = get_pass_data(player_id)

    total = len(succ_df) + len(fail_df)
    if total == 0:
        print(f"⚠️ No pass data found for {full_name}.")
        return

    completion = len(succ_df) / total * 100

    bold_prop = font_bold.prop    if font_bold    else None
    reg_prop  = font_regular.prop if font_regular else None

    fig = plt.figure(figsize=(10, 13), facecolor=BG_COLOR)
    gs  = GridSpec(3, 1, figure=fig, height_ratios=[1.4, 5, 0.6], hspace=0.05)

    ax_title  = fig.add_subplot(gs[0])
    ax_pitch  = fig.add_subplot(gs[1])
    ax_footer = fig.add_subplot(gs[2])

    for ax in [ax_title, ax_footer]:
        ax.set_facecolor(BG_COLOR)
        ax.axis('off')

    # ---------------- TITLE ---------------- #

    ax_title.text(0.5, 0.78, "PASS MAP",
        fontproperties=bold_prop, fontsize=56,
        color=TEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes, fontweight='bold')

    subtitle = full_name.upper()
    if club_name:
        subtitle += f"  |  {club_name}"

    ax_title.text(0.5, 0.38, subtitle,
        fontproperties=reg_prop, fontsize=15,
        color=SUBTEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes)

    ax_title.text(0.5, 0.10,
        f"{season}  •  {total} Passes  •  {completion:.1f}% Completion",
        fontproperties=reg_prop, fontsize=10,
        color=SUBTEXT_COLOR, ha='center', va='center',
        transform=ax_title.transAxes, alpha=0.7)

    ax_title.axhline(y=0.0, color='#dddddd', linewidth=1, xmin=0.05, xmax=0.95)

    # ---------------- PITCH ---------------- #

    pitch = Pitch(
        pitch_type='opta',
        pitch_color=PITCH_COLOR,
        line_color=PITCH_LINE,
        linewidth=2.5,
        goal_type='box',
        corner_arcs=True
    )
    pitch.draw(ax=ax_pitch)
    ax_pitch.set_facecolor(PITCH_COLOR)

    # Unsuccessful passes drawn first (underneath)
    if not fail_df.empty:
        pitch.arrows(
            fail_df.x, fail_df.y,
            fail_df.end_x, fail_df.end_y,
            ax=ax_pitch,
            color=FAIL_COLOR, alpha=0.5,
            width=1.5, headwidth=4, headlength=4,
            zorder=2
        )

    # Successful passes on top
    if not succ_df.empty:
        pitch.arrows(
            succ_df.x, succ_df.y,
            succ_df.end_x, succ_df.end_y,
            ax=ax_pitch,
            color=SUCC_COLOR, alpha=0.6,
            width=1.5, headwidth=4, headlength=4,
            zorder=3
        )

    # Force pitch lines on top of arrows
    for line in ax_pitch.get_lines():
        line.set_zorder(5)
        line.set_linewidth(2.5)
        line.set_color(PITCH_LINE)
    for patch in ax_pitch.patches:
        patch.set_zorder(5)

    # Legend — bottom left of pitch
    legend_elements = [
        Line2D([0], [0], color=SUCC_COLOR, lw=2,
               label=f'Successful  {len(succ_df)}'),
        Line2D([0], [0], color=FAIL_COLOR, lw=2,
               label=f'Unsuccessful  {len(fail_df)}')
    ]
    legend = ax_pitch.legend(
        handles=legend_elements,
        loc='lower left',
        facecolor='#ffffffcc',
        edgecolor='#dddddd',
        labelcolor=TEXT_COLOR,
        prop=reg_prop,
        fontsize=11,
        framealpha=0.9
    )
    legend.set_zorder(6)

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

    plt.savefig("passmap_output.png", dpi=150,
        bbox_inches='tight', facecolor=BG_COLOR, edgecolor='none')
    print("✅ Saved to passmap_output.png")
    plt.show()


# ---------------- ENTRY ---------------- #

def run(player_name, season="2024/25"):
    try:
        print(f"🔎 Searching for {player_name}...")
        plot_pass_map(player_name, season=season)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run("Bruno Fernandes")