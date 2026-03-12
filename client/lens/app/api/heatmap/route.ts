import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const tm_id = searchParams.get('tm_id');
  const event_type = searchParams.get('event_type') || null;

  if (!tm_id) return NextResponse.json({ error: 'Missing tm_id' }, { status: 400 });

  // tm_id → player_mappings.player_id (match_events uses this ID)
  const { data: mapping } = await supabase
    .from('player_mappings')
    .select('player_id, players_master:player_id(name, clubs_master(name))')
    .eq('tm_id', tm_id)
    .limit(1)
    .single();

  if (!mapping?.player_id) {
    return NextResponse.json({ error: 'Player not found in player_mappings' }, { status: 404 });
  }

  let query = supabase
    .from('match_events')
    .select('x, y, event_type, outcome, minute, period')
    .eq('player_id', mapping.player_id)
    .not('x', 'is', null)
    .not('y', 'is', null)
    .limit(5000);

  if (event_type) query = query.eq('event_type', event_type);

  const { data: events, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const points = (events || []).map((e: any) => ({
    x: parseFloat(e.x),
    y: parseFloat(e.y),
    event_type: e.event_type,
    outcome: e.outcome,
    minute: e.minute,
    period: e.period,
  }));

  const type_counts: Record<string, number> = {};
  points.forEach(p => { type_counts[p.event_type] = (type_counts[p.event_type] || 0) + 1; });

  const playerInfo = (mapping as any).players_master;

  return NextResponse.json({
    player: {
      id: mapping.player_id,
      name: playerInfo?.name ?? null,
      club: playerInfo?.clubs_master?.name ?? null,
      tm_id,
    },
    stats: { total_events: points.length, type_counts },
    points,
  });
}