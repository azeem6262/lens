import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from mplsoccer import Pitch, FontManager
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    font_bold    = FontManager('https://raw.githubusercontent.com/google/fonts/main/ofl/Anton/Anton-Regular.ttf')
    font_regular = FontManager('https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Regular.ttf')
except:
    font_bold = font_regular = None

BG         = '#ffffff'
TEXT       = '#111111'
SUBTEXT    = '#555555'
ACCENT     = '#cc0000'
PITCH_COL  = '#1e6b2e'
PITCH_LINE = '#ffffff'
COL_GOAL    = '#cc0000'
COL_SAVED   = '#4a90d9'
COL_MISSED  = '#aaaaaa'
COL_BLOCKED = '#f5a623'
COL_POST    = '#9b59b6'

SIT_COLS = {
    'OpenPlay':       '#1e6b2e',
    'FromCorner':     '#4a90d9',
    'SetPiece':       '#f5a623',
    'DirectFreekick': '#cc0000',
}
SIT_LABELS = {
    'OpenPlay':       'Open Play',
    'FromCorner':     'From Corner',
    'SetPiece':       'Set Piece',
    'DirectFreekick': 'Direct FK',
}

def result_colour(r):
    if r == 'Goal':        return COL_GOAL,    True,  0.95
    if r == 'SavedShot':   return COL_SAVED,   False, 0.75
    if r == 'MissedShots': return COL_MISSED,  False, 0.60
    if r == 'BlockedShot': return COL_BLOCKED, False, 0.65
    if r == 'ShotOnPost':  return COL_POST,    False, 0.80
    return COL_MISSED, False, 0.50

def get_player_info(player_name):
    res = supabase.table("players_master")\
        .select("id, name, club_id, clubs_master(name)")\
        .ilike("name", player_name).limit(1).execute()
    if not res.data:
        raise Exception(f"Player '{player_name}' not found.")
    row  = res.data[0]
    club = ""
    try:
        club = row["clubs_master"]["name"].upper()
    except:
        pass
    return row["id"], row["name"], club

def get_shot_data(player_id):
    res = supabase.table("understat_shots")\
        .select("x, y, xg, result, situation, shot_type, last_action, minute")\
        .eq("player_id", player_id).execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    df = df.dropna(subset=["x","y","xg"])
    df["x"]  = pd.to_numeric(df["x"]) * 100
    df["y"]  = pd.to_numeric(df["y"]) * 100
    df["xg"] = pd.to_numeric(df["xg"])
    return df

def plot_shot_profile(player_name, competition="Premier League", season="2024/25"):
    player_id, full_name, club_name = get_player_info(player_name)
    df = get_shot_data(player_id)
    if df.empty:
        print(f"No shot data for {full_name}")
        return

    goals     = int((df["result"] == "Goal").sum())
    total     = len(df)
    total_xg  = df["xg"].sum()
    xg_diff   = goals - total_xg
    avg_xg    = df["xg"].mean()
    on_target = int(df["result"].isin(["Goal","SavedShot"]).sum())
    sot_pct   = on_target / total * 100 if total else 0

    bold_prop = font_bold.prop    if font_bold    else None
    reg_prop  = font_regular.prop if font_regular else None

    # ---- Layout: 5 rows ----
    # 0: title
    # 1: pitch + zone grid
    # 2: situation bar
    # 3: situation legend
    # 4: stat cards
    # 5: footer
    fig = plt.figure(figsize=(14, 15), facecolor=BG)
    gs = GridSpec(6, 2, figure=fig,
        height_ratios=[2.2, 5, 0.5, 0.5, 1.6, 0.4],
        width_ratios=[1.15, 0.85],
        hspace=0.12, wspace=0.06)

    ax_title   = fig.add_subplot(gs[0, :])
    ax_pitch   = fig.add_subplot(gs[1, 0])
    ax_zone    = fig.add_subplot(gs[1, 1])
    ax_sitbar  = fig.add_subplot(gs[2, :])
    ax_sitleg  = fig.add_subplot(gs[3, :])
    ax_stats   = fig.add_subplot(gs[4, :])
    ax_footer  = fig.add_subplot(gs[5, :])

    for ax in [ax_title, ax_sitbar, ax_sitleg, ax_stats, ax_footer]:
        ax.set_facecolor(BG)
        ax.axis('off')

    # ================================================================
    # TITLE
    # ================================================================
    ax_title.text(0.02, 0.97, "SHOT PROFILE",
        fontproperties=bold_prop, fontsize=42,
        color=TEXT, ha='left', va='top',
        transform=ax_title.transAxes)

    subtitle = full_name.upper()
    if club_name:
        subtitle += f"  |  {club_name}"
    ax_title.text(0.02, 0.52, subtitle,
        fontproperties=reg_prop, fontsize=14,
        color=SUBTEXT, ha='left', va='top',
        transform=ax_title.transAxes)

    ax_title.text(0.02, 0.24,
        f"{competition}  •  {season}  •  {total} Shots  •  {goals} Goals  •  {total_xg:.2f} xG  •  xG Diff {xg_diff:+.2f}",
        fontproperties=reg_prop, fontsize=9.5,
        color=SUBTEXT, ha='left', va='top',
        transform=ax_title.transAxes, alpha=0.8)



    # ================================================================
    # LEFT: PITCH
    # ================================================================
    pitch = Pitch(pitch_type='opta', pitch_color=PITCH_COL,
        line_color=PITCH_LINE, linewidth=2.0,
        goal_type='box', corner_arcs=True, half=True)
    pitch.draw(ax=ax_pitch)
    ax_pitch.set_facecolor(PITCH_COL)

    for _, shot in df.iterrows():
        col, filled, alpha = result_colour(shot["result"])
        ax_pitch.scatter(shot["x"], shot["y"],
            s=max(30, shot["xg"] * 800),
            color=col if filled else BG,
            edgecolors=col, linewidths=1.8,
            alpha=alpha, zorder=4)

    for line in ax_pitch.get_lines():
        line.set_zorder(5)
        line.set_color(PITCH_LINE)

    legend_elements = [
        Line2D([0],[0], marker='o', color='w', markerfacecolor=COL_GOAL,
               markersize=9, label=f'Goal ({int((df.result=="Goal").sum())})'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor=BG,
               markeredgecolor=COL_SAVED, markeredgewidth=1.8,
               markersize=9, label=f'Saved ({int((df.result=="SavedShot").sum())})'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor=BG,
               markeredgecolor=COL_MISSED, markeredgewidth=1.8,
               markersize=9, label=f'Missed ({int((df.result=="MissedShots").sum())})'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor=BG,
               markeredgecolor=COL_BLOCKED, markeredgewidth=1.8,
               markersize=9, label=f'Blocked ({int((df.result=="BlockedShot").sum())})'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor=BG,
               markeredgecolor=COL_POST, markeredgewidth=1.8,
               markersize=9, label=f'Post ({int((df.result=="ShotOnPost").sum())})'),
    ]
    leg = ax_pitch.legend(handles=legend_elements, loc='lower left',
        facecolor='#ffffffee', edgecolor='#dddddd',
        prop=reg_prop, fontsize=9, framealpha=0.95)
    leg.set_zorder(6)
    ax_pitch.set_title("Shot Locations  (bubble size = xG)",
        fontproperties=reg_prop, fontsize=11, color=TEXT, pad=8)

    # ================================================================
    # RIGHT: ZONE GRID
    # ================================================================
    ax_zone.set_facecolor(BG)
    ax_zone.set_xlim(0, 10)
    ax_zone.set_ylim(0, 6.5)
    ax_zone.axis('off')
    ax_zone.set_title("Shot Volume by Zone",
        fontproperties=reg_prop, fontsize=11, color=TEXT, pad=8)

    x_zones  = [(50,66),(66,83),(83,100)]
    y_zones  = [(0,33),(33,67),(67,100)]
    x_labels = ["Deep","Mid","Box"]
    y_labels = ["Left","Centre","Right"]

    zone_data = {}
    for xi,(x0,x1) in enumerate(x_zones):
        for yi,(y0,y1) in enumerate(y_zones):
            mask = ((df["x"]>=x0)&(df["x"]<x1)&(df["y"]>=y0)&(df["y"]<y1))
            z = df[mask]
            zone_data[(xi,yi)] = {
                "shots": len(z),
                "goals": int((z["result"]=="Goal").sum()),
                "xg":    z["xg"].sum(),
            }

    max_shots = max((v["shots"] for v in zone_data.values()), default=1)
    cell_w, cell_h, x_start, y_start = 2.8, 1.6, 0.5, 0.4

    for xi in range(3):
        for yi in range(3):
            z_shots = zone_data[(xi,yi)]["shots"]
            z_goals = zone_data[(xi,yi)]["goals"]
            z_xg    = zone_data[(xi,yi)]["xg"]
            intensity = z_shots / max_shots if max_shots > 0 else 0
            r = min(1.0, 0.15 + 0.85 * intensity)
            g = max(0.0, 0.92 - intensity * 0.85)
            b = max(0.0, 0.92 - intensity * 0.85)
            cx = x_start + xi * cell_w
            cy = y_start + yi * cell_h
            ax_zone.add_patch(patches.FancyBboxPatch(
                (cx,cy), cell_w-0.12, cell_h-0.12,
                boxstyle="round,pad=0.05",
                facecolor=(r,g,b,0.25+0.65*intensity),
                edgecolor='#cccccc', linewidth=1.0))
            ax_zone.text(cx+(cell_w-0.12)/2, cy+(cell_h-0.12)*0.64,
                str(z_shots), fontproperties=bold_prop, fontsize=17,
                color=TEXT if intensity<0.6 else 'white',
                ha='center', va='center')
            detail = f"{z_xg:.2f} xG"
            if z_goals > 0:
                detail += f"  G:{z_goals}"
            ax_zone.text(cx+(cell_w-0.12)/2, cy+(cell_h-0.12)*0.25,
                detail, fontproperties=reg_prop, fontsize=7.5,
                color=SUBTEXT if intensity<0.6 else '#eeeeee',
                ha='center', va='center')

    for xi,label in enumerate(x_labels):
        ax_zone.text(x_start+xi*cell_w+(cell_w-0.12)/2,
            y_start+3*cell_h+0.15, label,
            fontproperties=reg_prop, fontsize=8,
            color=SUBTEXT, ha='center', va='bottom')
    for yi,label in enumerate(y_labels):
        ax_zone.text(x_start-0.22, y_start+yi*cell_h+(cell_h-0.12)/2,
            label, fontproperties=reg_prop, fontsize=8,
            color=SUBTEXT, ha='right', va='center', rotation=90)

    # ================================================================
    # SITUATION BAR (own row)
    # ================================================================
    sit_counts = df["situation"].value_counts()
    sit_total  = sit_counts.sum()
    x_cur = 0.0
    for sit, col in SIT_COLS.items():
        count = sit_counts.get(sit, 0)
        if count == 0:
            continue
        w = count / sit_total
        ax_sitbar.add_patch(patches.Rectangle(
            (x_cur, 0.0), w, 1.0,
            facecolor=col, transform=ax_sitbar.transAxes, clip_on=False))
        if w > 0.06:
            ax_sitbar.text(x_cur + w/2, 0.5,
                f"{SIT_LABELS[sit]}  {count} ({w*100:.0f}%)",
                fontproperties=reg_prop, fontsize=8.5,
                color='white', ha='center', va='center',
                transform=ax_sitbar.transAxes, fontweight='bold')
        x_cur += w

    # ================================================================
    # SITUATION LEGEND (own row)
    # ================================================================
    ax_sitleg.text(0.0, 0.95, "Shot Situations",
        fontproperties=reg_prop, fontsize=8.5,
        color=SUBTEXT, ha='left', va='top',
        transform=ax_sitleg.transAxes)

    legend_x = 0.13
    for sit, col in SIT_COLS.items():
        count = sit_counts.get(sit, 0)
        if count == 0:
            continue
        ax_sitleg.add_patch(patches.Rectangle(
            (legend_x, 0.2), 0.016, 0.55,
            facecolor=col, transform=ax_sitleg.transAxes, clip_on=False))
        ax_sitleg.text(legend_x + 0.022, 0.55,
            f"{SIT_LABELS[sit]} ({count})",
            fontproperties=reg_prop, fontsize=8.5,
            color=SUBTEXT, ha='left', va='center',
            transform=ax_sitleg.transAxes)
        legend_x += 0.20

    # ================================================================
    # STAT CARDS (own row)
    # ================================================================
    ax_stats.axhline(y=1.0, color='#eeeeee', linewidth=1)
    ax_stats.axhline(y=0.0, color='#eeeeee', linewidth=1)

    stats = [
        ("Shots on Target", f"{on_target}  ({sot_pct:.0f}%)"),
        ("Avg xG / Shot",   f"{avg_xg:.3f}"),
        ("Goals",           f"{goals}"),
        ("xG Overperformance", f"{xg_diff:+.2f}"),
    ]
    for i, (label, value) in enumerate(stats):
        cx = i * 0.25 + 0.125
        is_diff = "Overperformance" in label
        col = (ACCENT if xg_diff >= 0 else '#4a90d9') if is_diff else TEXT
        ax_stats.text(cx, 0.72, value,
            fontproperties=bold_prop, fontsize=26,
            color=col, ha='center', va='top',
            transform=ax_stats.transAxes)
        ax_stats.text(cx, 0.22, label,
            fontproperties=reg_prop, fontsize=9,
            color=SUBTEXT, ha='center', va='top',
            transform=ax_stats.transAxes)

    for cx in [0.25, 0.50, 0.75]:
        ax_stats.axvline(x=cx, ymin=0.05, ymax=0.95,
            color='#eeeeee', linewidth=1)

    # ================================================================
    # FOOTER
    # ================================================================
    ax_footer.set_facecolor(BG)
    ax_footer.text(0.5, 0.5,
        "LensPro Analytics  •  Data via Understat / WhoScored",
        fontproperties=reg_prop, fontsize=8,
        color=SUBTEXT, ha='center', va='center',
        transform=ax_footer.transAxes, style='italic')
    ax_footer.text(0.98, 0.5, "LENSPRO",
        fontproperties=bold_prop, fontsize=9,
        color=ACCENT, ha='right', va='center',
        transform=ax_footer.transAxes)

    plt.savefig("shot_profile_output.png", dpi=150,
        bbox_inches='tight', facecolor=BG, edgecolor='none')
    print("Saved to shot_profile_output.png")
    plt.show()

def run(player_name, competition="Premier League", season="2024/25"):
    try:
        print(f"Building shot profile for {player_name}...")
        plot_shot_profile(player_name, competition=competition, season=season)
    except Exception as e:
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    run("Erling Haaland")