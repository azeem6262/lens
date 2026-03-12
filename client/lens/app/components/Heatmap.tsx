'use client';
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

type Point = { x: number; y: number; event_type: string; outcome: string };
type Stats = { total_events: number; type_counts: Record<string, number> };
type Props = { points: Point[]; stats: Stats; playerName: string };

// Kernel density estimator
function kde(kernel: (v: number) => number, thresholds: number[], data: number[]) {
  return thresholds.map(x => [x, d3.mean(data, v => kernel(x - v)) ?? 0] as [number, number]);
}
function epanechnikovKernel(bandwidth: number) {
  return function (v: number) {
    v = v / bandwidth;
    return Math.abs(v) <= 1 ? 0.75 * (1 - v * v) / bandwidth : 0;
  };
}

export default function Heatmap({ points, stats, playerName }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!points?.length || !svgRef.current) return;

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
    const drawPitch = (g: d3.Selection<SVGGElement, unknown, null, undefined>) => {
      g.append('rect')
        .attr('x', xScale(0)).attr('y', yScale(100))
        .attr('width', xScale(100) - xScale(0))
        .attr('height', yScale(0) - yScale(100))
        .attr('fill', '#0d1f12').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

      // Halfway
      g.append('line')
        .attr('x1', xScale(50)).attr('y1', yScale(0))
        .attr('x2', xScale(50)).attr('y2', yScale(100))
        .attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

      // Centre circle
      g.append('circle')
        .attr('cx', xScale(50)).attr('cy', yScale(50))
        .attr('r', xScale(58.5) - xScale(50))
        .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);

      // Both penalty areas
      [[0, 17, 83], [100, 17, 83]].forEach(([px, y1, y2]) => {
        const x0 = px === 0 ? xScale(0) : xScale(83);
        const x1 = px === 0 ? xScale(17) : xScale(100);
        g.append('rect')
          .attr('x', Math.min(x0, x1)).attr('y', yScale(y2))
          .attr('width', Math.abs(x1 - x0))
          .attr('height', yScale(y1) - yScale(y2))
          .attr('fill', 'none').attr('stroke', '#1f3d2b').attr('stroke-width', 1.5);
      });

      // Goals
      [0, 100].forEach(gx => {
        g.append('rect')
          .attr('x', gx === 0 ? xScale(0) - 10 : xScale(100))
          .attr('y', yScale(54.8))
          .attr('width', 10)
          .attr('height', yScale(45.2) - yScale(54.8))
          .attr('fill', 'none').attr('stroke', '#2a4a35').attr('stroke-width', 2);
      });
    };

    const pitchGroup = svg.append('g');
    drawPitch(pitchGroup);

    // ---- Density grid via canvas-like approach with D3 contours ----
    const gridW = 80, gridH = 50;
    const density = new Array(gridW * gridH).fill(0);
    const bw = 8; // bandwidth in pitch coords

    points.forEach(p => {
      const gx = Math.floor((p.x / 100) * (gridW - 1));
      const gy = Math.floor(((100 - p.y) / 100) * (gridH - 1));
      for (let dx = -8; dx <= 8; dx++) {
        for (let dy = -8; dy <= 8; dy++) {
          const nx = gx + dx, ny = gy + dy;
          if (nx < 0 || nx >= gridW || ny < 0 || ny >= gridH) continue;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const weight = Math.max(0, 1 - dist / bw);
          density[ny * gridW + nx] += weight;
        }
      }
    });

    const maxDensity = d3.max(density) || 1;

    // ---- Contours ----
    const contours = d3.contours()
      .size([gridW, gridH])
      .thresholds(d3.range(0.05, 1.0, 0.05).map(t => t * maxDensity));

    const contourPaths = contours(density);

    // Custom colour scale: transparent → yellow → orange → red
    const colorScale = d3.scaleSequential()
      .domain([0, maxDensity * 0.85])
      .interpolator(t => {
        if (t < 0.15) return `rgba(255,220,0,${t * 2})`;
        if (t < 0.5)  return d3.interpolateYlOrRd((t - 0.15) / 0.35 * 0.5 + 0.2) as string;
        return d3.interpolateYlOrRd((t - 0.5) / 0.5 * 0.5 + 0.6) as string;
      });

    const scaleX = (W - PAD.left - PAD.right) / gridW;
    const scaleY = (H - PAD.top - PAD.bottom) / gridH;

    const contourGroup = svg.append('g').attr('transform', `translate(${PAD.left},${PAD.top})`);

    contourGroup.selectAll('path')
      .data(contourPaths)
      .enter().append('path')
      .attr('d', d3.geoPath(d3.geoIdentity().scale(1).reflectY(false)
        .fitExtent([[0, 0], [W - PAD.left - PAD.right, H - PAD.top - PAD.bottom]], contourPaths[0])))
      .attr('fill', d => colorScale(d.value))
      .attr('stroke', 'none')
      .attr('opacity', 0.85);

    // Redraw pitch lines on top of heatmap
    const pitchOverlay = svg.append('g');
    drawPitch(pitchOverlay);
    pitchOverlay.selectAll('rect, line, circle, path').attr('fill', 'none');

    // ---- Watermark ----
    svg.append('text')
      .attr('x', W - 14).attr('y', H - 12)
      .attr('text-anchor', 'end').attr('fill', '#ffffff').attr('opacity', 0.08)
      .style('font-size', '11px').style('font-weight', '700').style('letter-spacing', '0.15em')
      .text('LENSPRO');

  }, [points]);

  const topEvents = Object.entries(stats.type_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <div className="flex flex-col gap-4">
      {/* Stat strip */}
      <div className="grid grid-cols-4 gap-3">
        {topEvents.map(([type, count]) => (
          <div key={type} className="bg-[#0a0f0b] border border-white/5 rounded-xl p-4">
            <div className="text-[10px] font-black uppercase tracking-widest text-white/30 mb-1">{type}</div>
            <div className="text-2xl font-black font-mono text-white">{count}</div>
            <div className="text-[10px] text-white/20 font-mono mt-1">
              {(count / stats.total_events * 100).toFixed(0)}% of actions
            </div>
          </div>
        ))}
      </div>

      {/* Heatmap viz */}
      <div className="rounded-2xl overflow-hidden border border-white/5">
        <svg ref={svgRef} className="w-full" style={{ height: '420px' }} />
      </div>

      {/* Colour legend */}
      <div className="flex items-center gap-3 px-2">
        <span className="text-[10px] text-white/20 font-mono uppercase tracking-widest">Density</span>
        <div className="flex-1 h-2 rounded-full" style={{
          background: 'linear-gradient(to right, rgba(255,220,0,0.1), #fd8d3c, #bd0026)'
        }} />
        <span className="text-[10px] text-white/20 font-mono uppercase tracking-widest">High</span>
      </div>
    </div>
  );
}