# server/main.py
from fastapi import FastAPI
from playwright.async_api import async_playwright
import os
import uvicorn

app = FastAPI()

# 1. INDUSTRY BEST PRACTICE: A super-fast health check route.
# This ensures Render's health check passes immediately before the heavy stuff loads.
@app.get("/")
async def health_check():
    return {"status": "online", "project": "transfer-lens"}

# 2. THE SCRAPER ROUTE: Only runs when specifically called.
@app.get("/scrape/{player_id}/{slug}")
async def get_player(player_id: str, slug: str):
    async with async_playwright() as p:
        # Launching Chromium with minimal features to save RAM (Free Tier is limited!)
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        url = f"https://www.transfermarkt.com/{slug}/profil/spieler/{player_id}"
        
        try:
            # We use 'domcontentloaded' to avoid waiting for heavy ads/trackers
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            name = await page.locator("h1").inner_text()
            value_element = page.locator(".tm-player-market-value-main__current-value")
            value = await value_element.inner_text() if await value_element.count() > 0 else "N/A"

            await browser.close()
            return {"name": name.strip(), "current_value": value.strip()}
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# 3. DYNAMIC PORT HANDLING: Render tells us which port to use via an Env Var.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)