import { lazy, Suspense, useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { BookOpen, ExternalLink } from "lucide-react";
import MarkdownIt from "markdown-it";
import mermaid from "mermaid";
import Viewfinder2D from "./components/Viewfinder2D";
import PipelineDiagram from "./components/PipelineDiagram";

const Hero3D = lazy(() => import("./components/Hero3D"));

mermaid.initialize({ startOnLoad: false, theme: "dark" });

const markdown = new MarkdownIt({ html: true, linkify: true, typographer: true });

export interface LabModule {
  number: string;
  title: string;
  text: string;
  detail: string;
  action: string;
  href: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}

export interface LabDocument {
  id: string;
  title: string;
  body: string;
  kind: "md" | "text";
}

export interface LabSite {
  slug: string;
  shortName: string;
  name: string;
  eyebrow: string;
  badge: string;
  heroTitle: [string, string];
  heroDescription: string;
  accent: "cyan" | "rose" | "violet";
  repository: string;
  originalRepository: string;
  modules: LabModule[];
  stages: string[];
  documents: LabDocument[];
}

const ACCENTS = {
  cyan: {
    text: "text-[#00f0ff]",
    border: "border-[#00f0ff]",
    bg: "bg-[#00f0ff]/10",
    glow: "shadow-[0_0_30px_rgba(0,240,255,0.15)]",
    hover: "hover:border-[#00f0ff]/50",
  },
  rose: {
    text: "text-[#ff5c93]",
    border: "border-[#ff0055]",
    bg: "bg-[#ff0055]/10",
    glow: "shadow-[0_0_30px_rgba(255,0,85,0.15)]",
    hover: "hover:border-[#ff0055]/50",
  },
  violet: {
    text: "text-[#b895ff]",
    border: "border-[#9b6cff]",
    bg: "bg-[#9b6cff]/10",
    glow: "shadow-[0_0_30px_rgba(155,108,255,0.15)]",
    hover: "hover:border-[#9b6cff]/50",
  },
} as const;

/** Turn a Vite raw glob, keyed from a lab page, into sidebar documents. */
export function documentsFromGlob(files: Record<string, string>): LabDocument[] {
  const marker = "../../../../";
  return Object.entries(files)
    .filter(([path]) => !path.includes("/website/"))
    .map(([path, body]) => {
      const at = path.indexOf(marker);
      const id = at >= 0 ? path.slice(at + marker.length) : path.split("/").pop() || path;
      const heading = /^#\s+(.+)$/m.exec(body)?.[1]?.trim();
      const kind = id.endsWith(".md") ? "md" : "text";
      return { id, title: heading || id, body, kind } satisfies LabDocument;
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

function docHref(site: LabSite, id: string): string {
  return `/labs/${site.slug}/docs/${id}`;
}

function LabChrome({ site, children }: { site: LabSite; children: ReactNode }) {
  const { pathname } = useLocation();
  const base = `/labs/${site.slug}`;
  const accent = ACCENTS[site.accent];
  const links = [
    { href: base, label: "Home", on: pathname === base },
    { href: `${base}/pipeline`, label: "Pipeline", on: pathname.startsWith(`${base}/pipeline`) },
    { href: `${base}/docs`, label: "Docs", on: pathname.startsWith(`${base}/docs`) },
  ];
  return (
    <div className="lab-page bg-[#050505] text-[#e2e8f0] min-h-screen">
      <div className="sticky top-[4.5rem] z-40 border-b border-[#1a1c23] bg-[#050505]/90 backdrop-blur">
        <div className="max-w-[1400px] mx-auto px-8 py-3 flex flex-wrap items-center gap-4">
          <span className={`${accent.text} font-mono text-xs tracking-[0.18em]`}>{site.shortName}</span>
          {links.map((link) => (
            <Link key={link.href} to={link.href} className={link.on ? `${accent.text} font-mono text-sm` : "text-[#8c92a0] font-mono text-sm"}>
              {link.label}
            </Link>
          ))}
          <a className="ml-auto text-[#8c92a0] font-mono text-xs" href={site.originalRepository} target="_blank" rel="noreferrer">
            Original repository <ExternalLink className="inline" size={12} />
          </a>
        </div>
      </div>
      {children}
    </div>
  );
}

export function LabHome({ site }: { site: LabSite }) {
  const [active, setActive] = useState(0);
  const accent = ACCENTS[site.accent];
  const current = site.modules[active];
  return (
    <LabChrome site={site}>
      <div className="home-page overflow-hidden">
        <section className="relative min-h-[90vh] max-w-[1400px] mx-auto px-8 flex items-center overflow-hidden">
          <div className="absolute inset-0">
            <img src={`${import.meta.env.BASE_URL}anime_lab_hero.png`} alt="" className="w-full h-full object-cover opacity-25 saturate-150 mix-blend-screen" />
            <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-[#050505]/65 to-transparent" />
          </div>
          <Viewfinder2D />
          <Suspense fallback={null}><Hero3D /></Suspense>
          <motion.div initial={{ opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 1.1 }} className="relative z-30 space-y-6 max-w-2xl mt-20">
            <div className={`inline-flex items-center gap-3 px-5 py-2 rounded border ${accent.border}/30 ${accent.bg} ${accent.text} text-xs font-mono tracking-widest uppercase`}>
              <span className="w-2 h-2 rounded-full bg-[#00f0ff] animate-pulse" />
              {site.badge}
            </div>
            <h1 className="text-6xl md:text-8xl font-bold leading-[0.95] tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-white via-[#e2e8f0] to-[#8c92a0]">
              {site.heroTitle[0]}<br /><span>{site.heroTitle[1]}</span>
            </h1>
            <p className="text-[#a0a5b5] text-xl max-w-lg leading-relaxed font-light">{site.heroDescription}</p>
            <div className="flex flex-wrap gap-4 pt-8">
              <a href="#modules" className={`px-7 py-4 rounded border ${accent.border} ${accent.bg} ${accent.text} font-mono ${accent.glow}`}>Explore the system</a>
              <a href={site.repository} target="_blank" rel="noreferrer" className="px-7 py-4 rounded border border-[#333538] bg-black/40 text-[#e2e8f0] font-mono">View repository <ExternalLink className="inline ml-2" size={14} /></a>
            </div>
          </motion.div>
        </section>
        <section id="modules" className="relative z-10 py-28 px-8 max-w-[1400px] mx-auto border-t border-[#1a1c23] bg-gradient-to-b from-[#0a0a0c] to-[#050505]">
          <div className="mb-16 text-center">
            <span className={`${accent.text} text-xs font-mono tracking-[0.2em] font-bold uppercase`}>{site.shortName} / SYSTEM MODULES</span>
            <h2 className="text-4xl md:text-5xl font-bold mt-4">A focused instrument.</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {site.modules.map((item, index) => {
              const Icon = item.icon;
              const selected = active === index;
              return (
                <motion.article key={item.title} whileHover={{ y: -5 }} onClick={() => setActive(index)} className={`p-9 border bg-[#0a0a0c] group cursor-pointer ${selected ? `${accent.border}/70 ${accent.glow}` : "border-[#1a1c23]"}`}>
                  <div className="flex justify-between items-start mb-14">
                    <span className="font-mono text-4xl font-bold text-[#1a1c23]">{item.number}</span>
                    <Icon size={28} className={`${accent.text} opacity-70`} />
                  </div>
                  <h3 className="text-2xl font-bold mb-4">{item.title}</h3>
                  <p className="text-[#8c92a0] leading-relaxed">{item.text}</p>
                </motion.article>
              );
            })}
          </div>
          {current ? (
            <motion.div key={active} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mt-8 border ${accent.border}/20 bg-[#08090c] p-7`}>
              <span className={`${accent.text} text-[10px] font-mono tracking-[0.2em]`}>ACTIVE MODULE / {current.number}</span>
              <p className="mt-3 text-[#8c92a0]">{current.detail}</p>
              <Link to={current.href} className={`inline-block mt-4 ${accent.text} font-mono text-sm`}>{current.action} →</Link>
            </motion.div>
          ) : null}
        </section>
        <section className="relative z-10 py-28 px-8 max-w-[1400px] mx-auto border-t border-[#1a1c23]">
          <div className="grid lg:grid-cols-[.7fr_1.3fr] gap-12 items-center">
            <div>
              <span className="text-[#ffcf4a] text-xs font-mono tracking-[0.2em] font-bold uppercase">{site.shortName} / PIPELINE OBSERVATORY</span>
              <h2 className="text-4xl md:text-5xl font-bold mt-4">Follow the signal<br />through the system.</h2>
              <p className="mt-5 text-[#8c92a0] leading-relaxed">Every boundary is measurable, reviewable, and documented.</p>
            </div>
            <div className={`border border-[#1a1c23] bg-[#0a0a0c] p-5 ${accent.glow}`}><PipelineDiagram height={240} /></div>
          </div>
          <div className="mt-8 flex flex-wrap justify-center gap-3 text-[10px] font-mono text-[#8c92a0]">
            {site.stages.map((stage) => <span key={stage} className={`border border-[#1a1c23] px-3 py-2 ${accent.text}`}>{stage}</span>)}
          </div>
        </section>
        <section className="relative z-10 py-20 px-8 max-w-[1400px] mx-auto border-t border-[#1a1c23]">
          <span className={`${accent.text} text-xs font-mono tracking-[0.2em] font-bold uppercase`}>DOCUMENTATION / {site.shortName}</span>
          <h2 className="text-4xl font-bold mt-4">Read the engineering trail.</h2>
          <Link to={`/labs/${site.slug}/docs`} className={`inline-block mt-7 ${accent.text} font-mono text-sm`}>Open the {site.shortName} documents →</Link>
        </section>
        <footer className="border-t border-[#1a1c23] px-8 py-12 flex flex-wrap gap-4 justify-between text-[#4a4d57] text-[10px] font-mono">
          <span>{site.name.toUpperCase()} / IMAGE-TOOLKIT</span>
          <Link className={accent.text} to="/">Return to Image-Toolkit</Link>
        </footer>
      </div>
    </LabChrome>
  );
}

export function LabPipeline({ site }: { site: LabSite }) {
  const accent = ACCENTS[site.accent];
  return (
    <LabChrome site={site}>
      <div className="max-w-[1400px] mx-auto px-8 pt-12 pb-24 min-h-screen">
        <span className="text-[#ffcf4a] text-xs font-mono tracking-[0.2em] font-bold uppercase">{site.shortName} / PIPELINE OBSERVATORY</span>
        <h1 className="text-4xl md:text-6xl font-bold mt-4 tracking-tight text-[#e2e8f0]">A measurable path from input<br />to finished work.</h1>
        <p className="mt-5 max-w-2xl text-lg text-[#8c92a0] leading-relaxed">{site.heroDescription} The stages below make the hand-offs visible so experiments, failures, and improvements remain reviewable.</p>
        <div className={`mt-14 border border-[#1a1c23] bg-[#0a0a0c] p-6 md:p-10 ${accent.glow}`}>
          <div className="flex justify-between text-[#4a4d57] text-[10px] font-mono tracking-[0.18em] uppercase mb-4">
            <span>{site.name} / SYSTEM FLOW</span>
            <span className="text-[#00f0ff]">● ACTIVE</span>
          </div>
          <PipelineDiagram height={300} />
        </div>
        <div className="grid md:grid-cols-3 gap-5 mt-8">
          {site.stages.map((stage, index) => (
            <motion.article key={stage} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * 0.06 }} className="border border-[#1a1c23] bg-[#0a0a0c] p-6">
              <span className={`${accent.text} text-[10px] font-mono`}>0{index + 1}</span>
              <h2 className="mt-5 text-xl font-bold text-[#e2e8f0]">{stage}</h2>
              <p className="mt-3 text-sm leading-relaxed text-[#8c92a0]">A documented boundary in the {site.shortName} processing graph.</p>
            </motion.article>
          ))}
        </div>
        <a href={site.repository} target="_blank" rel="noreferrer" className={`inline-block mt-10 ${accent.text} font-mono text-sm`}>Inspect implementation on GitHub ↗</a>
      </div>
    </LabChrome>
  );
}

export function LabDocs({ site }: { site: LabSite }) {
  const params = useParams();
  const splat = params["*"] ?? "";
  const accent = ACCENTS[site.accent];
  const active = site.documents.find((doc) => doc.id === splat) ?? null;
  const featured = ["ARCHITECTURE.md", "BENCHMARKS.md", "DEVELOPMENT.md", "TESTING.md"]
    .map((id) => site.documents.find((doc) => doc.id === id))
    .filter((doc): doc is LabDocument => Boolean(doc));
  const html = useMemo(() => (active && active.kind === "md" ? markdown.render(active.body) : ""), [active]);

  useEffect(() => {
    if (!html) return;
    const els = document.querySelectorAll(".lab-prose pre code.language-mermaid");
    els.forEach((el, index) => {
      const parent = el.parentElement;
      if (!parent) return;
      const div = document.createElement("div");
      div.className = "mermaid my-8";
      div.id = `lab-mermaid-${index}`;
      div.textContent = el.textContent;
      parent.replaceWith(div);
    });
    mermaid.run({ querySelector: ".lab-prose .mermaid" }).catch(() => undefined);
  }, [html]);

  return (
    <LabChrome site={site}>
      <div className="max-w-[1400px] mx-auto px-8 pt-12 pb-24 min-h-screen grid md:grid-cols-[260px_1fr] gap-8">
        <aside className="border border-[#1a1c23] bg-[#0a0a0c] p-4 h-fit sticky top-36 max-h-[70vh] overflow-auto">
          <h2 className={`${accent.text} font-mono text-xs tracking-[0.16em] mb-4`}>DOCUMENTS</h2>
          <nav className="space-y-1">
            {site.documents.map((doc) => (
              <Link key={doc.id} to={docHref(site, doc.id)} className={`block px-2 py-1 text-sm ${doc.id === active?.id ? accent.text : "text-[#8c92a0]"}`}>
                {doc.title}
              </Link>
            ))}
          </nav>
        </aside>
        <article>
          {!active ? (
            <>
              <span className={`${accent.text} text-xs font-mono tracking-[0.2em] font-bold uppercase`}>DOCUMENTATION / {site.shortName}</span>
              <h1 className="text-4xl md:text-6xl font-bold mt-4 text-[#e2e8f0]">The engineering trail.</h1>
              <p className="mt-5 max-w-2xl text-lg text-[#8c92a0] leading-relaxed">Architecture decisions, experiments, benchmarks, and development guidance for {site.name} are part of the Image-Toolkit docs.</p>
              <div className="grid md:grid-cols-2 gap-5 mt-12">
                {featured.map((doc, index) => (
                  <Link key={doc.id} to={docHref(site, doc.id)} className={`group border border-[#1a1c23] bg-[#0a0a0c] p-7 ${accent.hover} transition-colors`}>
                    <BookOpen className={`${accent.text} mb-8`} size={24} />
                    <h2 className="text-xl font-bold text-[#e2e8f0]">{doc.title}</h2>
                    <p className="mt-3 text-sm text-[#8c92a0]">{doc.id}</p>
                    <span className={`inline-block mt-6 ${accent.text} text-xs font-mono`}>SECTION 0{index + 1}</span>
                  </Link>
                ))}
              </div>
            </>
          ) : active.kind === "text" ? (
            <>
              <h1 className="text-3xl font-bold text-[#e2e8f0]">{active.title}</h1>
              <pre className="mt-6 whitespace-pre-wrap text-sm text-[#c5cad3]">{active.body}</pre>
            </>
          ) : (
            <div className="lab-prose max-w-3xl" dangerouslySetInnerHTML={{ __html: html }} />
          )}
        </article>
      </div>
    </LabChrome>
  );
}
