import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const tm_id = searchParams.get('tm_id');
  const competition = searchParams.get('competition') || null;

  if (!tm_id) return NextResponse.json({ error: 'Missing tm_id' }, { status: 400 });

  // tm_id → players_master.id (understat shots use this)
  const { data: master } = await supabase
    .from('players_master')
    .select('id, name, clubs_master(name)')
    .eq('tm_id', tm_id)
    .limit(1)
    .single();

  if (!master) return NextResponse.json({ error: 'Player not found in players_master' }, { status: 404 });

  let query = supabase
    .from('understat_shots')
    .select(`
      x, y, xg, result, situation, shot_type, last_action, minute,
      matches_master(competition, match_date, home_goals, away_goals,
        home_club:home_club_id(name), away_club:away_club_id(name))
    `)
    .eq('player_id', master.id);

  const { data: shots, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const filtered = competition
    ? (shots || []).filter((s: any) => s.matches_master?.competition === competition)
    : shots || [];

  const normalized = filtered.map((s: any) => ({
    x: parseFloat(s.x) * 100,
    y: parseFloat(s.y) * 100,
    xg: parseFloat(s.xg),
    result: s.result,
    situation: s.situation,
    shot_type: s.shot_type,
    last_action: s.last_action,
    minute: s.minute,
    match: s.matches_master ? {
      competition: s.matches_master.competition,
      date: s.matches_master.match_date,
      home: s.matches_master.home_club?.name,
      away: s.matches_master.away_club?.name,
      score: `${s.matches_master.home_goals ?? '?'}-${s.matches_master.away_goals ?? '?'}`,
    } : null,
  }));

  const goals    = normalized.filter(s => s.result === 'Goal').length;
  const total_xg = normalized.reduce((a, s) => a + s.xg, 0);
  const on_target = normalized.filter(s => ['Goal','SavedShot'].includes(s.result)).length;

  return NextResponse.json({
    player: { id: master.id, name: master.name, club: (master as any).clubs_master?.name ?? null, tm_id },
    stats: {
      total: normalized.length,
      goals,
      total_xg: parseFloat(total_xg.toFixed(2)),
      xg_diff: parseFloat((goals - total_xg).toFixed(2)),
      on_target,
      sot_pct: normalized.length ? parseFloat((on_target / normalized.length * 100).toFixed(1)) : 0,
      avg_xg: normalized.length ? parseFloat((total_xg / normalized.length).toFixed(3)) : 0,
    },
    shots: normalized,
  });
}