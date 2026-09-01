// Aurelia 2 custom element — no separate .html template file (this package
// has no aurelia-loader/vite-plugin-aurelia wired up), so the template is
// defined inline via CustomElement.define, same mechanism Aurelia's own
// `au.app()` bootstrapping resolves for the root component either way.
import { customElement, bindable } from "aurelia";
import { createSimulationController, type SimulationController } from "../../simulations/context/createSimulationController";
import { scenarios, defaultScenario } from "../../simulations/scenarios/scenarios";
import type { ConvergenceFrame } from "../../simulations/repository/types";

const CLUSTER_COLORS = ["#7c3aed", "#22d3ee", "#f59e0b", "#ef4444", "#10b981", "#ec4899", "#3b82f6", "#a855f7"];

const template = `
<div class="ann-root">
  <header>
    <p class="kicker">Framework island · Aurelia 2</p>
    <h2>k-means convergence (illustrative pgvector index-build analogy)</h2>
    <p class="subtitle">\${scenario.description}</p>
  </header>

  <div class="controls">
    <select change.trigger="onScenarioChange($event.target)">
      <option repeat.for="s of scenarioList" model.bind="s.id" selected.bind="s.id === scenario.id">\${s.title}</option>
    </select>
    <button type="button" click.trigger="togglePlay()">\${playing ? 'Pause' : 'Play'}</button>
    <button type="button" click.trigger="reset()">Reset</button>
    <span class="step-label">step \${frame ? frame.step : 0}\${frame && frame.converged ? ' · converged' : ''}</span>
  </div>

  <svg viewBox="0 0 100 100" role="img" aria-label="k-means convergence visualization">
    <circle repeat.for="a of assignments" cx.bind="a.point.x" cy.bind="a.point.y" r="1.1" fill.bind="colorFor(a.centroidId)" opacity="0.55"></circle>
    <g repeat.for="c of centroidList">
      <circle cx.bind="c.x" cy.bind="c.y" r="2.6" fill.bind="colorFor(c.id)" stroke="white" stroke-width="0.5"></circle>
    </g>
  </svg>
</div>
`;

@customElement({ name: "ann-convergence", template })
export class AnnConvergenceApp {
  @bindable autoplay = true;

  scenarioList = scenarios;
  scenario = defaultScenario;
  controller: SimulationController = createSimulationController(this.scenario);
  frame: ConvergenceFrame | null = null;
  playing = false;
  private timer: ReturnType<typeof setInterval> | null = null;

  get assignments() {
    return this.frame?.assignments ?? [];
  }
  get centroidList() {
    return this.frame?.centroids ?? [];
  }

  colorFor(centroidId: number): string {
    return CLUSTER_COLORS[centroidId % CLUSTER_COLORS.length];
  }

  binding() {
    this.frame = this.controller.step();
    if (this.autoplay) this.play();
  }

  play() {
    if (this.timer) return;
    this.playing = true;
    this.timer = setInterval(() => {
      if (this.controller.isDone()) {
        this.pause();
        return;
      }
      this.frame = this.controller.step();
    }, 220);
  }

  pause() {
    this.playing = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  togglePlay() {
    if (this.playing) this.pause();
    else this.play();
  }

  reset() {
    this.pause();
    this.controller.reset();
    this.frame = this.controller.step();
    this.play();
  }

  onScenarioChange(target: HTMLSelectElement) {
    const next = this.scenarioList.find((s) => s.id === target?.value);
    if (!next) return;
    this.scenario = next;
    this.controller = createSimulationController(next);
    this.reset();
  }

  unbinding() {
    this.pause();
  }
}
