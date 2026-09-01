// Mounts the Aurelia 2 island into a plain DOM node — the same pattern any
// non-primary framework uses, just with Aurelia's own Aurelia.app().start().
import { Aurelia } from "aurelia";
import { AnnConvergenceApp } from "./ann-convergence-app";
import { logIslandMount, logIslandUnmount } from "../shared/utils";

export interface AureliaMountHandle {
  stop(): Promise<void>;
}

export function mountAnnConvergence(host: HTMLElement): AureliaMountHandle {
  const au = new Aurelia();
  au.app({ host, component: AnnConvergenceApp });
  void au.start();
  logIslandMount("Aurelia", "ann-convergence");

  return {
    async stop() {
      await au.stop(true);
      logIslandUnmount("Aurelia", "ann-convergence");
    },
  };
}
