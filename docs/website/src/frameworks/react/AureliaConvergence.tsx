import { useEffect, useRef, useState } from "react";
import "./framework-islands.css";

export default function AureliaConvergence() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    let stop: (() => Promise<void>) | undefined;

    void import("../aurelia/mount")
      .then(({ mountAnnConvergence }) => {
        if (!active || !hostRef.current) return;
        const handle = mountAnnConvergence(hostRef.current);
        stop = () => handle.stop();
      })
      .catch(() => {
        if (active) setError(true);
      });

    return () => {
      active = false;
      if (stop) void stop();
    };
  }, []);

  if (error) {
    return <p className="framework-island-error" role="alert">The Aurelia visualization could not be loaded.</p>;
  }

  return <div ref={hostRef} className="aurelia-host framework-island" />;
}
