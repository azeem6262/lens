import supabase
def merge_duplicate_players(target_name):
    # 1. Get all entries for the duplicate name
    res = supabase.table("players_master").select("id, club_id").ilike("name", target_name).execute()
    records = res.data
    
    if len(records) <= 1:
        print(f"✅ {target_name} is already clean.")
        return

    # 2. Pick the 'Golden ID' (the first one) and 'Duplicate IDs' (the rest)
    golden_id = records[0]['id']
    duplicate_ids = [r['id'] for r in records[1:]]

    print(f"Merging {len(duplicate_ids)} duplicates into Golden ID: {golden_id}")

    # 3. Update player_mappings to point to the Golden ID
    # This ensures your WhoScored events don't lose their player link
    for dup_id in duplicate_ids:
        supabase.table("player_mappings").update({"player_id": golden_id}).eq("player_id", dup_id).execute()

    # 4. Safely delete the duplicate master records
    # Since mappings are now moved, these are "orphaned" and safe to remove
    for dup_id in duplicate_ids:
        supabase.table("players_master").delete().eq("id", dup_id).execute()
    
    print(f"✨ {target_name} successfully merged.")

# merge_duplicate_players("Marcus Rashford")