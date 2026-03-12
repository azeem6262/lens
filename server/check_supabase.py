import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def verify_db():
    print("📡 Connecting to Supabase...")
    res = supabase.table("players").select("name, position_group, club").execute()
    data = res.data
    
    print(f"📊 Total players fetched by Python: {len(data)}")
    
    # Let's look for Jonathan David in the actual data array
    jd_finds = [p for p in data if "David" in str(p.get('name'))]
    
    if jd_finds:
        print(f"✅ Found Jonathan David in local Python data!")
        print(f"Full Record: {jd_finds[0]}")
    else:
        print("❌ Jonathan David NOT found in the data returned to Python.")
        print("First 3 names found:", [p.get('name') for p in data[:3]])

if __name__ == "__main__":
    verify_db()