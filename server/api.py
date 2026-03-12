from fastapi import FastAPI
from pass_network import generate_team_pass_network

app = FastAPI()

@app.get("/pass-network")
def get_pass_network(match_id: str, team: str, half: str):
    return generate_team_pass_network(match_id, team, half)
