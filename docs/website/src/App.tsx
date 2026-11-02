import { BrowserRouter, Routes, Route, Link, useLocation, useSearchParams } from "react-router-dom";
import { Aperture } from "lucide-react";
import AchievementToast from "./components/AchievementToast";
import Home from "./pages/Home";
import RatingsDashboard from "./pages/RatingsDashboard";
import Docs from "./pages/Docs";
import Pipeline from "./pages/Pipeline";
import Journal from "./pages/Journal";
import { AspDocs, AspHome, AspPipeline } from "./labs/asp";
import { CreDocs, CreHome, CrePipeline } from "./labs/cre";
import { CsgDocs, CsgHome, CsgPipeline } from "./labs/csg";
import { HieDocs, HieHome, HiePipeline } from "./labs/hie";
import "./App.css";

function Nav() {
  const { pathname } = useLocation();
  const [search] = useSearchParams();
  if (search.get("embed") === "1") {
    return null;
  }
  const onDash = pathname.startsWith("/dashboard");
  const onJournal = pathname.startsWith("/journal");
  const onDocs = pathname.startsWith("/docs");
  const onPipeline = pathname.startsWith("/pipeline");
  const onLabs = pathname.startsWith("/labs");

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
          <Link to="/" className={!onDash && !onJournal && !onDocs && !onPipeline && !onLabs ? "active" : undefined}>
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
          <Link to="/labs/asp" className={pathname.startsWith("/labs/asp") ? "active" : undefined}>
            ASP
          </Link>
          <Link to="/labs/cre" className={pathname.startsWith("/labs/cre") ? "active" : undefined}>
            CRE
          </Link>
          <Link to="/labs/csg" className={pathname.startsWith("/labs/csg") ? "active" : undefined}>
            CSG
          </Link>
          <Link to="/labs/hie" className={pathname.startsWith("/labs/hie") ? "active" : undefined}>
            HIE
          </Link>
          <Link to="/docs" className={onDocs ? "active" : undefined}>
            Docs
          </Link>
        </div>

        <Link to="/dashboard" className="nav-cta hud-btn">
          View live signals
        </Link>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="site-shell boot-anim">
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
            <Route path="/labs/asp" element={<AspHome />} />
            <Route path="/labs/asp/pipeline" element={<AspPipeline />} />
            <Route path="/labs/asp/docs" element={<AspDocs />} />
            <Route path="/labs/asp/docs/*" element={<AspDocs />} />
            <Route path="/labs/cre" element={<CreHome />} />
            <Route path="/labs/cre/pipeline" element={<CrePipeline />} />
            <Route path="/labs/cre/docs" element={<CreDocs />} />
            <Route path="/labs/cre/docs/*" element={<CreDocs />} />
            <Route path="/labs/csg" element={<CsgHome />} />
            <Route path="/labs/csg/pipeline" element={<CsgPipeline />} />
            <Route path="/labs/csg/docs" element={<CsgDocs />} />
            <Route path="/labs/csg/docs/*" element={<CsgDocs />} />
            <Route path="/labs/hie" element={<HieHome />} />
            <Route path="/labs/hie/pipeline" element={<HiePipeline />} />
            <Route path="/labs/hie/docs" element={<HieDocs />} />
            <Route path="/labs/hie/docs/*" element={<HieDocs />} />
          </Routes>
        </main>
        <AchievementToast />
      </div>
    </BrowserRouter>
  );
}
