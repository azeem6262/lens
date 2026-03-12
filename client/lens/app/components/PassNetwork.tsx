'use client';
import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

type Node = {
  id: string;
  name?: string;
  x: number;
  y: number;
  size: number;
  touches?: number;
};

type Edge = {
  source: string;
  target: string;
  width: number;
  completion: number;
};

type Props = {
  data: {
    nodes: Node[];
    edges: Edge[];
  };
};

export default function PassNetwork({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!data || !svgRef.current) return;

    const width = 900;
    const height = 550;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    svg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("preserveAspectRatio", "xMidYMid meet")
      .style("background", "linear-gradient(180deg, #0d1b12 0%, #08100b 100%)")
      .style("border-radius", "16px");

    // ---------------- SCALES ----------------

    const xScale = d3.scaleLinear().domain([0, 100]).range([60, width - 60]);
    const yScale = d3.scaleLinear().domain([0, 100]).range([height - 60, 60]);

    // ---------------- PITCH MARKINGS ----------------

    const pitch = svg.append("g");

    pitch.append("rect")
      .attr("x", 40)
      .attr("y", 40)
      .attr("width", width - 80)
      .attr("height", height - 80)
      .attr("stroke", "#1f3d2b")
      .attr("stroke-width", 2)
      .attr("fill", "none");

    pitch.append("line")
      .attr("x1", width / 2)
      .attr("y1", 40)
      .attr("x2", width / 2)
      .attr("y2", height - 40)
      .attr("stroke", "#1f3d2b")
      .attr("stroke-width", 2);

    pitch.append("circle")
      .attr("cx", width / 2)
      .attr("cy", height / 2)
      .attr("r", 60)
      .attr("stroke", "#1f3d2b")
      .attr("stroke-width", 2)
      .attr("fill", "none");

    // ---------------- TOOLTIP ----------------

    const tooltip = d3.select("body")
      .append("div")
      .style("position", "absolute")
      .style("background", "#111")
      .style("color", "#fff")
      .style("padding", "8px 12px")
      .style("border-radius", "6px")
      .style("font-size", "12px")
      .style("opacity", 0)
      .style("pointer-events", "none")
      .style("box-shadow", "0 4px 20px rgba(0,0,0,0.4)");

    // ---------------- EDGES ----------------

    svg.selectAll(".link")
      .data(data.edges)
      .enter()
      .append("line")
      .attr("x1", d => xScale(data.nodes.find(n => n.id === d.source)?.x || 0))
      .attr("y1", d => yScale(data.nodes.find(n => n.id === d.source)?.y || 0))
      .attr("x2", d => xScale(data.nodes.find(n => n.id === d.target)?.x || 0))
      .attr("y2", d => yScale(data.nodes.find(n => n.id === d.target)?.y || 0))
      .attr("stroke", "#00ff85")
      .attr("stroke-opacity", d => Math.max(0.25, d.completion))
      .attr("stroke-width", d => d.width)
      .attr("stroke-linecap", "round")
      .style("filter", "drop-shadow(0px 0px 4px rgba(0,255,133,0.4))");

    // ---------------- NODES ----------------

    const nodeGroups = svg.selectAll(".node")
      .data(data.nodes)
      .enter()
      .append("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .on("mouseover", function (event, d) {
        d3.select(this).select("circle")
          .attr("stroke", "#00ff85")
          .attr("stroke-width", 4);

        tooltip
          .style("opacity", 1)
          .html(`
            <strong>${d.name}</strong><br/>
            Touches: ${d.touches ?? 0}
          `)
          .style("left", event.pageX + 10 + "px")
          .style("top", event.pageY - 20 + "px");
      })
      .on("mouseout", function () {
        d3.select(this).select("circle")
          .attr("stroke", "#ffffff")
          .attr("stroke-width", 2);

        tooltip.style("opacity", 0);
      });

    nodeGroups.append("circle")
      .attr("cx", d => xScale(d.x))
      .attr("cy", d => yScale(d.y))
      .attr("r", d => d.size)
      .attr("fill", "#121212")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 2)
      .style("filter", "drop-shadow(0px 0px 10px rgba(0,255,133,0.25))");

    // ---------------- PLAYER INITIALS ----------------

    nodeGroups.append("text")
      .attr("x", d => xScale(d.x))
      .attr("y", d => yScale(d.y) + 4)
      .attr("text-anchor", "middle")
      .attr("fill", "#ffffff")
      .style("font-family", "Inter, sans-serif")
      .style("font-weight", "600")
      .style("font-size", "10px")
      .text(d => {
        if (!d.name) return "";
        const parts = d.name.split(" ");
        if (parts.length === 1) return parts[0][0].toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      });

    // ---------------- WATERMARK ----------------

    svg.append("text")
      .attr("x", width - 30)
      .attr("y", height - 20)
      .attr("text-anchor", "end")
      .attr("fill", "#ffffff")
      .attr("opacity", 0.15)
      .style("font-size", "14px")
      .style("font-weight", "700")
      .text("LENSPRO ANALYTICS");

  }, [data]);

  return (
    <div className="w-full flex justify-center items-center p-6 bg-[#0b0f0c] rounded-2xl shadow-2xl">
      <svg
        ref={svgRef}
        className="w-full max-w-6xl"
        style={{ height: "550px" }}
      />
    </div>
  );
  
}
