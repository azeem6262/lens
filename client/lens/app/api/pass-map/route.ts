import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const tm_id = searchParams.get('tm_id');

  if (!tm_id) return NextResponse.json({ error: 'Missing tm_id' }, { status: 400 });

  // Step 1: tm_id → player_mappings.player_id
  const { data: mapping, error: mappingErr } = await supabase
    .from('player_mappings')
    .select('player_id')
    .eq('tm_id', tm_id)
    .limit(1)
    .single();

  if (mappingErr || !mapping?.player_id) {
    return NextResponse.json({ error: `player_mappings lookup failed: ${mappingErr?.message}` }, { status: 404 });
  }

  // Step 2: player name from players_master
  const { data: master } = await supabase
    .from('players_master')
    .select('name, clubs_master(name)')
    .eq('tm_id', tm_id)
    .limit(1)
    .single();

  // Step 3: passes from match_events
  const { data: passes, error: passErr } = await supabase
    .from('match_events')
    .select('x, y, end_x, end_y, outcome, is_key_pass, is_progressive, minute, period')
    .eq('player_id', mapping.player_id)
    .eq('event_type', 'Pass')
    .not('x', 'is', null)
    .not('end_x', 'is', null)
    .limit(2000);

  if (passErr) {
    return NextResponse.json({ error: `match_events query failed: ${passErr.message}` }, { status: 500 });
  }

  const mapped = (passes || []).map((p: any) => ({
    x: parseFloat(p.x),
    y: parseFloat(p.y),
    end_x: parseFloat(p.end_x),
    end_y: parseFloat(p.end_y),
    success: p.outcome === 'Successful',
    is_key: p.is_key_pass ?? false,
    is_progressive: p.is_progressive ?? false,
    minute: p.minute,
    period: p.period,
  }));

  const total       = mapped.length;
  const successful  = mapped.filter(p => p.success).length;
  const key_passes  = mapped.filter(p => p.is_key).length;
  const progressive = mapped.filter(p => p.is_progressive).length;

  return NextResponse.json({
    player: {
      id: mapping.player_id,
      name: master?.name ?? null,
      club: (master as any)?.clubs_master?.name ?? null,
      tm_id,
    },
    stats: {
      total,
      successful,
      completion_pct: total ? parseFloat((successful / total * 100).toFixed(1)) : 0,
      key_passes,
      progressive,
    },
    passes: mapped,
  });
}