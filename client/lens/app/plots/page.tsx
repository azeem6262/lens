'use client';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { TOP_5_LEAGUES, CLUB_TO_LEAGUE } from '@/lib/leagueMap';
import { 
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, 
  ResponsiveContainer, Label, ReferenceLine, Cell 
} from 'recharts';
import { Globe, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface PlayerData {
  id: string;
  name: string;
  club: string;
  league: string;
  position_group: string;
  xG: number;
  goals: number;
  xA: number;
  assists: number;
  color: string;
  performance: 'over' | 'under' | 'expected';
}

type PerformanceFilter = 'all' | 'over' | 'under' | 'expected';

export default function MarketDiscovery() {
  const [allData, setAllData] = useState<PlayerData[]>([]);
  const [filteredData, setFilteredData] = useState<PlayerData[]>([]);
  const [loading, setLoading] = useState(true);
  const [metric, setMetric] = useState<'scoring' | 'creation'>('scoring');
  const [selectedLeague, setSelectedLeague] = useState<string>('all');
  const [performanceFilter, setPerformanceFilter] = useState<PerformanceFilter>('all');
  const [leagues, setLeagues] = useState<string[]>([]);

  useEffect(() => {
    async function fetchMarketData() {
      setLoading(true);
      let allFetchedPlayers: any[] = [];
      let from = 0;
      const step = 1000; // Supabase default max per request
    
      try {
        // --- PAGINATION LOOP START ---
        while (true) {
          const { data: players, error } = await supabase
            .from('players')
            .select(`
              *, 
              stats_attackers(*), 
              stats_midfielders(*), 
              stats_defenders(*), 
              stats_goalkeepers(*)
            `)
            .range(from, from + step - 1); // Fetch a specific window of rows
    
          if (error) {
            console.error('Supabase error:', error);
            setLoading(false);
            return;
          }
    
          if (!players || players.length === 0) break; // Stop if no more players are found
    
          allFetchedPlayers = [...allFetchedPlayers, ...players];
          
          if (players.length < step) break; // Exit loop if we fetched the last partial page
          from += step; // Increment to the next chunk
        }
        // --- PAGINATION LOOP END ---
    
        const processed: PlayerData[] = [];
        const leagueSet = new Set<string>();
        
        // Process the full set of allFetchedPlayers instead of just one page
        for (const p of allFetchedPlayers) {
          let stats: any = null;
    
          const league = CLUB_TO_LEAGUE[p.club];
          if (!league) continue;
    
          leagueSet.add(league);
          
          if (p.stats_attackers) {
            stats = Array.isArray(p.stats_attackers) ? p.stats_attackers[0] : p.stats_attackers;
          } else if (p.stats_midfielders) {
            stats = Array.isArray(p.stats_midfielders) ? p.stats_midfielders[0] : p.stats_midfielders;
          } else if (p.stats_defenders) {
            stats = Array.isArray(p.stats_defenders) ? p.stats_defenders[0] : p.stats_defenders;
          } else if (p.stats_goalkeepers) {
            stats = Array.isArray(p.stats_goalkeepers) ? p.stats_goalkeepers[0] : p.stats_goalkeepers;
          }
        
          if (!stats) continue;
        
          const xG = parseFloat(stats.npxg ?? 0) || 0;
          const goals = parseFloat(stats.goals_scored ?? 0) || 0;
          const xA = parseFloat(stats.xa ?? 0) || 0;
          const assists = parseFloat(stats.assists_provided ?? 0) || 0;
        
          if (xG === 0 && goals === 0 && xA === 0 && assists === 0) continue;
        
          const diff =
            metric === 'scoring'
              ? goals - xG
              : assists - xA;
        
          let performance: 'over' | 'under' | 'expected' = 'expected';
          if (diff > 0.05) performance = 'over';
          else if (diff < -0.05) performance = 'under';
        
          processed.push({
            id: p.tm_id,
            name: p.name,
            club: p.club,
            league,
            position_group: p.position_group,
            xG,
            goals,
            xA,
            assists,
            color:
              p.position_group === 'Attacker'
                ? '#ef4444'
                : p.position_group === 'Midfielder'
                ? '#0070f3'
                : '#10b981',
            performance
          });
        }
        
        setAllData(processed);
        setLeagues(['all', ...Array.from(leagueSet).sort()]);
      } catch (err) {
        console.error('Data Fetch Error:', err);
      } finally {
        setLoading(false);
      }
    }
    
    fetchMarketData();
  }, []);

  // Apply filters whenever data, metric, league, or performance filter changes
  useEffect(() => {
    let filtered = [...allData];
    
    // Filter by metric (must have data for the selected metric)
    filtered = filtered.filter(p => {
      if (metric === 'scoring') {
        return p.xG > 0 || p.goals > 0;
      } else {
        return p.xA > 0 || p.assists > 0;
      }
    });
    
    // Identify and log outliers (for debugging)
    const values = metric === 'scoring' 
      ? filtered.map(p => Math.max(p.xG, p.goals))
      : filtered.map(p => Math.max(p.xA, p.assists));
    const maxValue = Math.max(...values);
    
    // If there's an extreme outlier (> 10), log it
    if (maxValue > 10) {
      const outliers = filtered.filter(p => {
        const val = metric === 'scoring' 
          ? Math.max(p.xG, p.goals)
          : Math.max(p.xA, p.assists);
        return val > 10;
      });
      console.log('Outliers detected:', outliers.map(o => ({
        name: o.name,
        xG: o.xG,
        goals: o.goals,
        xA: o.xA,
        assists: o.assists
      })));
    }
    
    // Recalculate performance based on current metric
    filtered = filtered.map(p => {
      const diff = metric === 'scoring' ? (p.goals - p.xG) : (p.assists - p.xA);
      let performance: 'over' | 'under' | 'expected' = 'expected';
      if (diff > 0.05) performance = 'over';
      else if (diff < -0.05) performance = 'under';
      return { ...p, performance };
    });
    
    // Filter by league
    if (selectedLeague !== 'all') {
      filtered = filtered.filter(p => p.league === selectedLeague);
    }
    
    // Filter by performance
    if (performanceFilter !== 'all') {
      filtered = filtered.filter(p => p.performance === performanceFilter);
    }
    
    setFilteredData(filtered);
  }, [allData, metric, selectedLeague, performanceFilter]);

  const getDomain = () => {
    if (filteredData.length === 0) return { min: 0, max: 1 };
    
    // Get all values based on metric
    const xValues = metric === 'scoring' 
      ? filteredData.map(d => d.xG)
      : filteredData.map(d => d.xA);
    const yValues = metric === 'scoring'
      ? filteredData.map(d => d.goals)
      : filteredData.map(d => d.assists);
    
    const allValues = [...xValues, ...yValues];
    
    // Remove extreme outliers (values > 99th percentile)
    const sorted = [...allValues].sort((a, b) => a - b);
    const p99Index = Math.floor(sorted.length * 0.99);
    const p99Value = sorted[p99Index] || 1;
    
    // Use 99th percentile or 2 (whichever is higher) as max, with 10% padding
    const maxValue = Math.max(p99Value, 2);
    const max = Math.ceil(maxValue * 1.1);
    
    return { min: 0, max };
  };

  const domain = getDomain();

  // Calculate stats for display
  const stats = {
    total: filteredData.length,
    overperformers: filteredData.filter(p => p.performance === 'over').length,
    underperformers: filteredData.filter(p => p.performance === 'under').length,
    expected: filteredData.filter(p => p.performance === 'expected').length
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#020202] flex items-center justify-center text-lens-blue font-mono animate-pulse uppercase tracking-[0.3em]">
        INITIALIZING_MARKET_SCAN...
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#020202] text-white p-6 lg:p-12 font-sans">
      {/* Header */}
      <div className="max-w-[1600px] mx-auto mb-8 flex flex-col md:flex-row justify-between items-end gap-8">
        <div>
          <div className="flex items-center gap-3 text-lens-blue mb-4">
            <Globe size={18} />
            <span className="text-[10px] font-black uppercase tracking-[0.5em] italic">Intelligence Matrix</span>
          </div>
          <h1 className="text-7xl font-[1000] italic uppercase tracking-tighter leading-none">
            Discovery<span className="text-white/10">_Matrix</span>
          </h1>
        </div>

        {/* Metric Toggle */}
        <div className="flex gap-4 bg-[#0A0A0A] border border-white/5 p-2 rounded-2xl">
          <button 
            onClick={() => setMetric('scoring')}
            className={`px-8 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
              metric === 'scoring' ? 'bg-lens-blue text-white' : 'text-white/30 hover:bg-white/5'
            }`}
          >
            Clinicality (xG/G)
          </button>
          <button 
            onClick={() => setMetric('creation')}
            className={`px-8 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
              metric === 'creation' ? 'bg-lens-blue text-white' : 'text-white/30 hover:bg-white/5'
            }`}
          >
            Creativity (xA/A)
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="max-w-[1600px] mx-auto mb-8 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* League Filter */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-2xl p-6">
          <label className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-3 block">
            Filter by League
          </label>
          <select
            value={selectedLeague}
            onChange={(e) => setSelectedLeague(e.target.value)}
            className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-lens-blue transition-all"
          >
            {leagues.map(league => (
              <option key={league} value={league}>
                {league === 'all' ? 'All Leagues' : league}
              </option>
            ))}
          </select>
        </div>

        {/* Performance Filter */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-2xl p-6">
          <label className="text-[10px] font-black uppercase tracking-widest text-white/40 mb-3 block">
            Performance Category
          </label>
          <div className="grid grid-cols-4 gap-2">
            <button
              onClick={() => setPerformanceFilter('all')}
              className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all ${
                performanceFilter === 'all' 
                  ? 'bg-white text-black' 
                  : 'bg-black/50 text-white/40 hover:bg-white/5'
              }`}
            >
              All
              <div className="text-[8px] mt-1">{stats.total}</div>
            </button>
            <button
              onClick={() => setPerformanceFilter('over')}
              className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all flex flex-col items-center justify-center gap-1 ${
                performanceFilter === 'over' 
                  ? 'bg-green-500 text-white' 
                  : 'bg-black/50 text-white/40 hover:bg-white/5'
              }`}
            >
              <TrendingUp size={14} />
              Over
              <div className="text-[8px]">{stats.overperformers}</div>
            </button>
            <button
              onClick={() => setPerformanceFilter('expected')}
              className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all flex flex-col items-center justify-center gap-1 ${
                performanceFilter === 'expected' 
                  ? 'bg-yellow-500 text-black' 
                  : 'bg-black/50 text-white/40 hover:bg-white/5'
              }`}
            >
              <Minus size={14} />
              Par
              <div className="text-[8px]">{stats.expected}</div>
            </button>
            <button
              onClick={() => setPerformanceFilter('under')}
              className={`px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all flex flex-col items-center justify-center gap-1 ${
                performanceFilter === 'under' 
                  ? 'bg-red-500 text-white' 
                  : 'bg-black/50 text-white/40 hover:bg-white/5'
              }`}
            >
              <TrendingDown size={14} />
              Under
              <div className="text-[8px]">{stats.underperformers}</div>
            </button>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="max-w-[1600px] mx-auto bg-[#0A0A0A] border border-white/5 rounded-[40px] p-12 relative overflow-hidden" style={{ height: '700px' }}>
        {filteredData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-white/50 gap-4">
            <p className="text-lg">No players match the selected filters</p>
            <p className="text-sm text-white/30">Try adjusting your league or performance filters</p>
          </div>
        ) : (
          <div style={{ width: '100%', height: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 40, bottom: 60, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1A1A1A" />
                
                <XAxis 
                  type="number" 
                  dataKey={metric === 'scoring' ? 'xG' : 'xA'} 
                  domain={[domain.min, domain.max]}
                  stroke="#666" 
                  fontSize={11} 
                  tickLine={false}
                >
                  <Label 
                    value={metric === 'scoring' ? 'EXPECTED GOALS (xG)' : 'EXPECTED ASSISTS (xA)'} 
                    position="insideBottom" 
                    fill="#666" 
                    offset={-40} 
                    style={{ fontSize: 10, fontWeight: 900, fontStyle: 'italic' }}
                  />
                </XAxis>
                
                <YAxis 
                  type="number" 
                  dataKey={metric === 'scoring' ? 'goals' : 'assists'} 
                  domain={[domain.min, domain.max]}
                  stroke="#666" 
                  fontSize={11} 
                  tickLine={false}
                >
                  <Label 
                    value={metric === 'scoring' ? 'ACTUAL GOALS' : 'ACTUAL ASSISTS'} 
                    angle={-90} 
                    position="insideLeft" 
                    fill="#666" 
                    offset={-45}
                    style={{ fontSize: 10, fontWeight: 900, fontStyle: 'italic' }}
                  />
                </YAxis>
                
                {/* Diagonal reference line (y = x) */}
                <ReferenceLine 
                  segment={[
                    { x: domain.min, y: domain.min }, 
                    { x: domain.max, y: domain.max }
                  ]} 
                  stroke="#444" 
                  strokeWidth={2} 
                  strokeDasharray="5 5" 
                />
                
                <Tooltip content={<CustomTooltip metric={metric} />} />
                
                <Scatter data={filteredData}>
                  {filteredData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.color}
                      fillOpacity={0.7}
                      stroke={entry.color}
                      strokeWidth={1}
                      r={6}
                      className="cursor-pointer hover:fill-opacity-100 transition-all"
                      onClick={() => window.location.href = `/player/${entry.id}`}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="max-w-[1600px] mx-auto mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#0A0A0A] border border-green-500/20 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="text-green-500" size={20} />
            <h3 className="text-sm font-black uppercase tracking-wider">Overperformers</h3>
          </div>
          <p className="text-xs text-white/40 leading-relaxed">
            Players performing above their expected metrics (actual &gt; expected + 0.05)
          </p>
        </div>
        
        <div className="bg-[#0A0A0A] border border-yellow-500/20 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <Minus className="text-yellow-500" size={20} />
            <h3 className="text-sm font-black uppercase tracking-wider">On Par</h3>
          </div>
          <p className="text-xs text-white/40 leading-relaxed">
            Players performing in line with expectations (±0.05 difference)
          </p>
        </div>
        
        <div className="bg-[#0A0A0A] border border-red-500/20 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <TrendingDown className="text-red-500" size={20} />
            <h3 className="text-sm font-black uppercase tracking-wider">Underperformers</h3>
          </div>
          <p className="text-xs text-white/40 leading-relaxed">
            Players performing below their expected metrics (actual &lt; expected - 0.05)
          </p>
        </div>
      </div>
    </main>
  );
}

function CustomTooltip({ active, payload, metric }: { active?: boolean; payload?: any; metric: 'scoring' | 'creation' }) {
  if (active && payload && payload.length) {
    const d = payload[0].payload as PlayerData;
    const diff = metric === 'scoring' ? (d.goals - d.xG) : (d.assists - d.xA);
    const diffSign = diff > 0 ? '+' : '';
    
    return (
      <div className="bg-black/95 backdrop-blur-xl border border-white/10 p-6 rounded-2xl shadow-2xl">
        <p className="text-lens-blue font-black italic uppercase text-lg leading-none mb-1">{d.name}</p>
        <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">{d.club}</p>
        <p className="text-[9px] text-white/30 uppercase tracking-wider mb-4">{d.league}</p>
        
        <div className="grid grid-cols-2 gap-6 mb-4">
          <div>
            <p className="text-[8px] uppercase tracking-widest text-white/30 mb-1">Expected</p>
            <p className="text-xl font-black italic text-white">
              {(metric === 'scoring' ? d.xG : d.xA).toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-[8px] uppercase tracking-widest text-white/30 mb-1">Actual</p>
            <p className="text-xl font-black italic text-white">
              {(metric === 'scoring' ? d.goals : d.assists).toFixed(2)}
            </p>
          </div>
        </div>
        
        <div className={`text-center py-2 px-4 rounded-lg ${
          d.performance === 'over' ? 'bg-green-500/20 text-green-400' :
          d.performance === 'under' ? 'bg-red-500/20 text-red-400' :
          'bg-yellow-500/20 text-yellow-400'
        }`}>
          <p className="text-[8px] uppercase tracking-widest mb-1">Difference</p>
          <p className="text-lg font-black italic">{diffSign}{diff.toFixed(2)}</p>
        </div>
      </div>
    );
  }
  return null;
}