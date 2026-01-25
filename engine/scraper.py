from fastapi import FastAPI
from playwright.async_api import async_playwright

app = FastAPI()

async def scrape_transfermarkt(player_id, player_slug):
    async with async_playwright() as p:
        # We launch without a proxy because cloud servers aren't blocked by Indian ISPs
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = f"https://www.transfermarkt.com/{player_slug}/profil/spieler/{player_id}"
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            name = await page.locator("h1").inner_text()
            value = await page.locator(".tm-player-market-value-main__current-value").inner_text()
            await browser.close()
            return {"name": name.strip(), "value": value.strip()}
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

@app.get("/scrape/{player_id}/{slug}")
async def get_player(player_id: str, slug: str):
    data = await scrape_transfermarkt(player_id, slug)
    return data