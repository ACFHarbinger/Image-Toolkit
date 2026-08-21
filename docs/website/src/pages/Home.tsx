import { motion } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import {
  Camera,
  Layers3,
  ScanLine,
} from "lucide-react";
import Viewfinder2D from "../components/Viewfinder2D";
import PipelineDiagram from "../components/PipelineDiagram";
import "../App.css";

// Keep the optical demo out of the initial route chunk. The homepage remains
// useful on machines that do not need WebGL, while the scene still loads in
// the hero when the browser supports it.
const Hero3D = lazy(() => import("../components/Hero3D"));

const modules = [
  {
    number: "01",
    title: "Capture & Index",
    text: "Bring massive anime frame libraries into a searchable, observable point-cloud workspace.",
    detail: "Start with references, sprite sheets, and source frames. Keep provenance attached while the toolkit turns a visual collection into something you can search and inspect.",
    action: "Read the development guide",
    href: "/docs/DEVELOPMENT.md",
    icon: Camera,
  },
  {
    number: "02",
    title: "Understand Structure",
    text: "Measure visual alignment, structural similarity, and motion using sub-pixel precision.",
    detail: "Inspect feature matches, motion, and alignment signals without hiding uncertainty behind a single score. The pipeline is an instrument, not a black box.",
    action: "Inspect the pipeline",
    href: "/pipeline",
    icon: ScanLine,
  },
  {
    number: "03",
    title: "Compose & Render",
    text: "Stitch panoramas with robust bundle adjustment and output artifacts backed by honest evidence.",
    detail: "Compose usable panoramas and game-art assets while preserving the settings, inputs, and review trail needed to understand the output later.",
    action: "Open quality dashboard",
    href: "/dashboard",
    icon: Layers3,
  },
];

export default function Home() {
  const [activeModule, setActiveModule] = useState(0);

  return (
    <div className="home-page min-h-screen bg-[#050505] text-[#e2e8f0] relative font-sans overflow-hidden">

      {/* Tri-Layer Hero */}
      <section className="relative w-full h-[90vh] flex items-center max-w-[1400px] mx-auto px-8 overflow-hidden">

        {/* Layer 1: Cinematic Anime Static Asset */}
        <div className="absolute inset-0 z-0">
          <img
            src={`${import.meta.env.BASE_URL}anime_lab_hero.png`}
            alt="Anime Optic Lab"
            className="w-full h-full object-cover opacity-30 saturate-150 mix-blend-screen"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-[#050505]/60 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#050505] via-transparent to-transparent" />
        </div>

        {/* Layer 2: Interactive 2D Viewfinder Overlay */}
        <Viewfinder2D />

        {/* Layer 3: Abstract 3D Glass Prism */}
        <Suspense fallback={null}>
          <Hero3D />
        </Suspense>

        {/* Hero Content */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          className="relative z-30 space-y-6 max-w-2xl mt-20"
        >
          <div className="inline-flex items-center gap-3 px-5 py-2 rounded border border-[#00f0ff]/30 bg-[#00f0ff]/10 text-[#00f0ff] text-xs font-mono tracking-widest uppercase shadow-[0_0_15px_rgba(0,240,255,0.2)]">
            <span className="w-2 h-2 rounded-full bg-[#ff0055] animate-pulse" />
            Optic Lab v2.0
          </div>

          <h1 className="text-6xl md:text-8xl font-bold leading-[0.95] tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-[#ffffff] via-[#e2e8f0] to-[#8c92a0]">
            Focus the <br/>
            unseen.
          </h1>

          <p className="text-[#a0a5b5] text-xl max-w-lg leading-relaxed font-light">
            A high-performance laboratory for anime frame stitching, visual vector search, and sub-pixel structural evaluation.
          </p>

          <div className="flex gap-6 pt-8">
            <a href="#modules" className="px-8 py-4 rounded border border-[#00f0ff] bg-[#00f0ff]/10 hover:bg-[#00f0ff]/20 text-[#00f0ff] font-mono transition-all shadow-[0_0_20px_rgba(0,240,255,0.15)] hover:shadow-[0_0_30px_rgba(0,240,255,0.3)] text-sm tracking-wide">
              Explore Modules
            </a>
            <Link to="/dashboard" className="px-8 py-4 rounded border border-[#333538] hover:border-[#ff0055]/50 bg-black/40 text-[#e2e8f0] hover:text-[#ff0055] transition-all font-mono text-sm tracking-wide group backdrop-blur-sm">
              View Benchmarks <span className="inline-block transition-transform group-hover:translate-x-2">→</span>
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Module Explorer - Prioritized Section */}
      <section id="modules" className="relative z-10 py-32 px-8 max-w-[1400px] mx-auto border-t border-[#1a1c23] bg-gradient-to-b from-[#0a0a0c] to-[#050505]">
        <div className="mb-20 text-center">
          <span className="text-[#00f0ff] text-xs font-mono tracking-[0.2em] font-bold uppercase">TOOLKIT MODULES</span>
          <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight text-[#e2e8f0]">
            The complete visual stack.
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-10">
          {modules.map(({ number, title, text, icon: Icon }, index) => (
            <motion.article
              className={`p-10 border bg-[#0a0a0c] group transition-all hover:shadow-[0_0_30px_rgba(0,240,255,0.05)] relative overflow-hidden cursor-pointer ${activeModule === index ? "border-[#00f0ff]/70" : "border-[#1a1c23] hover:border-[#00f0ff]/50"}`}
              key={title}
              role="button"
              tabIndex={0}
              onClick={() => setActiveModule(index)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setActiveModule(index);
              }}
            >
              {/* Neon accent line */}
              <div className="absolute top-0 left-0 w-0 h-[2px] bg-[#00f0ff] transition-all duration-500 group-hover:w-full" />

              <div className="flex justify-between items-start mb-16">
                <span className="font-mono text-4xl font-bold text-[#1a1c23] group-hover:text-[#ff0055] transition-colors">{number}</span>
                <Icon size={28} className="text-[#4a4d57] group-hover:text-[#00f0ff] transition-colors" />
              </div>
              <h3 className="text-2xl font-bold text-[#e2e8f0] mb-4 tracking-tight">{title}</h3>
              <p className="text-[#8c92a0] leading-relaxed font-light">{text}</p>
            </motion.article>
          ))}
        </div>
        <motion.div
          key={activeModule}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .25 }}
          className="mt-8 border border-[#00f0ff]/20 bg-[#08090c] p-7 md:flex items-center justify-between gap-8"
        >
          <div>
            <span className="text-[#00f0ff] text-[10px] font-mono tracking-[0.2em] uppercase">ACTIVE MODULE / {modules[activeModule].number}</span>
            <p className="max-w-3xl mt-3 text-[#8c92a0] leading-relaxed font-light">{modules[activeModule].detail}</p>
          </div>
          <Link to={modules[activeModule].href} className="mt-5 md:mt-0 shrink-0 text-[#00f0ff] font-mono text-sm hover:text-white transition-colors">
            {modules[activeModule].action} <span aria-hidden="true">→</span>
          </Link>
        </motion.div>
      </section>

      <section id="pipeline" className="relative z-10 py-28 px-8 max-w-[1400px] mx-auto border-t border-[#1a1c23]">
        <div className="grid lg:grid-cols-[.7fr_1.3fr] gap-12 items-center">
          <div>
            <span className="text-[#ffcf4a] text-xs font-mono tracking-[0.2em] font-bold uppercase">PIPELINE OBSERVATORY</span>
            <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight text-[#e2e8f0]">Follow the image<br />through the instrument.</h2>
            <p className="mt-5 max-w-md text-[#8c92a0] leading-relaxed font-light">A compact view of the processing stages. It explains the system without pretending that runtime or proxy metrics replace human visual review.</p>
          </div>
          <div className="border border-[#1a1c23] bg-[#0a0a0c] p-5 shadow-[0_0_30px_rgba(0,240,255,0.04)]">
            <div className="flex justify-between text-[#4a4d57] text-[10px] font-mono tracking-[0.18em] uppercase mb-2">
              <span>STITCH / SYSTEM FLOW</span><span className="text-[#00f0ff]">● ACTIVE</span>
            </div>
            <PipelineDiagram height={240} />
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-[#1a1c23] bg-[#050505]">
        <div className="max-w-[1400px] mx-auto px-8 py-12 flex justify-between items-center text-[#4a4d57] text-[10px] font-mono tracking-[0.2em] uppercase">
          <span>IMAGE-TOOLKIT / VISUAL SYSTEMS LAB</span>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00f0ff]" />
            Systems Online
          </span>
        </div>
      </footer>
    </div>
  );
}
