'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import ShotMap from '@/app/components/ShotMap';
import Heatmap from '@/app/components/Heatmap';
import PassMap from '@/app/components/PassMap';
import { ArrowLeft, Target, Zap, Activity, GitBranch, TrendingUp, ChevronRight } from 'lucide-react';
import Link from 'next/link';

type Tab = 'shots' | 'heat' | 'passes';

type PlayerInfo = {
  name: string;
  club: string;
  position: string;
  position_group: string;
  current_market_value: number;
  age: number;
  tm_id: string;
};

export default function PlayerPage() {
  const { id: tm_id } = useParams<{ id: string }>();
  const router = useRouter();

  const [player, setPlayer]       = useState<PlayerInfo | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('shots');
  const [mounted, setMounted]     = useState(false);

  // Data per tab
  const [shotData, setShotData]   = useState<any>(null);
  const [heatData, setHeatData]   = useState<any>(null);
  const [passData, setPassData]   = useState<any>(null);

  // Loading states per tab
  const [loading, setLoading]     = useState<Record<Tab, boolean>>({
    shots: false, heat: false, passes: false,
  });
  const [errors, setErrors]       = useState<Record<Tab, string | null>>({
    shots: null, heat: null, passes: null,
  });

  useEffect(() => { setMounted(true); }, []);

  // Fetch base player info from `players` table (TM data)
  useEffect(() => {
    if (!tm_id) return;
    supabase
      .from('players')
      .select('name, club, position, position_group, current_market_value, age, tm_id')
      .eq('tm_id', tm_id)
      .single()
      .then(({ data }) => { if (data) setPlayer(data); });
  }, [tm_id]);

  // Fetch tab data lazily — only when tab is first activated
  useEffect(() => {
    if (!tm_id || !mounted) return;

    const fetchers: Record<Tab, () => Promise<void>> = {
      shots: async () => {
        if (shotData) return;
        setLoading(l => ({ ...l, shots: true }));
        try {
          const res = await fetch(`/api/shot-map?tm_id=${tm_id}`);
          const data = await res.json();
          if (data.error) throw new Error(data.error);
          setShotData(data);
        } catch (e: any) {
          setErrors(err => ({ ...err, shots: e.message }));
        } finally {
          setLoading(l => ({ ...l, shots: false }));
        }
      },
      heat: async () => {
        if (heatData) return;
        setLoading(l => ({ ...l, heat: true }));
        try {
          const res = await fetch(`/api/heatmap?tm_id=${tm_id}`);
          const data = await res.json();
          if (data.error) throw new Error(data.error);
          setHeatData(data);
        } catch (e: any) {
          setErrors(err => ({ ...err, heat: e.message }));
        } finally {
          setLoading(l => ({ ...l, heat: false }));
        }
      },
      passes: async () => {
        if (passData) return;
        setLoading(l => ({ ...l, passes: true }));
        try {
          const res = await fetch(`/api/pass-map?tm_id=${tm_id}`);
          const data = await res.json();
          if (data.error) throw new Error(data.error);
          setPassData(data);
        } catch (e: any) {
          setErrors(err => ({ ...err, passes: e.message }));
        } finally {
          setLoading(l => ({ ...l, passes: false }));
        }
      },
    };

    fetchers[activeTab]();
  }, [activeTab, tm_id, mounted]);

  if (!mounted) return null;

  const tabs: { key: Tab; label: string; icon: React.ReactNode; desc: string }[] = [
    { key: 'shots',  label: 'Shot Map',  icon: <Target size={14} />,   desc: 'xG & shooting zones' },
    { key: 'heat',   label: 'Heatmap',   icon: <Activity size={14} />, desc: 'Positional density' },
    { key: 'passes', label: 'Pass Map',  icon: <GitBranch size={14} />, desc: 'Passing patterns' },
  ];

  const formatValue = (v: number) => {
    if (!v) return '—';
    if (v >= 1_000_000) return `€${(v / 1_000_000).toFixed(1)}M`;
    return `€${(v / 1_000).toFixed(0)}K`;
  };

  return (
    <main className="min-h-screen bg-[#020202] text-white font-sans">

      {/* ── Top nav ── */}
      <div className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#020202]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-white/30 hover:text-white transition-colors text-xs font-black uppercase tracking-widest"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          <span className="text-xs font-black uppercase tracking-[0.4em] text-white/20 italic">
            LENS<span className="text-[#00aaff]">PRO</span>
          </span>
          <div className="w-16" /> {/* spacer */}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pt-24 pb-16">

        {/* ── Player header ── */}
        <div className="mb-10 flex items-end justify-between gap-6 flex-wrap">
          <div>
            {/* League / club breadcrumb */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-white/20">
                {player?.club ?? '—'}
              </span>
              <ChevronRight size={10} className="text-white/10" />
              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-[#00aaff]/60">
                {player?.position ?? '—'}
              </span>
            </div>

            {/* Name */}
            <h1 className="text-6xl font-[1000] uppercase italic tracking-tighter leading-none text-white mb-1">
              {player?.name ?? tm_id}
            </h1>

            {/* Sub info */}
            <div className="flex items-center gap-4 mt-3">
              {player?.age && (
                <span className="text-[11px] font-mono text-white/30">
                  AGE <span className="text-white/60 font-black">{player.age}</span>
                </span>
              )}
              {player?.current_market_value && (
                <span className="text-[11px] font-mono text-white/30">
                  VALUE <span className="text-[#00aaff] font-black">{formatValue(player.current_market_value)}</span>
                </span>
              )}
              {player?.position_group && (
                <span className="text-[11px] font-mono text-white/30">
                  <span className="text-white/40 font-black uppercase">{player.position_group}</span>
                </span>
              )}
            </div>
          </div>

          {/* Quick xG stat if loaded */}
          {shotData && (
            <div className="bg-[#0a0f0b] border border-white/5 rounded-2xl px-6 py-4 text-right hidden sm:block">
              <div className="text-[9px] font-black uppercase tracking-widest text-white/20 mb-1">xG Performance</div>
              <div
                className="text-4xl font-black font-mono italic"
                style={{ color: shotData.stats.xg_diff >= 0 ? '#22c55e' : '#ef4444' }}
              >
                {shotData.stats.xg_diff >= 0 ? '+' : ''}{shotData.stats.xg_diff}
              </div>
              <div className="text-[10px] text-white/20 font-mono mt-1">
                {shotData.stats.goals}G / {shotData.stats.total_xg} xG
              </div>
            </div>
          )}
        </div>

        {/* ── Tabs ── */}
        <div className="flex gap-2 mb-8 border-b border-white/5 pb-0">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                flex items-center gap-2 px-5 py-3 text-xs font-black uppercase tracking-widest
                transition-all border-b-2 -mb-px
                ${activeTab === tab.key
                  ? 'text-white border-[#00aaff]'
                  : 'text-white/25 border-transparent hover:text-white/50 hover:border-white/10'
                }
              `}
            >
              {tab.icon}
              {tab.label}
              <span className="text-[9px] font-normal normal-case tracking-normal text-white/20 hidden lg:block">
                {tab.desc}
              </span>
            </button>
          ))}
        </div>

        {/* ── Tab content ── */}
        <div className="min-h-[520px]">

          {/* SHOT MAP */}
          {activeTab === 'shots' && (
            <>
              {loading.shots && <TabLoader label="Loading shot data..." />}
              {errors.shots  && <TabError msg={errors.shots} />}
              {!loading.shots && !errors.shots && shotData && (
                <ShotMap
                  shots={shotData.shots}
                  stats={shotData.stats}
                  playerName={shotData.player.name}
                />
              )}
              {!loading.shots && !errors.shots && !shotData && (
                <TabEmpty label="No shot data available" />
              )}
            </>
          )}

          {/* HEATMAP */}
          {activeTab === 'heat' && (
            <>
              {loading.heat && <TabLoader label="Loading positional data..." />}
              {errors.heat  && <TabError msg={errors.heat} />}
              {!loading.heat && !errors.heat && heatData && (
                <Heatmap
                  points={heatData.points}
                  stats={heatData.stats}
                  playerName={heatData.player.name}
                />
              )}
              {!loading.heat && !errors.heat && !heatData && (
                <TabEmpty label="No positional data available" />
              )}
            </>
          )}

          {/* PASS MAP */}
          {activeTab === 'passes' && (
            <>
              {loading.passes && <TabLoader label="Loading pass data..." />}
              {errors.passes  && <TabError msg={errors.passes} />}
              {!loading.passes && !errors.passes && passData && (
                <PassMap
                  passes={passData.passes}
                  stats={passData.stats}
                  playerName={passData.player.name}
                />
              )}
              {!loading.passes && !errors.passes && !passData && (
                <TabEmpty label="No pass data available" />
              )}
            </>
          )}

        </div>

        {/* ── Footer data note ── */}
        <div className="mt-12 pt-6 border-t border-white/5 flex items-center justify-between">
          <span className="text-[10px] font-mono text-white/15 uppercase tracking-widest">
            Data via Understat · WhoScored · Transfermarkt
          </span>
          <span className="text-[10px] font-black uppercase tracking-[0.4em] text-white/10 italic">
            LENS<span className="text-[#00aaff]/30">PRO</span>
          </span>
        </div>

      </div>
    </main>
  );
}

// ── Helpers ──────────────────────────────────────────

function TabLoader({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-80 gap-4">
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 rounded-full border-2 border-white/5" />
        <div className="absolute inset-0 rounded-full border-2 border-t-[#00aaff] animate-spin" />
      </div>
      <span className="text-[11px] font-mono uppercase tracking-widest text-white/20">{label}</span>
    </div>
  );
}

function TabError({ msg }: { msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-80 gap-3">
      <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
        <Zap size={16} className="text-red-400" />
      </div>
      <span className="text-[11px] font-mono uppercase tracking-widest text-red-400/60">{msg}</span>
    </div>
  );
}

function TabEmpty({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-80 gap-3">
      <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
        <TrendingUp size={16} className="text-white/20" />
      </div>
      <span className="text-[11px] font-mono uppercase tracking-widest text-white/20">{label}</span>
    </div>
  );
}