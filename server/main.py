from fastapi import FastAPI
from playwright.async_api import async_playwright
import os
import uvicorn
import re

app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "online", "project": "transfer-lens"}

# --- NEW: Search Endpoint ---
@app.get("/search")
async def search_player(query: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        # Transfermarkt search results page
        search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={query}"
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            
            # Target the first 'hauptlink' (main link) in the search result table
            first_result = page.locator("td.hauptlink a").first
            
            if await first_result.count() > 0:
                name = await first_result.inner_text()
                href = await first_result.get_attribute("href")
                
                # Href format: /erling-haaland/profil/spieler/418560
                parts = href.split('/')
                
                player_slug = parts[1]
                player_id = parts[4]

                await browser.close()
                return {
                    "name": name.strip(),
                    "id": player_id,
                    "slug": player_slug,
                    "scrape_url": f"/scrape/{player_id}/{player_slug}"
                }
            
            await browser.close()
            return {"error": "No player found matching that query."}
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# --- UPDATED: Scraper Route with Better Selectors ---
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
            
            # 1. Clean Name (Removes shirt numbers like '#9')
            raw_name = await page.locator("h1").inner_text()
            clean_name = re.sub(r'#\d+\s+', '', raw_name).strip()
            
            # 2. Resilient Market Value Selector
            # We try the primary class, then fallback to a broader search for the '€' symbol
            value_locator = page.locator(".tm-player-market-value-main__current-value")
            
            if await value_locator.count() == 0:
                # Fallback: Find a div containing the Euro symbol that looks like a price
                value_locator = page.locator('div:has-text("€")').filter(has_text=re.compile(r'm|k')).last

            value_text = await value_locator.inner_text() if await value_locator.count() > 0 else "Value Hidden"
            
            # Clean the value (removes things like 'Last update: Jun 1, 2025')
            clean_value = value_text.split('Last')[0].strip()

            await browser.close()
            return {
                "name": clean_name, 
                "current_value": clean_value,
                "player_id": player_id,
                "slug": slug
            }
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)