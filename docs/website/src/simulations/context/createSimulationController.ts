// Framework-neutral play/pause/reset/step wrapper around a frame generator.
// Any framework's island can drive this with setInterval/requestAnimationFrame
// and its own reactivity — the Aurelia island is the only current consumer.
import { generateConvergence, type ConvergenceGeneratorOptions } from "../generator/convergence";
import type { ConvergenceFrame } from "../repository/types";

export interface SimulationController {
  current(): ConvergenceFrame | null;
  step(): ConvergenceFrame | null;
  reset(): void;
  isDone(): boolean;
}

export function createSimulationController(opts: ConvergenceGeneratorOptions): SimulationController {
  let generator = generateConvergence(opts);
  let frame: ConvergenceFrame | null = null;
  let done = false;

  return {
    current: () => frame,
    step() {
      if (done) return frame;
      const result = generator.next();
      if (result.done) {
        done = true;
        return frame;
      }
      frame = result.value;
      if (frame.converged) done = true;
      return frame;
    },
    reset() {
      generator = generateConvergence(opts);
      frame = null;
      done = false;
    },
    isDone: () => done,
  };
}
