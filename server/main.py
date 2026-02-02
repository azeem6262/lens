from fastapi import FastAPI
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import uvicorn
from supabase import create_client, Client
import re
import pandas as pd
import io
import requests
import soccerdata as sd


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
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        try:
            # 1. Get Club URLs from League Page
            await page.goto(league_url, wait_until="domcontentloaded", timeout=60000)
            club_links = await page.locator("td.hauptlink a").all()
            club_urls = []
            for link in club_links:
                href = await link.get_attribute("href")
                if href and "startseite/verein" in href:
                    club_urls.append(f"https://www.transfermarkt.com{href}")
            
            club_urls = list(set(club_urls))
            all_players = []

            # 2. Visit each club
            for club_url in club_urls:
                try:
                    await page.goto(club_url, wait_until="domcontentloaded", timeout=30000)
                    club_name = await page.locator("h1.data-header__headline-wrapper").inner_text()
                    rows = await page.locator("table.items > tbody > tr").all()
                    
                    for row in rows:
                        try:
                            # Verify this is a player row
                            link = row.locator("td.hauptlink a").first
                            if await link.count() == 0: continue
                            
                            href = await link.get_attribute("href")
                            if "profil/spieler" not in href: continue
                            
                            # Extract data with safe fallbacks to prevent 500 errors
                            tm_id = href.split('/')[-1]
                            name = await link.inner_text()
                            
                            # Position is usually in the second row of the first cell's table
                            pos_locator = row.locator("td.hauptlink + td") # fallback
                            position = await row.locator("table.inline-table tr:nth-child(2) td").inner_text() if await row.locator("table.inline-table").count() > 0 else "Unknown"
                            
                            # Market Value is in the cell with class 'rechts hauptlink'
                            value_cell = row.locator("td.rechts.hauptlink")
                            value = await value_cell.inner_text() if await value_cell.count() > 0 else "N/A"

                            all_players.append({
                                "tm_id": tm_id,
                                "name": name.strip(),
                                "slug": href.split('/')[1],
                                "position": position.strip(),
                                "current_market_value": value.strip(),
                                "club": club_name.strip()
                            })
                        except Exception:
                            continue # Skip bad player rows
                except Exception:
                    continue # Skip bad club pages

            # 3. Bulk UPSERT in chunks
            if all_players:
                for i in range(0, len(all_players), 100):
                    chunk = all_players[i:i + 100]
                    supabase.table("players").upsert(chunk).execute()
                
                await browser.close()
                return {"status": "success", "total_ingested": len(all_players)}

            await browser.close()
            return {"error": "No players found"}

        except Exception as e:
            await browser.close()
            return {"error": f"Critical Failure: {str(e)}"}

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

def get_position_group(raw_position: str):
    pos = raw_position.lower()
    
    # Attackers: Look for scoring roles
    if any(x in pos for x in ["striker", "winger", "forward", "centre-forward", "left wing", "right wing"]):
        return "Attacker", "stats_attackers"
    
    # Midfielders: Look for engine room roles
    if any(x in pos for x in ["midfield", "amc", "dmc", "cm", "mezzala"]):
        return "Midfielder", "stats_midfielders"
    
    # Defenders: Specifically catch all 'back' and 'defender' variants
    if any(x in pos for x in ["back", "defender", "cb", "lb", "rb", "sweeper"]):
        return "Defender", "stats_defenders"
    
    # Goalkeepers
    if "goalkeeper" in pos:
        return "Goalkeeper", "stats_goalkeepers"
        
    return "Unknown", None

@app.post("/process/segregate")
async def segregate_players():
    try:
        # 1. Fetch all players from the master index
        response = supabase.table("players").select("tm_id, position").execute()
        players = response.data
        
        counts = {"Attacker": 0, "Midfielder": 0, "Defender": 0, "Goalkeeper": 0, "Unknown": 0}

        for p in players:
            # Use your existing helper to find the right category and table
            group, table_name = get_position_group(p['position'])
            
            if table_name:
                # 2. Insert into the specialized table (upsert avoids duplicates)
                supabase.table(table_name).upsert({
                    "tm_id": p['tm_id'],
                    "scraped_at": "now()"
                }).execute()
                
                # 3. Update the master table so we know the group is assigned
                supabase.table("players").update({"position_group": group}).eq("tm_id", p['tm_id']).execute()
                
                counts[group] += 1
            else:
                counts["Unknown"] += 1
                
        return {"message": "Segregation complete", "stats": counts}
    except Exception as e:
        return {"error": str(e)}

@app.get("/scrape/fbref/attackers")
async def scrape_fbref_attackers():
    # 1. Fetch attackers who still need an ID
    response = supabase.table("players").select("tm_id, name, club").eq("position_group", "Attacker").is_("fbref_id", "null").execute()
    attackers = response.data

    if not attackers:
        return {"message": "All attackers already have IDs. Ready for deep scraping!"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent="Mozilla/5.0...")
        page = await context.new_page()

        processed = []
        for player in attackers[:5]:
            try:
                # BYPASS GOOGLE: Go directly to FBRef's internal search
                search_url = f"https://fbref.com/en/search/search.fcgi?search={player['name'].replace(' ', '+')}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                # If FBRef finds an exact match, it redirects to the player page
                # If not, it shows a list. We grab the first player link.
                current_url = page.url
                
                if "/players/" in current_url:
                    # Case 1: Direct Redirect
                    fb_id = current_url.split('/')[5]
                else:
                    # Case 2: Search Results List
                    first_link = page.locator("#search_results .search-item a").first
                    if await first_link.count() > 0:
                        href = await first_link.get_attribute("href")
                        fb_id = href.split('/')[3] # Format is /en/players/ID/Name
                    else:
                        continue

                # 2. Update Supabase IMMEDIATELY
                supabase.table("players").update({"fbref_id": fb_id}).eq("tm_id", player['tm_id']).execute()
                processed.append({"name": player['name'], "fb_id": fb_id})
                
                # Small wait to avoid being rate-limited
                await page.wait_for_timeout(2000)

            except Exception as e:
                print(f"Error on {player['name']}: {e}")
                continue

        await browser.close()
        return {"status": "success", "new_ids_found": processed}

@app.post("/process/instant-mapping")
async def instant_mapping():
    # 1. Target ANY player without an ID (Attackers, Midfielders, etc.)
    response = supabase.table("players") \
        .select("tm_id, name, club") \
        .or_("fbref_id.is.null, fbref_id.eq.") \
        .execute()
    
    players_to_map = response.data

    if not players_to_map:
        return {"status": "success", "new_mappings": 0, "message": "All players already have IDs."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        # Professional user-agent to ensure we get the desktop search results
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        mapped_count = 0
        for player in players_to_map[:10]: # Batch of 10 for safety
            try:
                # 2. Search FBRef directly using their internal search engine
                search_url = f"https://fbref.com/en/search/search.fcgi?search={player['name'].replace(' ', '+')}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                # Check if we were redirected straight to a profile or a search list
                current_url = page.url
                
                if "/players/" in current_url:
                    # Case A: Direct hit (FBRef was sure)
                    fb_id = current_url.split('/')[5]
                else:
                    # Case B: Multiple results (Pick the first one)
                    # We target the first link in the search results table
                    first_link = page.locator("#search_results .search-item a").first
                    if await first_link.count() > 0:
                        href = await first_link.get_attribute("href")
                        # Format is /en/players/ID/Name
                        fb_id = href.split('/')[3]
                    else:
                        continue

                # 3. Update Supabase
                supabase.table("players").update({"fbref_id": fb_id}).eq("tm_id", player['tm_id']).execute()
                mapped_count += 1
                
                # Human-like delay to avoid rate limiting
                await page.wait_for_timeout(2000)

            except Exception as e:
                print(f"Error mapping {player['name']}: {e}")
                continue

        await browser.close()
        return {"status": "Batch complete", "new_mappings": mapped_count}


@app.post("/process/soccerdata-sync-attackers")
async def soccerdata_sync_attackers():
    try:
        # 1. Initialize FBref (SD handles the 2026 season automatically)
        fbref = sd.FBref(leagues="ENG-Premier League", seasons="2526")
        
        # 2. Pull the 4 vital tables for a complete Attacker profile
        print("Downloading FBRef tables...")
        std_df = fbref.read_player_season_stats(stat_type="standard").reset_index()
        shot_df = fbref.read_player_season_stats(stat_type="shooting").reset_index()
        pass_df = fbref.read_player_season_stats(stat_type="passing").reset_index()
        poss_df = fbref.read_player_season_stats(stat_type="possession").reset_index()

        # 3. Get your attackers from Supabase
        response = supabase.table("players").select("tm_id, name").eq("position_group", "Attacker").execute()
        my_attackers = response.data

        count = 0
        for p in my_attackers:
            # Match by name (Fuzzy matching is handled by checking if name is 'in' FBref name)
            match = std_df[std_df['player'].str.contains(p['name'], case=False, na=False)]
            
            if not match.empty:
                player_name = match['player'].values[0]
                
                # Extracting all fields for your DB
                # Note: SoccerData uses MultiIndex, so we access via ('Category', 'Stat')
                stats_payload = {
                    # From Standard Table
                    "npxg_per_90": float(match['Expected']['npxG_per90'].values[0]),
                    
                    # From Shooting Table (Conversion Rate)
                    "conversion_rate": float(shot_df[shot_df['player'] == player_name]['Standard']['G/Sh'].values[0] or 0),
                    
                    # From Passing Table (Playmaking)
                    "xa_per_90": float(pass_df[pass_df['player'] == player_name]['Expected']['xA_per90'].values[0] or 0),
                    
                    # From Possession Table (Dribbling/Progression)
                    "progressive_carries_per_90": float(poss_df[poss_df['player'] == player_name]['Carries']['PrgC90'].values[0] or 0),
                    "successful_take_ons_per_90": float(poss_df[poss_df['player'] == player_name]['Take-Ons']['Succ90'].values[0] or 0),
                    
                    "fbref_id": "synced_v1"
                }

                # 4. Update the stats_attackers table
                supabase.table("stats_attackers").update(stats_payload).eq("tm_id", p['tm_id']).execute()
                count += 1

        return {"status": "Complete", "attackers_updated": count}
        
    except Exception as e:
        return {"error": f"Scrape failed: {str(e)}"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)