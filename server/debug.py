import requests

# Try known Understat AJAX endpoints
endpoints = [
    "https://understat.com/main/getLeagueFixturesAndResults/",
    "https://understat.com/main/getLeagueFixtures/",
    "https://understat.com/main/getLeagueResults/",
    "https://understat.com/league/EPL/2024",
    "https://understat.com/league/epl/2024",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://understat.com/league/EPL/2024",
}

for url in endpoints:
    try:
        r = requests.post(url, headers=headers, data={"league": "EPL", "season": "2024"}, timeout=10)
        print(f"\nPOST {url}")
        print(f"  Status: {r.status_code}, Length: {len(r.text)}, Type: {r.headers.get('Content-Type','')}")
        print(f"  Preview: {r.text[:200]}")
    except Exception as e:
        print(f"\nPOST {url} → ERROR: {e}")