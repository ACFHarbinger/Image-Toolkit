import { useEffect, useRef, useState } from "react";
import { logIslandMount, logIslandUnmount } from "../shared/utils";
import "./framework-islands.css";

type AstroVectorFlowFieldProps = {
  height?: string;
  title?: string;
};

export default function AstroVectorFlowField({
  height = "420px",
  title = "Astro vector flow field island",
}: AstroVectorFlowFieldProps) {
  const containerRef = useRef<HTMLElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [visible, setVisible] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || !("IntersectionObserver" in window)) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true);
        observer.disconnect();
      }
    }, { threshold: 0.2 });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const postTheme = () => frameRef.current?.contentWindow?.postMessage({
      type: "image-toolkit-theme",
      theme: media.matches ? "dark" : "light",
    }, "*");
    media.addEventListener("change", postTheme);
    return () => media.removeEventListener("change", postTheme);
  }, []);

  useEffect(() => () => {
    if (loaded) logIslandUnmount("Astro", "vector-flow-field");
  }, [loaded]);

  const onLoad = () => {
    setLoaded(true);
    frameRef.current?.contentWindow?.postMessage({
      type: "image-toolkit-theme",
      theme: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    }, "*");
    logIslandMount("Astro", "vector-flow-field");
  };

  return (
    <section ref={containerRef} className="astro-island-wrap framework-island">
      <div className="frame-shell" style={{ minHeight: height }}>
        {failed ? (
          <p className="framework-island-error" role="alert">The Astro visualization could not be loaded.</p>
        ) : visible ? (
          <iframe
            ref={frameRef}
            className="island-frame"
            src={`${import.meta.env.BASE_URL}astro-island/index.html`}
            title={title}
            style={{ height }}
            loading="lazy"
            referrerPolicy="no-referrer"
            onLoad={onLoad}
            onError={() => setFailed(true)}
          />
        ) : null}
        {!loaded && !failed && <p className="framework-island-loading">Loading Astro visualization…</p>}
      </div>
    </section>
  );
}
