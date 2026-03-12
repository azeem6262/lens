'use client';
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

type Pass = {
  x: number; y: number; end_x: number; end_y: number;
  success: boolean; is_key: boolean; is_progressive: boolean;
  minute: number; period: string;
};
type Stats = {
  total: number; successful: number; completion_pct: number;
  key_passes: number; progressive: number;
};
type Props = { passes: Pass[]; stats: Stats; playerName: string };

export default function PassMap({ passes, stats, playerName }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!passes?.length || !svgRef.current) return;

    const W = 900, H = 560;
    const PAD = { top: 30, right: 30, bottom: 30, left: 30 };

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('background', 'linear-gradient(160deg, #0a0f0b 0%, #060a07 100%)')
      .style('border-radius', '16px');

    const xScale = d3.scaleLinear().domain([0, 100]).range([PAD.left, W - PAD.right]);
    const yScale = d3.scaleLinear().domain([0, 100]).range([H - PAD.bottom, PAD.top]);

    // ---- Pitch ----
    const g = svg.append('g');

    g.append('rect')
      .attr('x', xScale(0)).attr('y', yScale(100))
      .attr('width', xScale(100) - xScale(0))
      .attr('height', yScale(0) - yScale(100))
      .attr('fill', '#0d1f12').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    g.append('line')
      .attr('x1', xScale(50)).attr('y1', yScale(0))
      .attr('x2', xScale(50)).attr('y2', yScale(100))
      .attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    g.append('circle')
      .attr('cx', xScale(50)).attr('cy', yScale(50))
      .attr('r', xScale(58.5) - xScale(50))
      .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

    [[0, 17, 83], [100, 17, 83]].forEach(([px, y1, y2]) => {
      const x0 = px === 0 ? xScale(0) : xScale(83);
      const x1 = px === 0 ? xScale(17) : xScale(100);
      g.append('rect')
        .attr('x', Math.min(x0, x1)).attr('y', yScale(y2))
        .attr('width', Math.abs(x1 - x0))
        .attr('height', yScale(y1) - yScale(y2))
        .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);
    });

    [0, 100].forEach(gx => {
      g.append('rect')
        .attr('x', gx === 0 ? xScale(0) - 10 : xScale(100))
        .attr('y', yScale(54.8))
        .attr('width', 10)
        .attr('height', yScale(45.2) - yScale(54.8))
        .attr('fill', 'none').attr('stroke', '#2a4a35').attr('stroke-width', 2);
    });

    // ---- Arrow marker defs ----
    const defs = svg.append('defs');

    [
      { id: 'arrow-success',     color: '#22c55e' },
      { id: 'arrow-fail',        color: '#ef4444' },
      { id: 'arrow-key',         color: '#f59e0b' },
      { id: 'arrow-progressive', color: '#3b82f6' },
    ].forEach(({ id, color }) => {
      defs.append('marker')
        .attr('id', id)
        .attr('viewBox', '0 -4 8 8')
        .attr('refX', 6).attr('refY', 0)
        .attr('markerWidth', 4).attr('markerHeight', 4)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color).attr('opacity', 0.8);
    });

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

    // ---- Draw passes ----
    // Sample for performance if too many
    const sample = passes.length > 500
      ? [...passes.filter(p => p.is_key || p.is_progressive), ...passes.filter(p => !p.is_key && !p.is_progressive).slice(0, 400)]
      : passes;

    const passGroups = g.selectAll('.pass')
      .data(sample).enter()
      .append('g').attr('class', 'pass')
      .style('cursor', 'crosshair');

    passGroups.append('line')
      .attr('x1', d => xScale(d.x))
      .attr('y1', d => yScale(d.y))
      .attr('x2', d => xScale(d.end_x))
      .attr('y2', d => yScale(d.end_y))
      .attr('stroke', d => {
        if (d.is_key) return '#f59e0b';
        if (d.is_progressive) return '#3b82f6';
        return d.success ? '#22c55e' : '#ef4444';
      })
      .attr('stroke-width', d => d.is_key ? 2 : 1)
      .attr('stroke-opacity', d => d.is_key ? 0.9 : d.is_progressive ? 0.65 : 0.35)
      .attr('marker-end', d => {
        if (d.is_key) return 'url(#arrow-key)';
        if (d.is_progressive) return 'url(#arrow-progressive)';
        return d.success ? 'url(#arrow-success)' : 'url(#arrow-fail)';
      })
      .on('mouseover', function (event, d) {
        d3.select(this).attr('stroke-opacity', 1).attr('stroke-width', 2);
        tooltip.style('opacity', 1).html(`
          <div style="font-weight:700;color:${d.is_key ? '#f59e0b' : d.success ? '#22c55e' : '#ef4444'};margin-bottom:4px">
            ${d.is_key ? 'KEY PASS' : d.is_progressive ? 'PROGRESSIVE' : d.success ? 'COMPLETE' : 'INCOMPLETE'}
          </div>
          <div>From: (${d.x.toFixed(0)}, ${d.y.toFixed(0)})</div>
          <div>To: (${d.end_x.toFixed(0)}, ${d.end_y.toFixed(0)})</div>
          <div>Min: ${d.minute}'  ${d.period}</div>
        `)
        .style('left', event.pageX + 14 + 'px')
        .style('top', event.pageY - 28 + 'px');
      })
      .on('mousemove', function (event) {
        tooltip.style('left', event.pageX + 14 + 'px').style('top', event.pageY - 28 + 'px');
      })
      .on('mouseout', function (_, d) {
        d3.select(this)
          .attr('stroke-opacity', d.is_key ? 0.9 : d.is_progressive ? 0.65 : 0.35)
          .attr('stroke-width', d.is_key ? 2 : 1);
        tooltip.style('opacity', 0);
      });

    // ---- Legend ----
    const legendData = [
      { color: '#22c55e', label: 'Completed' },
      { color: '#ef4444', label: 'Incomplete' },
      { color: '#3b82f6', label: 'Progressive' },
      { color: '#f59e0b', label: 'Key Pass' },
    ];
    const legend = svg.append('g').attr('transform', `translate(${PAD.left + 8}, ${H - PAD.bottom - 12})`);
    legendData.forEach((d, i) => {
      const lx = i * 120;
      legend.append('line')
        .attr('x1', lx).attr('y1', 0).attr('x2', lx + 18).attr('y2', 0)
        .attr('stroke', d.color).attr('stroke-width', 2);
      legend.append('text')
        .attr('x', lx + 24).attr('y', 4)
        .attr('fill', '#9ca3af').style('font-size', '10px').style('font-family', 'monospace')
        .text(d.label);
    });

    svg.append('text')
      .attr('x', W - 14).attr('y', H - 12)
      .attr('text-anchor', 'end').attr('fill', '#ffffff').attr('opacity', 0.08)
      .style('font-size', '11px').style('font-weight', '700').style('letter-spacing', '0.15em')
      .text('LENSPRO');

    return () => { tooltip.remove(); };
  }, [passes]);

  return (
    <div className="flex flex-col gap-4">
      {/* Stat strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Completion', value: `${stats.completion_pct}%`, sub: `${stats.successful}/${stats.total} passes` },
          { label: 'Key Passes', value: stats.key_passes, sub: 'chance-creating', color: '#f59e0b' },
          { label: 'Progressive', value: stats.progressive, sub: 'moving ball forward', color: '#3b82f6' },
          { label: 'Total Passes', value: stats.total, sub: 'in dataset' },
        ].map(s => (
          <div key={s.label} className="bg-[#0a0f0b] border border-white/5 rounded-xl p-4">
            <div className="text-[10px] font-black uppercase tracking-widest text-white/30 mb-1">{s.label}</div>
            <div className="text-2xl font-black font-mono italic" style={{ color: (s as any).color || '#ffffff' }}>{s.value}</div>
            <div className="text-[10px] text-white/20 font-mono mt-1">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Pass map viz */}
      <div className="rounded-2xl overflow-hidden border border-white/5">
        <svg ref={svgRef} className="w-full" style={{ height: '420px' }} />
      </div>
    </div>
  );
}