# server/main.py
from fastapi import FastAPI
from playwright.async_api import async_playwright
import os

app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "Transfer-Lens Server is Live", "location": "Render Cloud"}

@app.get("/scrape/{player_id}/{slug}")
async def get_player(player_id: str, slug: str):
    async with async_playwright() as p:
        # Launching chromium in the Render cloud environment
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        url = f"https://www.transfermarkt.com/{slug}/profil/spieler/{player_id}"
        
        try:
            # wait_until="domcontentloaded" is faster for cloud scrapers
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Use basic selectors to get data
            name = await page.locator("h1").inner_text()
            value_element = page.locator(".tm-player-market-value-main__current-value")
            value = await value_element.inner_text() if await value_element.count() > 0 else "N/A"

            await browser.close()
            return {
                "name": name.strip(), 
                "current_value": value.strip(),
                "status": "success"
            }
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# Render uses the PORT environment variable to tell your app where to listen
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)