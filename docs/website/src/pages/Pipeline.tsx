import React, { useState } from 'react';
import PipelineDiagram from '../components/PipelineDiagram';
import { submoduleSites } from '../constants/submodules';

export default function Pipeline() {
  const [selectedSubmodule, setSelectedSubmodule] = useState<string | null>(null);

  const localPaths: Record<string, string> = {
    'anime-stitch-pipeline': '/submodules/ASP/docs/website/index.html',
    'cel-shaded-generator': '/submodules/CSG/docs/website/index.html',
    'content-recommendation-engine': '/submodules/CRE/docs/website/index.html',
    'hybrid-image-editor': '/submodules/HIE/docs/website/index.html',
  };

  return (
    <div className="min-h-screen pt-32 px-8 max-w-[1400px] mx-auto pb-24">
      <div className="mb-16">
        <span className="text-[#00f0ff] text-[11px] tracking-[0.2em] font-bold uppercase font-mono">THE PIPELINE</span>
        <h1 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight text-[#e2e8f0]">
          Algorithmic flow & Submodule Architecture.
        </h1>
        <p className="text-[#8c92a0] mt-4 max-w-2xl text-lg">
          Explore the individual stages of the panorama stitching pipeline, and select any submodule below to open its dedicated interactive project website.
        </p>
      </div>

      {/* ASP Pipeline Diagram */}
      <div className="border border-[#1a1c23] bg-[#0a0a0c] p-8 md:p-12 relative overflow-hidden group hover:border-[#00f0ff]/30 transition-all mb-16">
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

      {/* Submodules Explorer Section */}
      <div className="border-t border-[#1a1c23] pt-12">
        <div className="mb-8">
          <span className="text-[#ff0055] text-[11px] tracking-[0.2em] font-bold uppercase font-mono">SUBMODULE SITES</span>
          <h2 className="text-2xl md:text-3xl font-bold mt-2 text-[#e2e8f0]">
            Integrated Submodules
          </h2>
          <p className="text-[#8c92a0] text-sm mt-2">
            Select a submodule below to view its project overview, architecture diagram, and documentation website.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {submoduleSites.map((site) => {
            const isSelected = selectedSubmodule === site.slug;
            const targetUrl = localPaths[site.slug] || site.url;

            return (
              <div 
                key={site.slug}
                className={`border bg-[#0a0a0c] p-6 rounded-xl relative flex flex-col justify-between transition-all cursor-pointer ${
                  isSelected 
                    ? 'border-[#00f0ff] bg-[#00f0ff]/5 shadow-[0_0_20px_rgba(0,240,255,0.15)]' 
                    : 'border-[#1a1c23] hover:border-[#00f0ff]/40'
                }`}
                onClick={() => setSelectedSubmodule(isSelected ? null : site.slug)}
              >
                <div>
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-[10px] font-mono font-bold text-[#00f0ff] uppercase px-2 py-0.5 border border-[#00f0ff]/20 rounded">
                      {site.slug.split('-').map(s => s[0]).join('').toUpperCase()}
                    </span>
                    <a 
                      href={targetUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-mono text-[#8c92a0] hover:text-[#00f0ff] flex items-center gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>New Tab</span>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                      </svg>
                    </a>
                  </div>
                  <h3 className="font-bold text-base text-[#e2e8f0] mb-2">{site.title}</h3>
                  <p className="text-xs text-[#8c92a0] leading-relaxed mb-4">{site.description}</p>
                </div>

                <button
                  className={`w-full py-2 px-3 rounded text-xs font-mono font-bold border transition-all ${
                    isSelected
                      ? 'bg-[#00f0ff] text-[#0a0a0c] border-[#00f0ff]'
                      : 'bg-[#14161d] text-[#00f0ff] border-[#1a1c23] hover:border-[#00f0ff]/40'
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedSubmodule(isSelected ? null : site.slug);
                  }}
                >
                  {isSelected ? 'Close Website Viewer' : 'Open Website Preview'}
                </button>
              </div>
            );
          })}
        </div>

        {/* Embedded Submodule Website Viewer Frame */}
        {selectedSubmodule && (
          <div className="border border-[#00f0ff]/30 bg-[#0d0e12] rounded-xl p-4 overflow-hidden">
            <div className="flex justify-between items-center pb-3 border-b border-[#1a1c23] mb-4">
              <div className="flex items-center space-x-2">
                <div className="w-2.5 h-2.5 bg-[#00f0ff] rounded-full animate-pulse"></div>
                <span className="text-xs font-mono font-bold text-[#00f0ff]">
                  PREVIEWING: {selectedSubmodule.toUpperCase()}
                </span>
              </div>
              <button 
                onClick={() => setSelectedSubmodule(null)}
                className="text-xs font-mono text-[#8c92a0] hover:text-white border border-[#1a1c23] px-3 py-1 rounded"
              >
                Close Frame
              </button>
            </div>
            <iframe 
              src={localPaths[selectedSubmodule] || submoduleSites.find(s => s.slug === selectedSubmodule)?.url} 
              title="Submodule Website Preview"
              className="w-full h-[650px] rounded border border-[#1a1c23]"
            />
          </div>
        )}
      </div>
    </div>
  );
}
