// Framework-neutral — no UI-runtime imports. Consumed by the Aurelia
// ANN-convergence island (src/frameworks/aurelia/) via createSimulationController.
export interface Point2D {
  x: number;
  y: number;
}

export interface Centroid extends Point2D {
  id: number;
}

export interface ClusterAssignment {
  point: Point2D;
  centroidId: number;
}

export interface ConvergenceFrame {
  step: number;
  centroids: Centroid[];
  assignments: ClusterAssignment[];
  /** Sum of squared distances from each point to its assigned centroid — decreases (or plateaus) as it converges. */
  inertia: number;
  converged: boolean;
}

export interface ConvergenceScenario {
  id: string;
  title: string;
  description: string;
  seed: number;
  pointCount: number;
  clusterCount: number;
  maxSteps: number;
}
