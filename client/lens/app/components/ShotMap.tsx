'use client';
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

type Shot = {
  x: number; y: number; xg: number;
  result: string; situation: string;
  shot_type: string; minute: number;
  match?: { home: string; away: string; score: string; date: string } | null;
};

type Stats = {
  total: number; goals: number; total_xg: number;
  xg_diff: number; on_target: number; sot_pct: number; avg_xg: number;
};

type Props = { shots: Shot[]; stats: Stats; playerName: string };

const RESULT_STYLE: Record<string, { fill: string; stroke: string; opacity: number }> = {
  Goal:        { fill: '#ef4444', stroke: '#ef4444', opacity: 0.95 },
  SavedShot:   { fill: 'transparent', stroke: '#3b82f6', opacity: 0.8 },
  MissedShots: { fill: 'transparent', stroke: '#6b7280', opacity: 0.6 },
  BlockedShot: { fill: 'transparent', stroke: '#f59e0b', opacity: 0.7 },
  ShotOnPost:  { fill: 'transparent', stroke: '#a855f7', opacity: 0.8 },
};

export default function ShotMap({ shots, stats, playerName }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!shots || !svgRef.current) return;

    const W = 900, H = 560;
    const PAD = { top: 30, right: 30, bottom: 30, left: 30 };

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('background', 'linear-gradient(160deg, #0a0f0b 0%, #060a07 100%)')
      .style('border-radius', '16px');

    // ---- Scales (Opta 0-100 coords, attacking half: x 50-100) ----
    const xScale = d3.scaleLinear().domain([50, 100]).range([PAD.left, W - PAD.right]);
    const yScale = d3.scaleLinear().domain([0, 100]).range([H - PAD.bottom, PAD.top]);

    // ---- Pitch (half pitch) ----
    const g = svg.append('g');

    // Pitch surface
    g.append('rect')
      .attr('x', xScale(50)).attr('y', yScale(100))
      .attr('width', xScale(100) - xScale(50))
      .attr('height', yScale(0) - yScale(100))
      .attr('fill', '#0d1f12').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    // Halfway line
    g.append('line')
      .attr('x1', xScale(50)).attr('y1', yScale(0))
      .attr('x2', xScale(50)).attr('y2', yScale(100))
      .attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    // Penalty area (83–100, 21–79 in Opta)
    g.append('rect')
      .attr('x', xScale(83)).attr('y', yScale(79))
      .attr('width', xScale(100) - xScale(83))
      .attr('height', yScale(21) - yScale(79))
      .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    // Six yard box (94–100, 36–64)
    g.append('rect')
      .attr('x', xScale(94)).attr('y', yScale(64))
      .attr('width', xScale(100) - xScale(94))
      .attr('height', yScale(36) - yScale(64))
      .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1);

    // Goal
    g.append('rect')
      .attr('x', xScale(100)).attr('y', yScale(54.8))
      .attr('width', 10).attr('height', yScale(45.2) - yScale(54.8))
      .attr('fill', 'none').attr('stroke', '#2a4a35').attr('stroke-width', 2);

    // Penalty spot
    g.append('circle')
      .attr('cx', xScale(88.5)).attr('cy', yScale(50))
      .attr('r', 2.5).attr('fill', '#1f3d2b');

    // Penalty arc
    const arc = d3.arc()
      .innerRadius(0).outerRadius(xScale(94) - xScale(88.5))
      .startAngle(-Math.PI * 0.4).endAngle(Math.PI * 0.4);
    g.append('path')
      .attr('d', arc as any)
      .attr('transform', `translate(${xScale(88.5)},${yScale(50)})`)
      .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    // ---- Tooltip ----
    const tooltip = d3.select('body').append('div')
      .style('position', 'absolute')
      .style('background', '#0a0a0a')
      .style('border', '1px solid #1f2937')
      .style('color', '#e5e7eb')
      .style('padding', '10px 14px')
      .style('border-radius', '8px')
      .style('font-size', '11px')
      .style('font-family', 'monospace')
      .style('opacity', 0)
      .style('pointer-events', 'none')
      .style('z-index', 9999)
      .style('box-shadow', '0 8px 32px rgba(0,0,0,0.6)');

    // ---- Shots ----
    const sizeScale = d3.scaleSqrt()
      .domain([0, d3.max(shots, s => s.xg) || 1])
      .range([4, 22]);

    const shotGroups = g.selectAll('.shot')
      .data(shots).enter()
      .append('g').attr('class', 'shot')
      .style('cursor', 'crosshair');

    shotGroups.append('circle')
      .attr('cx', d => xScale(d.x))
      .attr('cy', d => yScale(d.y))
      .attr('r', d => sizeScale(d.xg))
      .attr('fill', d => RESULT_STYLE[d.result]?.fill ?? 'transparent')
      .attr('stroke', d => RESULT_STYLE[d.result]?.stroke ?? '#6b7280')
      .attr('stroke-width', 1.5)
      .attr('opacity', d => RESULT_STYLE[d.result]?.opacity ?? 0.6)
      .style('filter', d => d.result === 'Goal' ? 'drop-shadow(0 0 6px rgba(239,68,68,0.6))' : 'none')
      .on('mouseover', function (event, d) {
        d3.select(this).attr('stroke-width', 2.5).attr('opacity', 1);
        tooltip.style('opacity', 1).html(`
          <div style="font-weight:700;color:#fff;margin-bottom:4px">${d.result.replace('Shots','').replace('Shot','')}</div>
          <div>xG: <span style="color:#00ff85;font-weight:700">${d.xg.toFixed(3)}</span></div>
          <div>Situation: ${d.situation}</div>
          <div>Foot: ${d.shot_type}</div>
          <div>Minute: ${d.minute}'</div>
          ${d.match ? `<div style="margin-top:4px;color:#6b7280">${d.match.home} ${d.match.score} ${d.match.away}</div>` : ''}
        `)
        .style('left', event.pageX + 14 + 'px')
        .style('top', event.pageY - 28 + 'px');
      })
      .on('mousemove', function (event) {
        tooltip.style('left', event.pageX + 14 + 'px').style('top', event.pageY - 28 + 'px');
      })
      .on('mouseout', function (_, d) {
        d3.select(this)
          .attr('stroke-width', 1.5)
          .attr('opacity', RESULT_STYLE[d.result]?.opacity ?? 0.6);
        tooltip.style('opacity', 0);
      });

    // ---- Legend ----
    const legendData = [
      { label: 'Goal', ...RESULT_STYLE['Goal'] },
      { label: 'Saved', ...RESULT_STYLE['SavedShot'] },
      { label: 'Missed', ...RESULT_STYLE['MissedShots'] },
      { label: 'Blocked', ...RESULT_STYLE['BlockedShot'] },
      { label: 'Post', ...RESULT_STYLE['ShotOnPost'] },
    ];
    const legend = svg.append('g').attr('transform', `translate(${PAD.left + 8}, ${H - PAD.bottom - 12})`);
    legendData.forEach((d, i) => {
      const lx = i * 110;
      legend.append('circle')
        .attr('cx', lx).attr('cy', 0).attr('r', 6)
        .attr('fill', d.fill).attr('stroke', d.stroke).attr('stroke-width', 1.5).attr('opacity', d.opacity);
      legend.append('text')
        .attr('x', lx + 12).attr('y', 4)
        .attr('fill', '#9ca3af').style('font-size', '10px').style('font-family', 'monospace')
        .text(d.label);
    });

    // ---- Watermark ----
    svg.append('text')
      .attr('x', W - 14).attr('y', H - 12)
      .attr('text-anchor', 'end').attr('fill', '#ffffff').attr('opacity', 0.08)
      .style('font-size', '11px').style('font-weight', '700').style('letter-spacing', '0.15em')
      .text('LENSPRO');

    return () => { tooltip.remove(); };
  }, [shots]);

  // ---- Zone stats ----
  const zones = (() => {
    const xZ = [[50,66],[66,83],[83,100]];
    const yZ = [[0,33],[33,67],[67,100]];
    const labels = { x: ['Deep','Mid','Box'], y: ['Left','Ctr','Right'] };
    return xZ.map((xr, xi) => yZ.map((yr, yi) => {
      const z = shots.filter(s => s.x >= xr[0] && s.x < xr[1] && s.y >= yr[0] && s.y < yr[1]);
      return {
        label: `${labels.x[xi]} ${labels.y[yi]}`,
        shots: z.length,
        goals: z.filter(s => s.result === 'Goal').length,
        xg: z.reduce((a,s) => a+s.xg, 0),
      };
    })).flat().sort((a,b) => b.shots - a.shots).slice(0, 3);
  })();

  return (
    <div className="flex flex-col gap-4">
      {/* Stat strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Goals', value: stats.goals, sub: `from ${stats.total_xg} xG` },
          { label: 'xG Diff', value: (stats.xg_diff >= 0 ? '+' : '') + stats.xg_diff, sub: 'overperformance', color: stats.xg_diff >= 0 ? '#22c55e' : '#ef4444' },
          { label: 'On Target', value: `${stats.on_target} (${stats.sot_pct}%)`, sub: `${stats.total} total shots` },
          { label: 'Avg xG/Shot', value: stats.avg_xg, sub: 'per attempt' },
        ].map(s => (
          <div key={s.label} className="bg-[#0a0f0b] border border-white/5 rounded-xl p-4">
            <div className="text-[10px] font-black uppercase tracking-widest text-white/30 mb-1">{s.label}</div>
            <div className="text-2xl font-black font-mono italic" style={{ color: (s as any).color || '#ffffff' }}>{s.value}</div>
            <div className="text-[10px] text-white/20 font-mono mt-1">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Pitch viz */}
      <div className="rounded-2xl overflow-hidden border border-white/5">
        <svg ref={svgRef} className="w-full" style={{ height: '420px' }} />
      </div>

      {/* Hot zones */}
      <div className="grid grid-cols-3 gap-3">
        {zones.map(z => (
          <div key={z.label} className="bg-[#0a0f0b] border border-white/5 rounded-xl p-3 flex justify-between items-center">
            <div>
              <div className="text-[9px] font-black uppercase tracking-widest text-white/30">{z.label}</div>
              <div className="text-lg font-black font-mono text-white">{z.shots} <span className="text-xs text-white/30">shots</span></div>
            </div>
            <div className="text-right">
              <div className="text-[9px] text-white/20 font-mono">{z.xg.toFixed(2)} xG</div>
              {z.goals > 0 && <div className="text-xs font-black text-red-400">{z.goals}G</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}