import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Aperture } from "lucide-react";
import Home from "./pages/Home";
import RatingsDashboard from "./pages/RatingsDashboard";
import "./App.css";

function Nav() {
  const { pathname } = useLocation();
  const onDash = pathname.startsWith("/dashboard");

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
          <Link to="/" className={!onDash ? "active" : undefined}>
            Home
          </Link>
          <Link to="/dashboard" className={onDash ? "active" : undefined}>
            Quality
          </Link>
          <a href="#pipeline">Pipeline</a>
          <a href="#docs">Docs</a>
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
            <Route path="/dashboard" element={<RatingsDashboard />} />
            <Route path="/dashboard/ratings" element={<RatingsDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
