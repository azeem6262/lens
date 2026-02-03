import asyncio
import os
import re
from playwright.async_api import async_playwright
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Load Credentials
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- HELPER: Position Mapper ---
def get_position_group(raw_position: str):
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

# --- MASTER INGEST LOGIC ---
async def ingest_league_locally(league_url: str):
    async with async_playwright() as p:
        # Launching with headless=False lets you watch the magic happen
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        try:
            print(f"--- 🚀 Starting Ingest for: {league_url} ---")
            await page.goto(league_url, wait_until="domcontentloaded", timeout=60000)
            
            # 1. Find all Club URLs
            club_links = await page.locator("td.hauptlink a").all()
            club_urls = []
            for link in club_links:
                href = await link.get_attribute("href")
                if href and "startseite/verein" in href:
                    club_urls.append(f"https://www.transfermarkt.com{href}")
            
            club_urls = list(set(club_urls))
            print(f"Found {len(club_urls)} clubs. Starting deep crawl...")

            # 2. Visit each club
            for index, club_url in enumerate(club_urls):
                try:
                    print(f"[{index+1}/{len(club_urls)}] Scraping: {club_url}")
                    await page.goto(club_url, wait_until="domcontentloaded", timeout=30000)
                    
                    club_name_element = page.locator("h1.data-header__headline-wrapper")
                    club_name = await club_name_element.inner_text() if await club_name_element.count() > 0 else "Unknown Club"
                    
                    rows = await page.locator("table.items > tbody > tr").all()
                    club_players = []

                    for row in rows:
                        link = row.locator("td.hauptlink a").first
                        if await link.count() == 0: continue
                        
                        href = await link.get_attribute("href")
                        if "profil/spieler" not in href: continue
                        
                        tm_id = href.split('/')[-1]
                        name = await link.inner_text()
                        
                        # Position Extraction
                        pos_table = row.locator("table.inline-table tr:nth-child(2) td")
                        position = await pos_table.inner_text() if await pos_table.count() > 0 else "Unknown"
                        group_name, _ = get_position_group(position)

                        # Value Extraction
                        value_cell = row.locator("td.rechts.hauptlink")
                        value = await value_cell.inner_text() if await value_cell.count() > 0 else "N/A"

                        club_players.append({
                            "tm_id": tm_id,
                            "name": name.strip(),
                            "slug": href.split('/')[1],
                            "position": position.strip(),
                            "position_group": group_name,
                            "current_market_value": value.strip(),
                            "club": club_name.strip()
                        })

                    # 3. UPSERT the club's players immediately to Supabase
                    if club_players:
                        supabase.table("players").upsert(club_players).execute()
                        print(f"   ✅ Saved {len(club_players)} players from {club_name}")

                except Exception as club_err:
                    print(f"   ❌ Error at club {club_url}: {club_err}")
                    continue

            print("--- 🎉 Global Ingest Complete! ---")
            await browser.close()

        except Exception as e:
            print(f"🔥 Critical Failure: {str(e)}")
            await browser.close()

if __name__ == "__main__":
    # RUN FOR THE BIG 5 ONE BY ONE
    TARGET_LEAGUE = "https://www.transfermarkt.com/la-liga/startseite/wettbewerb/ES1"
    asyncio.run(ingest_league_locally(TARGET_LEAGUE))