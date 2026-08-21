import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  BookOpen,
  Calendar,
  Clock,
  Tag,
  ArrowLeft,
  Share2,
  Sparkles,
  Layers,
  ShieldCheck,
  AlertTriangle,
  Info,
  ChevronRight,
  FlaskConical,
} from "lucide-react";
import DiffLoupe from "../components/journal/DiffLoupe";
import HoldTimelineSlider from "../components/journal/HoldTimelineSlider";
import LayerStack3D from "../components/journal/LayerStack3D";
import "./Journal.css";

interface Article {
  id: string;
  title: string;
  subtitle: string;
  date: string;
  readTime: string;
  category: "Lab Note" | "Case Study" | "Methodology";
  tags: string[];
  excerpt: string;
  authors: { name: string; role: string }[];
  content: React.ReactNode;
}

export default function Journal() {
  const { articleId } = useParams<{ articleId?: string }>();
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const articles: Article[] = [
    {
      id: "lab-note-01-metric-inversion",
      title: "Lab Note 01: Metric Inversion & Failure-Mode Anatomy in Multi-Frame Cel Alignment",
      subtitle: "Why classical CV sharpness anti-correlates with human visual coherence on animated frames, and how seam tearing masquerades as edge fidelity.",
      date: "2026-08-15",
      readTime: "7 min read",
      category: "Lab Note",
      tags: ["#methodology", "#cv-metrics", "#anime-stitch", "#failure-analysis"],
      excerpt:
        "Automated image metrics (SSIM, Sobel gradient sharpness, SIQE ghosting) systematically fail on anime pan sequences. A torn character cel introduces razor-sharp high-frequency seam lines that inflate Sobel filters while producing catastrophic visual distortion. This note breaks down the empirical evidence from our 97-case M0 relabeling audit.",
      authors: [
        { name: "ACFHarbinger", role: "Principal Investigator" },
        { name: "Optic Lab Team", role: "CV & Benchmark Engineering" },
      ],
      content: (
        <div className="article-body">
          <div className="article-callout note">
            <div className="callout-icon">
              <FlaskConical size={18} />
            </div>
            <div>
              <strong>Lab Note Scope &amp; Public Policy (§O1):</strong>
              <p>
                This document is a technical lab note documenting algorithm telemetry and metric validation. In accordance with the ASP Outreach Roadmap (§O1), performance claims are gated behind preregistered complementary splits. Third-party raw frames are excluded in favor of synthetic test fixtures and verified derived telemetry.
              </p>
            </div>
          </div>

          <h2>1. The Paradox of Automated Computer Vision Metrics</h2>
          <p>
            In natural scene stitching (such as landscape or architectural panoramas), edge sharpness and gradient energy are reliable proxies for alignment quality. When two camera poses are correctly registered with sub-pixel homography, high-frequency details (foliage, brickwork, texture) align constructively, maximizing the Sobel sharpness index:
          </p>

          <div className="math-display-block">
            <code>
              {"\\text{Sobel Sharpness}(I) = \\frac{1}{N} \\sum_{x,y} \\sqrt{G_x(x,y)^2 + G_y(x,y)^2}"}
            </code>
          </div>

          <p>
            On 2D hand-drawn and cel-shaded animation, however, this metric undergoes a <strong>pathological inversion</strong>. Anime sequences feature large flat-shaded color regions bounded by discrete ink lines. When classical phase correlation (SCANS) stitches adjacent frames across an animating character, character limbs or eyes get sliced into staggered strips.
          </p>

          <div className="article-callout alert">
            <div className="callout-icon">
              <AlertTriangle size={18} />
            </div>
            <div>
              <strong>The Artificial Sharpness Trap:</strong>
              <p>
                Each sliced seam step introduces artificial 255-unit step edges between mismatched palette colors. The automated Sobel filter detects hundreds of new high-energy edge pixels, reporting a <em>higher sharpness score</em> for a ruined, mangled image than for a seamless, continuous blend!
              </p>
            </div>
          </div>

          <h2>2. Conceptual Failure-Mode Simulation</h2>
          <p>
            Below is an interactive conceptual model comparing ideal foreground cel separation against the primary failure mode of classical phase correlation (seam striping). As documented in §5 below, achieving this ideal in practice remains an open research challenge on our 43 true raw ASP test cases (current human mean coherence: 1.33 / 4.00):
          </p>

          {/* Interactive Widget 1: DiffLoupe */}
          <DiffLoupe
            title="Conceptual Seam & Flow Simulation (Synthesized Pan Model)"
            caption="Drag the divider to observe how unsegmented phase correlation tears moving cels into discrete bands. Click '2.5x Seam Loupe' to inspect artificial step-edge boundaries."
            leftLabel="Target Cel Isolation"
            rightLabel="Classical Seam Slicing"
          />


          <h2>3. Keyframe Hold Deconstruction</h2>
          <p>
            Anime frames rarely pan across a static painting; characters animate on 2s and 3s while the camera scrolls continuously. If the compositing engine does not detect <em>hold blocks</em> (static pose spans), temporal averaging causes severe multi-image ghosting.
          </p>

          {/* Interactive Widget 2: HoldTimelineSlider */}
          <HoldTimelineSlider
            title="Cel-Pose Hold Selection & Ghosting Prevention"
            caption="Scrub through the timeline nodes. Observe how selecting a unified hold block isolates the character cel without multiple ghosted exposure layers."
          />

          <h2>4. 2.5D Layer Stack Synthesis</h2>
          <p>
            The core architecture of Anime Stitch Pipeline separates background plate synthesis from semantic character cel registration:
          </p>

          {/* Interactive Widget 3: LayerStack3D */}
          <LayerStack3D
            title="Exploded 2.5D Layer Decomposition Stack"
            caption="Click and drag to orbit the conceptual 3D scene. The temporal median renders a background candidate while a segmentation mask isolates the foreground cel before seam blending."
          />

          <h2>5. The 97-Case M0 Relabeling Audit</h2>
          <p>
            Our recent M0 relabeling run (<code>relabel.py</code>) across the full 97-test benchmark checkpoint established the authoritative ground truth:
          </p>

          <div className="table-responsive-wrapper my-6">
            <table className="optic-table">
              <thead>
                <tr>
                  <th>Partition Category</th>
                  <th>Case Count</th>
                  <th>Mean Human Score</th>
                  <th>Primary Characteristics</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-medium text-cyan-300">True Raw ASP Composites</td>
                  <td className="font-mono">43</td>
                  <td className="font-mono">1.33 / 4.00</td>
                  <td>Complex dynamic pans, severe non-rigid motion, cel isolation required</td>
                </tr>
                <tr>
                  <td className="font-medium text-emerald-300">Safety Fallbacks to SCANS</td>
                  <td className="font-mono">54</td>
                  <td className="font-mono">2.56 / 4.00</td>
                  <td>Rigid static camera translations, clean background pans without character crossings</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p>
            This 43 / 54 split demonstrates that the legacy benchmark scores were carried by safety fallbacks. Milestones M2 through M5 directly target improving the 43 true neural composite cases to reach our target coherence threshold of &ge; 3.20.
          </p>
        </div>
      ),
    },
    {
      id: "lab-note-02-evidence-backed-dual-veto",
      title: "Lab Note 02: Evidence-Backed Dual-Veto Gates for Public Benchmark Promotion (§C0.5)",
      subtitle: "Designing a one-sided acceptance policy with controlled provenance, minor-presenting hard vetoes, and reproducible anonymized telemetry sidecars.",
      date: "2026-08-15",
      readTime: "5 min read",
      category: "Methodology",
      tags: ["#governance", "#sfw-corpus", "#dual-veto", "#provenance"],
      excerpt:
        "To ensure public documentation and interactive benchmarks remain strictly safe for work (SFW) while maintaining complete scientific integrity, ASP implements a dual-assessor veto policy with machine-readable provenance metadata.",
      authors: [
        { name: "ACFHarbinger", role: "Principal Investigator" },
        { name: "Security & Governance Subsystem", role: "Policy Compliance" },
      ],
      content: (
        <div className="article-body">
          <div className="article-callout note">
            <div className="callout-icon">
              <ShieldCheck size={18} />
            </div>
            <div>
              <strong>Public Safety &amp; Content Architecture:</strong>
              <p>
                Any future public showcase case is eligible only after the §C0.5
                audit records <code>web_redistribution_ok = true</code> and the
                required safety disposition. This note contains no third-party
                showcase frames; the C0.5 SFW audit is still in progress.
              </p>
            </div>
          </div>

          <h2>1. The Dual-Veto Governance Framework</h2>
          <p>
            Under §C0.5 (Issue #41), every candidate has independent human and
            automated assessments. A high-likelihood high-risk finding from
            either assessor is a permanent exclusion; uncertainty is routed to
            an evidence-backed disposition rather than silently treated as a
            confirmed risk.
          </p>

          <ol className="article-ordered-list">
            <li>
              <strong>Automated evidence:</strong> Board metadata, official
              ratings, and optional classifiers may flag high risk. A
              high-likelihood flag is an immediate, non-overridable veto; an
              uncertain result is retained for review rather than treated as a
              verdict.
            </li>
            <li>
              <strong>Human review and adjudication:</strong> Evaluators assign
              content tags and safety tiers (<code>tier_g</code>,
              <code>tier_pg13</code>, <code>tier_mature_sfw</code>). A
              one-sided acceptance, when allowed by the active policy, requires
              an explicit justification and attached provenance (for example,
              PEGI-3 or CERO metadata); it never overrides a high-risk veto.
            </li>
          </ol>

          <h2>2. Machine-Readable Telemetry Sidecars</h2>
          <p>
            Every published evaluation artifact in <code>docs/website/public/data/</code> exposes structured JSON telemetry alongside human-facing charts. This ensures autonomous AI agents and human researchers share an identical, verifiable ground-truth data layer.
          </p>
        </div>
      ),
    },
  ];

  const currentArticle = articleId ? articles.find((a) => a.id === articleId) : null;

  if (currentArticle) {
    return (
      <div className="journal-page article-view-mode">
        <div className="journal-kicker">
          <Link to="/journal" className="kicker-back-link">
            <ArrowLeft size={14} />
            <span>Back to Journal Index</span>
          </Link>
          <span className="kicker-divider">/</span>
          <span className="kicker-category">{currentArticle.category}</span>
        </div>

        <article className="journal-article">
          <header className="article-header">
            <div className="article-meta-top">
              <span className={`article-category-chip ${currentArticle.category.toLowerCase().replace(" ", "-")}`}>
                {currentArticle.category}
              </span>
              <span className="article-date">
                <Calendar size={13} />
                <span>{currentArticle.date}</span>
              </span>
              <span className="article-read-time">
                <Clock size={13} />
                <span>{currentArticle.readTime}</span>
              </span>
            </div>

            <h1 className="article-title">{currentArticle.title}</h1>
            <p className="article-subtitle">{currentArticle.subtitle}</p>

            <div className="article-authors-row">
              {currentArticle.authors.map((auth, idx) => (
                <div key={idx} className="author-card">
                  <div className="author-avatar">{auth.name[0]}</div>
                  <div>
                    <div className="author-name">{auth.name}</div>
                    <div className="author-role">{auth.role}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="article-tags-bar">
              {currentArticle.tags.map((t) => (
                <span key={t} className="article-tag">
                  {t}
                </span>
              ))}
            </div>
          </header>

          <div className="article-content-wrapper">{currentArticle.content}</div>

          <footer className="article-footer">
            <div className="footer-nav-row">
              <Link to="/journal" className="back-btn">
                <ArrowLeft size={15} />
                <span>Return to Journal Index</span>
              </Link>
              <Link to="/dashboard" className="next-btn">
                <span>Explore Live Telemetry Dashboard</span>
                <ChevronRight size={15} />
              </Link>
            </div>
          </footer>
        </article>
      </div>
    );
  }

  const filteredArticles =
    selectedCategory === "all"
      ? articles
      : articles.filter((a) => a.category.toLowerCase() === selectedCategory.toLowerCase());

  return (
    <div className="journal-page">
      <div className="journal-kicker">
        <span className="kicker-pill">
          <BookOpen size={13} />
          <span>Optic Lab Journal</span>
        </span>
        <span className="kicker-divider">/</span>
        <span className="kicker-text">Explorable Explanations &amp; Lab Notes</span>
      </div>

      <header className="journal-hero">
        <div className="journal-hero-title-group">
          <h1>Optic Lab Research Journal</h1>
          <p className="journal-lead">
            Explorable explanations, failure-mode analyses, and empirical research notes on multi-frame computer vision and cel animation stitching.
          </p>
        </div>

        <div className="journal-callout-panel">
          <div className="callout-icon">
            <Sparkles size={20} />
          </div>
          <div className="callout-body">
            <strong>Distill-Style Interactive Explanations:</strong>
            <p>
              Rather than static figures, every article pairs rigorous mathematical reasoning with interactive browser widgets (diff loupes, timeline hold scrubbers, 3D layer stacks) to deconstruct real failure modes.
            </p>
          </div>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="journal-filter-bar">
        <div className="filter-tab-list">
          {["all", "Lab Note", "Methodology", "Case Study"].map((cat) => {
            const key = cat.toLowerCase().replace(" ", "-");
            const isActive = selectedCategory.toLowerCase() === cat.toLowerCase();
            return (
              <button
                key={cat}
                className={`filter-tab-btn ${isActive ? "active" : ""}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat === "all" ? "All Publications" : cat}
              </button>
            );
          })}
        </div>
        <span className="article-count">{filteredArticles.length} publications available</span>
      </div>

      {/* Article Grid */}
      <div className="journal-article-grid">
        {filteredArticles.map((art) => (
          <article key={art.id} className="journal-card">
            <div className="card-top-row">
              <span className={`article-category-chip ${art.category.toLowerCase().replace(" ", "-")}`}>
                {art.category}
              </span>
              <span className="card-date">
                <Calendar size={12} />
                <span>{art.date}</span>
              </span>
            </div>

            <h3 className="card-title">
              <Link to={`/journal/${art.id}`} className="card-title-link">
                {art.title}
              </Link>
            </h3>

            <p className="card-excerpt">{art.excerpt}</p>

            <div className="card-footer">
              <div className="card-tags">
                {art.tags.slice(0, 3).map((t) => (
                  <span key={t} className="mini-tag">
                    {t}
                  </span>
                ))}
              </div>
              <Link to={`/journal/${art.id}`} className="read-more-link">
                <span>Read article</span>
                <ChevronRight size={14} />
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
