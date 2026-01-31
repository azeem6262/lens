from fastapi import FastAPI
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import uvicorn
from supabase import create_client, Client
import re

# 1. Load Environment
load_dotenv() 

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing from environment variables")

supabase: Client = create_client(url, key)

app = FastAPI()

# --- HELPER: Positional Categorization ---
def get_position_group(raw_position: str):
    """Maps detailed Transfermarkt positions into four ML-ready groups."""
    pos = raw_position.lower()
    
    if any(x in pos for x in ["striker", "winger", "forward", "centre-forward"]):
        return "Attacker", "stats_attackers"
    
    if any(x in pos for x in ["midfield", "amc", "dmc", "cm", "mezzala"]):
        return "Midfielder", "stats_midfielders"
    
    if any(x in pos for x in ["back", "defender", "sweeper", "cb", "lb", "rb"]):
        return "Defender", "stats_defenders"
    
    if "goalkeeper" in pos:
        return "Goalkeeper", "stats_goalkeepers"
        
    return "Unknown", None

@app.get("/")
async def health_check():
    return {"status": "online", "project": "transfer-lens"}

# --- INGEST: League-wide Discovery ---
@app.post("/ingest/league")
async def ingest_league(league_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        await page.goto(league_url, wait_until="domcontentloaded")
        
        player_links = await page.locator("td.hauptlink a").all()
        players = []
        
        for link in player_links:
            href = await link.get_attribute("href")
            if href and "profil" in href:
                parts = href.split('/')
                players.append({
                    "tm_id": parts[4],
                    "name": (await link.inner_text()).strip(),
                    "slug": parts[1]
                })
        
        if players:
            supabase.table("players").upsert(players).execute()
            await browser.close()
            return {"ingested_count": len(players)}
        
        await browser.close()
        return {"error": "No players found"}

# --- SEARCH: Quick Lookup ---
@app.get("/search")
async def search_player(query: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={query}"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            first_result = page.locator("td.hauptlink a").first
            
            if await first_result.count() > 0:
                name = await first_result.inner_text()
                href = await first_result.get_attribute("href")
                parts = href.split('/')
                
                player_data = {
                    "name": name.strip(),
                    "id": parts[4],
                    "slug": parts[1],
                    "scrape_url": f"/scrape/{parts[4]}/{parts[1]}"
                }
                await browser.close()
                return player_data
            
            await browser.close()
            return {"error": "Player not found"}
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# --- SCRAPE: Detail & Positional Stats ---
@app.get("/scrape/{player_id}/{slug}")
async def get_player(player_id: str, slug: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        url = f"https://www.transfermarkt.com/{slug}/profil/spieler/{player_id}"
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 1. Basic Info & Position Detection
            raw_name = await page.locator("h1").inner_text()
            clean_name = re.sub(r'#\d+\s+', '', raw_name).strip()
            
            pos_element = page.locator("span.item-label:has-text('Position:') + span")
            raw_pos = await pos_element.inner_text() if await pos_element.count() > 0 else "Unknown"
            group_name, table_name = get_position_group(raw_pos)

            # 2. Market Value Extraction
            value_locator = page.locator(".tm-player-market-value-main__current-value")
            if await value_locator.count() == 0:
                value_locator = page.locator('div:has-text("€")').filter(has_text=re.compile(r'm|k')).last
            
            value_text = await value_locator.inner_text() if await value_locator.count() > 0 else "N/A"
            clean_value = value_text.split('Last')[0].strip()

            # 3. Save Position to Master Player Table
            supabase.table("players").update({"position_group": group_name}).eq("tm_id", player_id).execute()

            # 4. Save to Positional Table (Placeholder for future deep scraping)
            if table_name:
                supabase.table(table_name).upsert({
                    "tm_id": player_id,
                    "scraped_at": "now()"
                }).execute()

            await browser.close()
            return {
                "name": clean_name, 
                "current_value": clean_value,
                "position_group": group_name,
                "player_id": player_id
            }
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)