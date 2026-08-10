import React from 'react';
import PipelineDiagram from '../components/PipelineDiagram';

export default function Pipeline() {
  return (
    <div className="min-h-screen pt-32 px-8 max-w-[1400px] mx-auto">
      <div className="mb-16">
        <span className="text-[#00f0ff] text-[11px] tracking-[0.2em] font-bold uppercase font-mono">THE PIPELINE</span>
        <h1 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight text-[#e2e8f0]">
          Algorithmic flow.
        </h1>
        <p className="text-[#8c92a0] mt-4 max-w-2xl text-lg">
          Explore the individual stages of the ASP panorama stitching pipeline, visualizing the structural alignment and processing time distributions.
        </p>
      </div>

      <div className="border border-[#1a1c23] bg-[#0a0a0c] p-8 md:p-12 relative overflow-hidden group hover:border-[#00f0ff]/30 transition-all">
        <div className="absolute top-0 left-0 w-0 h-[2px] bg-[#ff0055] transition-all duration-700 group-hover:w-full" />
        <div className="mb-12 flex justify-between items-end">
          <div>
            <h3 className="text-xl font-bold text-[#e2e8f0]">ASP Stages</h3>
            <p className="text-[#8c92a0] text-sm mt-1">Sized by typical runtime share.</p>
          </div>
          <div className="text-xs font-mono text-[#4a4d57] border border-[#1a1c23] px-3 py-1 rounded">LIVE PREVIEW</div>
        </div>
        
        <PipelineDiagram height={300} />
      </div>
    </div>
  );
}
