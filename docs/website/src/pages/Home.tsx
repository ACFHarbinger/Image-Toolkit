import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  Camera,
  ChevronRight,
  CircleDot,
  Layers3,
  ScanLine,
  Sparkles,
} from "lucide-react";
import PipelineDiagram from "../components/PipelineDiagram";
import { useRatingsData } from "../hooks/useRatingsData";
import "../App.css";

const modules = [
  {
    number: "01",
    title: "Capture",
    text: "Bring frames, libraries, and media into one observable workspace.",
    icon: Camera,
    color: "cyan",
  },
  {
    number: "02",
    title: "Understand",
    text: "Measure alignment, similarity, motion, and structure—not just pixels.",
    icon: ScanLine,
    color: "violet",
  },
  {
    number: "03",
    title: "Compose",
    text: "Turn experiments into inspectable outputs with provenance attached.",
    icon: Layers3,
    color: "amber",
  },
];

const techChips = [
  "Python",
  "C++",
  "ASP stitch",
  "SCANS baseline",
  "Human coherence",
  "pgvector",
];

function SignalField() {
  const nodes = [
    [10, 32],
    [19, 66],
    [31, 22],
    [43, 51],
    [56, 30],
    [67, 70],
    [78, 39],
    [91, 60],
  ];
  const links = [
    [0, 1],
    [0, 2],
    [1, 3],
    [2, 3],
    [2, 4],
    [3, 5],
    [4, 6],
    [5, 7],
    [6, 7],
  ];
  return (
    <svg
      className="signal-field"
      viewBox="0 0 100 92"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="signal-line" x1="0" x2="1">
          <stop offset="0" stopColor="#62e7e0" stopOpacity=".1" />
          <stop offset=".55" stopColor="#a78bfa" stopOpacity=".7" />
          <stop offset="1" stopColor="#f2b66d" stopOpacity=".1" />
        </linearGradient>
        <filter id="signal-glow">
          <feGaussianBlur stdDeviation=".8" />
        </filter>
      </defs>
      {links.map(([a, b]) => (
        <line
          key={`${a}-${b}`}
          x1={nodes[a][0]}
          y1={nodes[a][1]}
          x2={nodes[b][0]}
          y2={nodes[b][1]}
          stroke="url(#signal-line)"
          strokeWidth=".25"
        />
      ))}
      {nodes.map(([x, y], i) => (
        <g key={`${x}-${y}`}>
          <circle
            cx={x}
            cy={y}
            r={i % 3 === 0 ? 2.2 : 1.2}
            fill={i % 3 === 0 ? "#62e7e0" : "#a78bfa"}
            opacity=".25"
            filter="url(#signal-glow)"
          />
          <circle
            cx={x}
            cy={y}
            r={i % 3 === 0 ? 0.8 : 0.45}
            fill={i % 3 === 0 ? "#bafcf2" : "#d9ccff"}
          />
        </g>
      ))}
    </svg>
  );
}

export default function Home() {
  const { humanRatings, benchmarkResults, meta } = useRatingsData();
  const reviewed = humanRatings?.summary.reviewed ?? 0;
  const total = humanRatings?.summary.total_keys ?? 0;
  const meanAsp = humanRatings?.summary.mean_asp;
  const meanSimple = humanRatings?.summary.mean_simple;
  const hint = humanRatings?.summary.narrative_hint ?? meta?.notes?.[0];

  return (
    <div className="home-page">
      {/* Cinematic radial stage (PMF/VGP atmosphere) */}
      <div className="atmosphere" aria-hidden="true">
        <div className="orb orb-teal" />
        <div className="orb orb-violet" />
        <div className="orb orb-amber" />
      </div>

      <section className="hero-lab">
        <SignalField />
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="eyebrow-pulse" /> IMAGE PIPELINE · DEV CONSOLE
          </div>
          <h1>
            Stitch the scene,
            <br />
            <em>not just the pixels.</em>
          </h1>
          <p className="hero-lede">
            A local laboratory for panorama stitching, visual search, and
            measurable image quality—from anime frames to full archives. Human
            judgment stays first-class; automated metrics stay honest.
          </p>

          <div className="hero-chips" aria-label="Stack and signals">
            {techChips.map((chip) => (
              <span key={chip} className="hero-chip">
                {chip}
              </span>
            ))}
          </div>

          <div className="hero-actions">
            <Link className="button button-primary" to="/dashboard">
              Open quality dashboard <ChevronRight size={17} />
            </Link>
            <a className="button button-quiet" href="#pipeline">
              Explore the pipeline <Sparkles size={15} />
            </a>
            <a
              className="button button-ghost"
              href="https://github.com/ACFHarbinger/Image-Toolkit"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub <ArrowUpRight size={15} />
            </a>
          </div>

          <div className="hero-note">
            <CircleDot size={13} />
            {hint
              ? hint
              : "Human review is active · quality signals shown without smoothing"}
          </div>
        </div>

        <motion.div
          className="hero-art-wrap"
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.15 }}
        >
          <div className="hero-art-frame">
            <img
              src={`${import.meta.env.BASE_URL}hero.jpg`}
              alt="Abstract visual processing workspace — frames becoming one coherent image"
            />
            <div className="hero-art-overlay">
              <PipelineDiagram height={120} />
            </div>
          </div>
          <div className="floating-readout readout-top">
            <span>LIVE SIGNAL</span>
            <strong>panorama lab</strong>
            <i />
          </div>
          <div className="floating-readout readout-bottom">
            <span>RATING COVERAGE</span>
            <strong>{reviewed ? `${reviewed} / ${total}` : "in progress"}</strong>
            <small>human evaluations</small>
          </div>
        </motion.div>
      </section>

      <section className="metric-rail" aria-label="Current project signals">
        <div>
          <span className="rail-label">HUMAN RATING PASS</span>
          <strong>{reviewed ? `${reviewed} cases` : "in progress"}</strong>
          <small>live benchmark evidence</small>
        </div>
        <div>
          <span className="rail-label">ASP COHERENCE</span>
          <strong>{meanAsp == null ? "—" : `${meanAsp.toFixed(2)} / 4`}</strong>
          <small>human structural score</small>
        </div>
        <div>
          <span className="rail-label">SCANS BASELINE</span>
          <strong>
            {meanSimple == null ? "—" : `${meanSimple.toFixed(2)} / 4`}
          </strong>
          <small>OpenCV simple stitch</small>
        </div>
        <div>
          <span className="rail-label">AUTOMATED RUNS</span>
          <strong>{benchmarkResults?.run_count ?? "—"}</strong>
          <small>kept separate from ratings</small>
        </div>
      </section>

      <section className="manifesto-section" id="modules">
        <div className="section-kicker">THE WORKBENCH</div>
        <div className="section-heading">
          <h2>
            From raw frames
            <br />
            <em>to honest evidence.</em>
          </h2>
          <p>
            Capture, understand, compose—each step leaves a trace you can
            inspect. Built for the moments where visual systems must be
            understood, not just run.
          </p>
        </div>
        <div className="module-grid">
          {modules.map(({ number, title, text, icon: Icon, color }) => (
            <motion.article
              className={`module-card module-${color}`}
              key={title}
              whileHover={{ y: -5 }}
              transition={{ duration: 0.2 }}
            >
              <div className="module-top">
                <span>{number}</span>
                <Icon size={20} />
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
              <span className="module-rule" />
            </motion.article>
          ))}
        </div>
      </section>

      <section className="pipeline-section" id="pipeline">
        <div className="pipeline-intro">
          <div className="section-kicker">THE PIPELINE</div>
          <h2>
            A living diagram
            <br />
            <em>of the stitch.</em>
          </h2>
          <p>
            BiRefNet → matching → bundle adjust → ECC → render → composite.
            Follow the stages, then compare ASP against the SCANS baseline with
            human coherence scores—not sharpness alone.
          </p>
          <Link className="text-link" to="/dashboard">
            Inspect benchmark signals <ArrowUpRight size={15} />
          </Link>
        </div>
        <div className="pipeline-card">
          <div className="pipeline-card-head">
            <span>
              <Sparkles size={14} /> SYSTEM FLOW
            </span>
            <span className="status-dot">● active</span>
          </div>
          <PipelineDiagram height={230} />
        </div>
      </section>

      <section className="closing-section" id="docs">
        <div className="closing-icon">
          <BookOpen size={22} />
        </div>
        <div>
          <div className="section-kicker">DOCUMENTATION / RESEARCH / ROADMAPS</div>
          <h2>
            Good tools leave
            <br />
            <em>a map behind.</em>
          </h2>
          <p>
            Architecture, tutorials, ASP research, and the decisions that shape
            Image-Toolkit—kept next to the signals that prove them.
          </p>
        </div>
        <a className="button button-primary" href={`${import.meta.env.BASE_URL}../`}>
          Browse documentation <ArrowUpRight size={16} />
        </a>
      </section>

      <footer className="home-footer">
        <span>IMAGE-TOOLKIT / VISUAL SYSTEMS LAB</span>
        <span>Built for inspection, not illusion.</span>
      </footer>
    </div>
  );
}
