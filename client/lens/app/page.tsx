'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { Search, Zap, Globe, Target, Shield, Cpu, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import PassNetwork from './components/PassNetwork';

export default function Home() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [isFocused, setIsFocused] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [networkData, setNetworkData] = useState<any>(null);
  const [half, setHalf] = useState<'FirstHalf' | 'SecondHalf'>('FirstHalf');
  const match_id = "948c8dfd-54bf-499c-923f-ea56d0b7a212";


  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const fetchNetwork = async () => {
      const res = await fetch(
        `/api/pass-network?match_id=${match_id}&team=Barcelona&half=${half}`
      );
  
      const data = await res.json();
      setNetworkData(data);
    };
  
    fetchNetwork();
  }, []);
  
  if (!mounted) return null;

  const handleSearch = async (val: string) => {
    setQuery(val);
    if (val.length < 2) { setResults([]); return; }

    const { data } = await supabase
      .from('players')
      .select('name, club, tm_id, current_market_value, position')
      .ilike('name', `%${val}%`)
      .limit(6);

    if (data) setResults(data);
  };

  return (
    <main className="min-h-screen bg-[#020202] flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans">
      {/* Background Ambience */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-lens-blue/5 blur-[120px] rounded-full" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-lens-blue/5 blur-[120px] rounded-full" />
      
      {/* HUD Elements */}
      <div className="absolute top-10 left-10 flex gap-4 opacity-20 pointer-events-none">
        <Cpu size={14} className="text-lens-blue" />
        <span className="text-[10px] font-mono uppercase tracking-[0.3em] text-white">Neural Scout Active</span>
      </div>

      <div className="w-full max-w-3xl text-center relative z-10 mb-20">
        <div className="mb-12">
            <h1 className="text-9xl font-[1000] tracking-tighter text-white mb-2 italic uppercase leading-none select-none">
            LENS<span className="text-lens-blue">PRO</span>
            </h1>
            <div className="flex items-center justify-center gap-4 text-white/30">
                <div className="h-px w-12 bg-white/10" />
                <p className="uppercase tracking-[0.6em] text-[10px] font-black">Analytical Grade • 25/26</p>
                <div className="h-px w-12 bg-white/10" />
            </div>
        </div>

        <div className={`relative transition-all duration-500 transform ${isFocused ? 'scale-[1.02]' : 'scale-100'}`}>
          <div className={`absolute -inset-1 bg-gradient-to-r from-lens-blue/20 to-transparent rounded-3xl blur transition duration-500 ${isFocused ? 'opacity-100' : 'opacity-0'}`} />
          
          <div className="relative flex items-center">
            <Search className={`absolute left-8 transition-colors duration-300 ${isFocused ? 'text-lens-blue' : 'text-white/10'}`} size={24} />
            <input
                autoFocus
                onFocus={() => setIsFocused(true)}
                onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                type="text"
                placeholder="INITIALIZE PLAYER SEARCH..."
                className="w-full bg-[#0A0A0A]/80 backdrop-blur-xl border border-white/5 rounded-2xl py-8 pl-20 pr-10 text-2xl font-bold text-white placeholder:text-white/5 focus:outline-none focus:border-lens-blue/50 transition-all uppercase tracking-tight italic"
                value={query}
                onChange={(e) => handleSearch(e.target.value)}
            />
          </div>

          {results.length > 0 && (
            <div className="absolute w-full mt-4 bg-[#0A0A0A] border border-white/5 rounded-3xl overflow-hidden z-50 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.8)]">
              {results.map((p) => (
                <button
                  key={p.tm_id}
                  onClick={() => router.push(`/player/${p.tm_id}`)}
                  className="w-full flex items-center justify-between p-6 hover:bg-lens-blue/10 border-b border-white/5 last:border-0 transition-all group text-left"
                >
                  <div className="flex items-center gap-6">
                    <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center group-hover:bg-lens-blue/20 transition-colors">
                        <Target size={18} className="text-white/20 group-hover:text-lens-blue" />
                    </div>
                    <div>
                        <span className="text-white font-black uppercase italic text-xl tracking-tighter group-hover:text-lens-blue transition-colors block">
                            {p.name}
                        </span>
                        <div className="flex gap-3 items-center mt-1">
                            <span className="text-[10px] text-white/30 font-bold uppercase tracking-widest">{p.club}</span>
                            <div className="w-1 h-1 bg-white/10 rounded-full" />
                            <span className="text-[10px] text-lens-blue font-mono font-bold uppercase tracking-widest">{p.position || 'Elite'}</span>
                        </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                        <span className="text-[8px] font-black text-white/20 uppercase block">Est. Value</span>
                        <span className="text-lg font-mono font-black text-white/60 group-hover:text-white transition-colors block">
                            €{(p.current_market_value / 1000000).toFixed(1)}M
                        </span>
                    </div>
                    <Zap size={16} className="text-white/10 group-hover:text-lens-blue animate-pulse" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* DISCOVERY BANNER - NOW FULLY COMPLIANT */}
      {networkData && (
        <div className="my-20">
        <PassNetwork data={networkData} />
        </div>
      )}

      <Link
        href="/plots"
        className="max-w-4xl w-full bg-gradient-to-br from-lens-blue to-blue-900 rounded-[40px] p-12 flex justify-between items-center group relative overflow-hidden transition-all hover:scale-[0.99] cursor-pointer"
      >
        <span className="relative z-10 block">
          <span className="flex items-center gap-3 mb-6">
            <Globe size={16} className="text-white/40 animate-spin-slow" />
            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-white/50 italic leading-none">
              Global Scout Access
            </span>
          </span>
          <span className="text-6xl font-[1000] italic uppercase tracking-tighter leading-none mb-4 block">
            Market<br />Discovery
          </span>
          <span className="text-white/40 font-medium max-w-sm text-sm italic block">
            Visualize clinicality and creativity outliers across all top leagues in a single unified neural matrix.
          </span>
        </span>

        <span className="relative z-10 bg-black/20 p-6 rounded-full group-hover:bg-white group-hover:text-black transition-all flex items-center justify-center">
          <ChevronRight size={48} strokeWidth={1} />
        </span>

        <span className="absolute -bottom-20 -right-20 opacity-10 group-hover:opacity-20 transition-opacity pointer-events-none">
          <Search size={400} strokeWidth={1} />
        </span>
      </Link>

      <div className="mt-16 grid grid-cols-3 gap-12 opacity-40 group hover:opacity-100 transition-opacity relative z-10">
          <QuickLink icon={<Globe size={14}/>} label="Top 5 Leagues" />
          <QuickLink icon={<Shield size={14}/>} label="Defensive Anchors" />
          <QuickLink icon={<Zap size={14}/>} label="U-21 Prospects" />
      </div>
    </main>
  );
}

function QuickLink({ icon, label }: { icon: any, label: string }) {
    return (
        <div className="flex items-center justify-center gap-2 text-[10px] font-black uppercase tracking-widest cursor-pointer hover:text-lens-blue transition-colors">
            {icon} {label}
        </div>
    );
}