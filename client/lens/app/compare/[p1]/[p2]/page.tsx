'use client';
import { use, useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Radar as RadarArea } from 'recharts';
import { Swords, Fingerprint, Clock, Zap, Shield, Target, Brain } from 'lucide-react';
import Link from 'next/link';

export default function DuelMatrix({ params }: { params: Promise<{ p1: string, p2: string }> }) {
  const resolvedParams = use(params);
  const { p1, p2 } = resolvedParams;
  
  const [player1, setPlayer1] = useState<any>(null);
  const [player2, setPlayer2] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDuelData() {
      if (!p1 || !p2) return;
      setLoading(true);
      
      try {
        // Step 1: Fetch raw player identities
        const [resP1, resP2] = await Promise.all([
          supabase.from('players').select('*').eq('tm_id', p1).single(),
          supabase.from('players').select('*').eq('tm_id', p2).single()
        ]);

        // Step 2: Fetch positional stats separately to ensure we get data
        // We use the same 'stats' tables from your player page
        const fetchStats = async (tmId: string) => {
          const { data: mid } = await supabase.from('stats_midfielders').select('*').eq('tm_id', tmId).maybeSingle();
          if (mid) return mid;
          const { data: att } = await supabase.from('stats_attackers').select('*').eq('tm_id', tmId).maybeSingle();
          if (att) return att;
          const { data: def } = await supabase.from('stats_defenders').select('*').eq('tm_id', tmId).maybeSingle();
          if (def) return def;
          const { data: gk } = await supabase.from('stats_goalkeepers').select('*').eq('tm_id', tmId).maybeSingle();
          return gk || {};
        };

        const [s1, s2] = await Promise.all([fetchStats(p1), fetchStats(p2)]);

        if (resP1.data) setPlayer1({ ...resP1.data, s: s1 });
        if (resP2.data) setPlayer2({ ...resP2.data, s: s2 });

      } catch (err) {
        console.error("DUEL_SYNC_FAILURE:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchDuelData();
  }, [p1, p2]);

  if (loading) return <div className="min-h-screen bg-[#050505] flex items-center justify-center text-lens-blue font-mono uppercase animate-pulse tracking-[0.3em]">SYNCHRONIZING_DUEL_STREAM...</div>;
  if (!player1 || !player2) return <div className="min-h-screen bg-[#050505] text-white p-20 font-mono text-center tracking-widest">404 // DATA_NOT_FOUND</div>;

  const radarData = [
    { subject: 'Prog', A: (player1.s?.progressive_passes_per_90 || 0) * 10, B: (player2.s?.progressive_passes_per_90 || 0) * 10 },
    { subject: 'Acc', A: (player1.s?.pass_completion_pct || 0), B: (player2.s?.pass_completion_pct || 0) },
    { subject: 'Creat', A: (player1.s?.sca_per_90 || 0) * 15, B: (player2.s?.sca_per_90 || 0) * 15 },
    { subject: 'Def', A: (player1.s?.tackles_per_90 || 0) * 30, B: (player2.s?.tackles_per_90 || 0) * 30 },
    { subject: 'Vol', A: Math.min(player1.s?.touches_per_90 || 0, 100), B: Math.min(player2.s?.touches_per_90 || 0, 100) },
  ];

  return (
    <main className="min-h-screen bg-[#050505] text-white p-4 lg:p-8 font-sans">
      <div className="max-w-[1800px] mx-auto flex justify-between items-center mb-6 bg-[#0A0A0A] border border-white/5 rounded-2xl px-6 py-4">
        <Link href="/" className="text-white font-black italic tracking-tighter hover:text-lens-blue transition-colors uppercase text-xl">LENS PRO</Link>
        <div className="flex items-center gap-3 bg-lens-blue/10 px-4 py-2 rounded-xl border border-lens-blue/20">
          <Swords size={12} className="text-lens-blue" />
          <span className="text-[10px] font-black uppercase tracking-[0.3em] text-lens-blue italic">Active Combat Matrix</span>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto grid grid-cols-1 md:grid-cols-12 gap-4">
        <IdentityTile player={player1} side="left" color="text-lens-blue" label="Alpha" />
        <div className="md:col-span-4 bg-[#0A0A0A] border border-white/5 rounded-3xl p-8 relative flex flex-col items-center justify-center min-h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid stroke="#222" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#444', fontSize: 10, fontWeight: '900' }} tickLine={false} />
              <RadarArea name={player1.name} dataKey="A" stroke="#0070f3" fill="#0070f3" fillOpacity={0.4} strokeWidth={3} />
              <RadarArea name={player2.name} dataKey="B" stroke="#ef4444" fill="#ef4444" fillOpacity={0.4} strokeWidth={3} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <IdentityTile player={player2} side="right" color="text-red-500" label="Beta" />

        <div className="md:col-span-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <DuelCard label="Prog. Passing" v1={player1.s?.progressive_passes_per_90} v2={player2.s?.progressive_passes_per_90} />
            <DuelCard label="Pass Acc %" v1={player1.s?.pass_completion_pct} v2={player2.s?.pass_completion_pct} unit="%" />
            <DuelCard label="Creation (SCA)" v1={player1.s?.sca_per_90} v2={player2.s?.sca_per_90} />
            <DuelCard label="Expected Assists" v1={player1.s?.xa_per_90} v2={player2.s?.xa_per_90} />
            <DuelCard label="Interceptions" v1={player1.s?.interceptions_per_90} v2={player2.s?.interceptions_per_90} />
            <DuelCard label="Tackles Made" v1={player1.s?.tackles_per_90} v2={player2.s?.tackles_per_90} />
            <DuelCard label="Ball Recoveries" v1={player1.s?.ball_recoveries_per_90} v2={player2.s?.ball_recoveries_per_90} />
            <DuelCard label="Dribble Runs" v1={player1.s?.progressive_runs_per_90} v2={player2.s?.progressive_runs_per_90} />
        </div>
      </div>
    </main>
  );
}

// SHARED COMPONENTS
function IdentityTile({ player, side, color, label }: any) {
    return (
        <div className={`md:col-span-4 bg-[#0A0A0A] border border-white/5 rounded-3xl p-10 flex flex-col justify-between min-h-[350px] ${side === 'left' ? 'border-l-4 border-l-lens-blue' : 'border-r-4 border-r-red-500 text-right'}`}>
          <div>
            <p className={`${color} text-[10px] font-black uppercase tracking-[0.4em] mb-4 italic`}>Subject {label}</p>
            <h1 className="text-6xl font-black tracking-tighter uppercase italic leading-[0.8] mb-4">{player.name}</h1>
            <p className="text-xl font-bold opacity-30 uppercase tracking-tighter">{player.club}</p>
          </div>
          <div className={`mt-8 flex justify-between items-end ${side === 'right' ? 'flex-row-reverse' : ''}`}>
             <div className="font-mono">
                <p className="text-[8px] text-white/20 uppercase mb-1">Market Value</p>
                <p className={`text-2xl font-black italic ${color}`}>€{((player.current_market_value || 0)/1000000).toFixed(1)}M</p>
             </div>
             <Fingerprint size={28} className="text-white/10" />
          </div>
        </div>
    );
}

function DuelCard({ label, v1, v2 }: any) {
  const val1 = Number(v1 || 0);
  const val2 = Number(v2 || 0);
  const total = val1 + val2;
  const p1Width = total === 0 ? 50 : (val1 / total) * 100;
  return (
    <div className="bg-[#0A0A0A] border border-white/5 rounded-3xl p-8 group transition-all font-mono text-center">
      <p className="text-[10px] font-black uppercase tracking-widest text-white/20 mb-8 italic">{label}</p>
      <div className="flex items-center justify-between gap-6">
        <span className={`text-3xl font-black italic ${val1 > val2 ? 'text-lens-blue' : 'text-white/10'}`}>{val1.toFixed(1)}</span>
        <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden flex">
            <div className={`h-full transition-all duration-1000 ${val1 > val2 ? 'bg-lens-blue' : 'bg-white/10'}`} style={{ width: `${p1Width}%` }} />
            <div className={`h-full transition-all duration-1000 ${val2 > val1 ? 'bg-red-500' : 'bg-white/10'}`} style={{ width: `${100 - p1Width}%` }} />
        </div>
        <span className={`text-3xl font-black italic ${val2 > val1 ? 'text-red-500' : 'text-white/10'}`}>{val2.toFixed(1)}</span>
      </div>
    </div>
  );
}