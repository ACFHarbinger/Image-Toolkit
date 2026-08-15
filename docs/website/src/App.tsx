import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Aperture } from "lucide-react";
import Home from "./pages/Home";
import RatingsDashboard from "./pages/RatingsDashboard";
import Docs from "./pages/Docs";
import Pipeline from "./pages/Pipeline";
import Journal from "./pages/Journal";
import "./App.css";

function Nav() {
  const { pathname } = useLocation();
  const onDash = pathname.startsWith("/dashboard");
  const onJournal = pathname.startsWith("/journal");
  const onDocs = pathname.startsWith("/docs");
  const onPipeline = pathname.startsWith("/pipeline");

  return (
    <nav className="site-nav" aria-label="Primary">
      <div className="site-nav-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <Aperture size={18} strokeWidth={2.2} />
          </span>
          <span className="brand-text">
            <strong>Image-Toolkit</strong>
            <em>visual systems lab</em>
          </span>
        </Link>

        <div className="nav-links">
          <Link to="/" className={!onDash && !onJournal && !onDocs && !onPipeline ? "active" : undefined}>
            Home
          </Link>
          <Link to="/journal" className={onJournal ? "active" : undefined}>
            Journal
          </Link>
          <Link to="/dashboard" className={onDash ? "active" : undefined}>
            Quality
          </Link>
          <Link to="/pipeline" className={onPipeline ? "active" : undefined}>
            Pipeline
          </Link>
          <Link to="/docs" className={onDocs ? "active" : undefined}>
            Docs
          </Link>
        </div>

        <Link to="/dashboard" className="nav-cta">
          View live signals
        </Link>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="site-shell">
        <Nav />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/journal/:articleId" element={<Journal />} />
            <Route path="/dashboard" element={<RatingsDashboard />} />
            <Route path="/dashboard/ratings" element={<RatingsDashboard />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/docs/:fileId" element={<Docs />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

