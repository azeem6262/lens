import os
import time
import random
import re
import requests
from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load credentials
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/122.0"
]

def parse_tm_value_regex(val_str):
    if not val_str: return 0
    match = re.search(r'(\d+\.?\d*)([mk])', val_str.lower())
    if not match: return 0
    num, suffix = match.groups()
    multiplier = 1_000_000 if suffix == 'm' else 1_000
    return int(float(num) * multiplier)

def fetch_value_stealth(tm_id, session):
    url = f"https://www.transfermarkt.com/a/profil/spieler/{tm_id}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }
    try:
        response = session.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            val_div = soup.select_one('.tm-player-market-value-main')
            if not val_div:
                val_div = soup.select_one('.data-header__market-value-wrapper')
            if val_div:
                return parse_tm_value_regex(val_div.get_text(strip=True))
        elif response.status_code == 429:
            return "SLEEP"
    except Exception as e:
        print(f"📡 Connection drop for ID {tm_id}: {str(e)[:50]}...")
    return None

def run_refresh(limit=15):
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()

    res = supabase.table("players") \
        .select("tm_id, name, current_market_value, last_scraped_at") \
        .or_("current_market_value.eq.0,current_market_value.is.null") \
        .or_(f"last_scraped_at.lt.{yesterday},last_scraped_at.is.null") \
        .limit(limit) \
        .execute()

    players = res.data
    if not players:
        return "FINISHED"

    with requests.Session() as session:
        for player in players:
            print(f"🔍 Checking: {player['name']} (ID: {player['tm_id']})...")

            # Mark as attempted immediately (prevents infinite loops)
            supabase.table("players").update({
                "last_scraped_at": datetime.now().isoformat()
            }).eq("tm_id", player['tm_id']).execute()

            new_val = fetch_value_stealth(player['tm_id'], session)

            if new_val == "SLEEP":
                print("🛑 Rate limited. Ending batch early.")
                return "SLEEP"

            # 🚨 HARD SAFETY LOCK
            if new_val and new_val > 0:
                supabase.table("players") \
                    .update({"current_market_value": new_val}) \
                    .eq("tm_id", player['tm_id']) \
                    .lt("current_market_value", 1_000_000) \
                    .execute()

                print(f"   💰 SUCCESS: €{new_val:,}")
            else:
                print("   ⚠️ No market value found.")

            time.sleep(random.uniform(3.5, 7.0))

    return "CONTINUE"


if __name__ == "__main__":
    batch_size = 20
    print(f"🚀 Starting PERSISTENT Auto-Pilot Scraper...")
    
    while True:
        status = run_refresh(limit=batch_size)
        
        if status == "FINISHED":
            print("✨ Mission Accomplished: All possible players have values!")
            break
            
        # Check remaining for the status log
        res_count = supabase.table("players").select("count", count="exact").eq("current_market_value", 0).execute()
        remaining = res_count.count if res_count.count else 0
        
        # If we got rate limited, sleep much longer
        sleep_duration = 1200 if status == "SLEEP" else random.uniform(600, 900)
        print(f"😴 Batch complete. {remaining} potential players left. Sleeping for {int(sleep_duration/60)} mins...")
        time.sleep(sleep_duration)