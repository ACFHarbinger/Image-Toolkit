import { ExperienceQuality } from "../enums/ExperienceQuality";

export interface HubExperienceConfig {
  /** Aurelia ANN-search convergence sim: points plotted per frame. */
  annSimPointCount: number;
  /** Aurelia ANN-search convergence sim: ms between simulation ticks. */
  annSimTickMs: number;
  /** Astro island (VectorFlowField) particle count. */
  flowFieldParticleCount: number;
  /** Whether hub panels auto-play their simulations on mount. */
  autoplay: boolean;
}

const presets: Record<ExperienceQuality, HubExperienceConfig> = {
  [ExperienceQuality.Minimal]: {
    annSimPointCount: 24,
    annSimTickMs: 240,
    flowFieldParticleCount: 60,
    autoplay: false,
  },
  [ExperienceQuality.Balanced]: {
    annSimPointCount: 64,
    annSimTickMs: 120,
    flowFieldParticleCount: 220,
    autoplay: true,
  },
  [ExperienceQuality.Full]: {
    annSimPointCount: 160,
    annSimTickMs: 60,
    flowFieldParticleCount: 480,
    autoplay: true,
  },
};

export function resolveHubExperience(quality: ExperienceQuality): HubExperienceConfig {
  return presets[quality];
}
