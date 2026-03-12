import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

# ---------------- SETUP ---------------- #

load_dotenv()
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

MIN_PASS_THRESHOLD = 3


# ---------------- FETCH EVENTS ---------------- #

def fetch_match_events(match_id: str, team_name: str, half: str):

    print("📡 Fetching match events...")

    response = (
        supabase
        .table("match_events")
        .select("*")
        .eq("match_id", match_id)
        .eq("team", team_name)
        .order("minute")
        .order("second")
        .execute()
    )

    if not response.data:
        print("⚠ No events found.")
        return pd.DataFrame()

    df = pd.DataFrame(response.data)
    df = df.sort_values(by=["minute", "second"]).reset_index(drop=True)

    # ---- HALF FILTER ----
    if half == 'FirstHalf':
        df = df[df["minute"] < 45]
    elif half == 'SecondHalf':
        df = df[df["minute"] >= 45]

    # ---- NORMALIZE DIRECTION ----
    if half == 'SecondHalf':
        df["x"] = 100 - df["x"]

    print(f"✅ Loaded {len(df)} events")

    return df


# ---------------- BUILD PASS NETWORK ---------------- #

def build_passing_network(df: pd.DataFrame):

    if df.empty:
        return {"nodes": [], "edges": []}

    edges = {}
    edge_attempts = {}
    node_touch_count = {}

    # -------- BUILD TOUCH COUNTS + EDGE COUNTS --------

    for i in range(len(df) - 1):

        current = df.iloc[i]
        next_event = df.iloc[i + 1]

        player = current["player_id"]
        node_touch_count[player] = node_touch_count.get(player, 0) + 1

        if (
            current["event_type"] == "Pass"
            and pd.notnull(next_event["player_id"])
            and next_event["team"] == current["team"]
        ):
            passer = current["player_id"]
            receiver = next_event["player_id"]
            key = (passer, receiver)

            edge_attempts[key] = edge_attempts.get(key, 0) + 1

            if current["outcome"] == "Successful":
                edges[key] = edges.get(key, 0) + 1

    # -------- LIMIT TO TOP 11 PLAYERS --------

    touch_series = pd.Series(node_touch_count)
    top_players = touch_series.nlargest(11).index.tolist()

    df = df[df["player_id"].isin(top_players)]

    # Filter edges to only top 11
    edges = {
        k: v for k, v in edges.items()
        if k[0] in top_players and k[1] in top_players
    }

    edge_attempts = {
        k: v for k, v in edge_attempts.items()
        if k[0] in top_players and k[1] in top_players
    }

    # -------- FETCH PLAYER NAMES --------

    player_res = (
        supabase
        .table("players_master")
        .select("id, name")
        .in_("id", top_players)
        .execute()
    )

    player_names = {
        p["id"]: p["name"]
        for p in player_res.data
    }

    # -------- NODE POSITIONS --------

    node_positions = (
        df.groupby("player_id")[["x", "y"]]
        .mean()
        .reset_index()
    )

    max_touches = max(
        [node_touch_count[p] for p in top_players]
    ) if top_players else 1

    nodes = []

    for _, row in node_positions.iterrows():

        player_id = row["player_id"]
        touches = node_touch_count.get(player_id, 0)

        nodes.append({
            "id": player_id,
            "name": player_names.get(player_id, "Unknown"),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "touches": touches,
            "size": (touches / max_touches) * 30 + 8
        })

    # -------- EDGE LIST --------

    edge_list = []

    for (passer, receiver), successful_passes in edges.items():

        if successful_passes < MIN_PASS_THRESHOLD:
            continue

        total_attempts = edge_attempts.get((passer, receiver), 1)
        completion = successful_passes / total_attempts

        edge_list.append({
            "source": passer,
            "target": receiver,
            "weight": successful_passes,
            "completion": round(completion, 2),
            "width": successful_passes * 0.6
        })

    print(f"🎯 Built {len(nodes)} nodes")
    print(f"🔗 Built {len(edge_list)} filtered edges")

    return {
        "nodes": nodes,
        "edges": edge_list
    }


# ---------------- MAIN FUNCTION ---------------- #

def generate_team_pass_network(match_id: str, team_name: str, half: str):

    df = fetch_match_events(match_id, team_name, half)
    return build_passing_network(df)


if __name__ == "__main__":

    MATCH_ID = "948c8dfd-54bf-499c-923f-ea56d0b7a212"
    TEAM_NAME = "Barcelona"
    HALF = 'FirstHalf'

    network_data = generate_team_pass_network(MATCH_ID, TEAM_NAME, HALF)

    print(network_data)
