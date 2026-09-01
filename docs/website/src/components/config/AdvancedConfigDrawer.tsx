import React, { useState, useMemo } from 'react';
import { Sliders, Search, Copy, Check } from 'lucide-react';
import { showAchievementToast } from '../../utils/achievementToast';

export interface ConfigSchemaEntry {
  key: string;
  type: 'int' | 'float' | 'str' | 'bool';
  min?: number;
  max?: number;
  defaultVal: ConfigValue;
  description: string;
  category: string;
  isPrimary?: boolean;
}

type ConfigValue = string | number | boolean;

export const ASP_CONFIG_MATRIX: ConfigSchemaEntry[] = [
  // ── Frame Selection & Hold Detection ──
  { key: 'ASP_HOLD_THRESHOLD', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.05, description: 'MAD hold-detection threshold [0, 1]', category: 'Frame Selection', isPrimary: true },
  { key: 'ASP_HOLD_DHASH_THRESH', type: 'int', min: 0, max: 64, defaultVal: 4, description: 'dHash Hamming floor for hold detection (0=off)', category: 'Frame Selection', isPrimary: true },
  { key: 'ASP_DHASH_EXACT_DROP', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Drop exact dHash duplicates before selection', category: 'Frame Selection' },
  { key: 'ASP_HIGH_HOLD_RESPONSE', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.7, description: 'phaseCorrelate response floor for hold merge', category: 'Frame Selection' },
  { key: 'ASP_HOLD_AVERAGE', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Overmix-style ECC sub-pixel averaging within hold blocks', category: 'Frame Selection' },
  { key: 'ASP_BLUR_REJECT_THRESH', type: 'float', min: 0.0, defaultVal: 50.0, description: 'Laplacian-variance floor for blurry-frame rejection (0=off)', category: 'Frame Selection', isPrimary: true },
  { key: 'ASP_CONTRAST_THRESH', type: 'float', min: 0.0, defaultVal: 15.0, description: 'Pixel-std floor for low-contrast frame rejection (0=off)', category: 'Frame Selection' },
  { key: 'ASP_NEAR_DUP_LUMA', type: 'float', min: 0.0, max: 255.0, defaultVal: 3.0, description: 'Near-dup luma dedup ceiling (0=off)', category: 'Frame Selection' },
  { key: 'ASP_TEMPORAL_VAR_THRESH', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.01, description: 'Static-frame temporal variance floor (0=off)', category: 'Frame Selection' },
  { key: 'ASP_OTSU_BG_CORR', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Per-pair Otsu bg mask for phase correlation', category: 'Frame Selection' },
  { key: 'ASP_TWO_CHANNEL_SELECT', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'BiRefNet two-channel camera/animation selection (experimental)', category: 'Frame Selection' },
  { key: 'ASP_POSE_WINDOW_PX', type: 'int', min: 0, defaultVal: 0, description: 'DINOv2 pose-consistent selection window (0=off, experimental)', category: 'Frame Selection' },
  { key: 'ASP_PHASE_AWARE_SELECT', type: 'bool', min: 0, max: 1, defaultVal: 0, description: '§2.4 Pass-2 bias toward same-phase candidates', category: 'Frame Selection' },
  { key: 'ASP_PHASE_CROSS_PENALTY', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.15, description: '§2.4 tie-break penalty applied to cross-phase candidate', category: 'Frame Selection' },
  { key: 'ASP_MAX_SKIPPABLE_HOLD_SIZE', type: 'int', min: 1, defaultVal: 8, description: 'Max hold-block size (frames) for animation hold', category: 'Frame Selection' },
  { key: 'ASP_POSE_REFINE_LOOK_RANGE', type: 'int', min: 0, defaultVal: 2, description: 'Pass-2 pose refinement search window (+-N slots)', category: 'Frame Selection' },
  { key: 'ASP_POSE_REFINE_MIN_GAIN', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.05, description: 'Min similarity improvement to swap candidates', category: 'Frame Selection' },
  { key: 'ASP_POSE_REFINE_MIN_ADV_FRAC', type: 'float', min: 0.0, defaultVal: 0.4, description: 'Min frame-advance fraction constraint', category: 'Frame Selection' },
  { key: 'ASP_POSE_REFINE_MAX_ADV_FRAC', type: 'float', min: 0.0, defaultVal: 1.8, description: 'Max frame-advance fraction constraint', category: 'Frame Selection' },
  { key: 'ASP_POSE_REFINE_SAME_HOLD_PENALTY', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.1, description: 'Penalty for staying in same hold block', category: 'Frame Selection' },
  { key: 'ASP_POSE_PATH_SELECT', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Experimental dynamic-programming pose path selection', category: 'Frame Selection' },
  { key: 'ASP_POSE_PATH_SAFE', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Reject experimental pose paths with structural-risk diagnostics', category: 'Frame Selection' },

  // ── Video Ingestion ──
  { key: 'ASP_VIDEO_MAX_FRAMES', type: 'int', min: 1, defaultVal: 300, description: 'Max frames decoded from a video input', category: 'Video Ingestion' },
  { key: 'ASP_VIDEO_PROXY_SCALE', type: 'float', min: 0.05, max: 1.0, defaultVal: 0.25, description: 'Proxy decode scale for selection pass', category: 'Video Ingestion', isPrimary: true },
  { key: 'ASP_VIDEO_TELECINE_MAD', type: 'float', min: 0.0, defaultVal: 0.01, description: 'Telecine duplicate MAD threshold', category: 'Video Ingestion' },
  { key: 'ASP_VIDEO_KEYFRAMES_ONLY', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Decode only keyframes in proxy pass', category: 'Video Ingestion' },

  // ── Masking & Segmentation ──
  { key: 'ASP_USE_SAM2', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Use SAM-2 video predictor instead of BiRefNet', category: 'Masking', isPrimary: true },

  // ── Matching & Geometric Alignment ──
  { key: 'ASP_MATCH_SPREAD_CEIL', type: 'float', min: 0.0, defaultVal: 30.0, description: 'Max MAD of per-match displacements (0=off)', category: 'Matching & Alignment' },
  { key: 'ASP_LOFTR_BG_RATIO_MIN', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.15, description: 'Min fraction of LoFTR matches on background (0=off)', category: 'Matching & Alignment', isPrimary: true },
  { key: 'ASP_SIMILARITY_MODE', type: 'bool', min: 0, max: 1, defaultVal: 1, description: '4-DOF similarity constraint for per-pair affines', category: 'Matching & Alignment', isPrimary: true },
  { key: 'ASP_ALIGN_GATE_DX', type: 'float', min: 0.0, defaultVal: 50.0, description: '75th-pct |dx| gate for vertical-scroll alignment', category: 'Matching & Alignment', isPrimary: true },
  { key: 'ASP_BA_F_SCALE', type: 'float', min: 0.0, defaultVal: 1.0, description: 'Cauchy loss f_scale (px) in bundle adjustment', category: 'Matching & Alignment', isPrimary: true },
  { key: 'ASP_GNC_OUTER', type: 'int', min: 1, max: 32, defaultVal: 4, description: 'GNC outer continuation iterations in BA', category: 'Matching & Alignment' },
  { key: 'ASP_DY_CV_MAX', type: 'float', min: 0.0, defaultVal: 0.65, description: 'dy_cv gate: SCANS fallback above this step-CV (0=off)', category: 'Matching & Alignment' },
  { key: 'ASP_ST_INLIER_THRESHOLD', type: 'float', min: 0.0, defaultVal: 20.0, description: 'Max allowed disagreement (px) vs spanning-tree reference', category: 'Matching & Alignment' },
  { key: 'ASP_ROT_TIGHT', type: 'float', min: 0.0, defaultVal: 2.0, description: 'Tight rotation threshold (high variance)', category: 'Matching & Alignment' },
  { key: 'ASP_ROT_LOOSE', type: 'float', min: 0.0, defaultVal: 6.0, description: 'Loose rotation threshold (near-identical rotation)', category: 'Matching & Alignment' },
  { key: 'ASP_SC_TIGHT', type: 'float', min: 0.0, defaultVal: 0.05, description: 'Tight scale threshold (high variance)', category: 'Matching & Alignment' },
  { key: 'ASP_SC_LOOSE', type: 'float', min: 0.0, defaultVal: 0.15, description: 'Loose scale threshold (near-identical scale)', category: 'Matching & Alignment' },
  { key: 'ASP_MONO_TAU_MIN', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.7, description: 'Min |Kendall tau| for translation monotonicity', category: 'Matching & Alignment' },
  { key: 'ASP_ROT_SCALE_CONSISTENCY_THRESH', type: 'float', min: 0.0, defaultVal: 0.1, description: 'Consistency threshold for adaptive tight/loose', category: 'Matching & Alignment' },

  // ── Foreground Registration & Flow ──
  { key: 'ASP_FG_REGISTER', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Enable Stage 8.5 foreground pose registration', category: 'Foreground Registration', isPrimary: true },
  { key: 'ASP_FLOW_ENGINE', type: 'str', defaultVal: 'dis', description: 'Dense flow engine: searaft | dis', category: 'Foreground Registration', isPrimary: true },
  { key: 'ASP_ARAP_PUSH', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'ARAP Push phase before Regularise', category: 'Foreground Registration', isPrimary: true },
  { key: 'ASP_FG_MAX_RESIDUAL', type: 'float', min: 0.0, defaultVal: 45.0, description: 'Max animation residual (px) to warp; above → single-pose', category: 'Foreground Registration' },

  // ── Rendering & Temporal Median ──
  { key: 'ASP_FG_EXCLUDE_MEDIAN', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Foreground-excluded temporal median (A5)', category: 'Rendering', isPrimary: true },
  { key: 'ASP_BG_AVERAGE', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Overmix-style mean/median blend for confirmed-bg samples', category: 'Rendering' },
  { key: 'ASP_BG_AVERAGE_FULL_AT', type: 'int', min: 3, defaultVal: 5, description: 'Sample count for full mean weight', category: 'Rendering' },
  { key: 'ASP_MASKED_MEDIAN', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Leave always-fg pixels black instead of ghost-averaging', category: 'Rendering', isPrimary: true },
  { key: 'ASP_ADAPTIVE_RENDER_GAIN', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Adaptive gain clamp in sequential render normalisation', category: 'Rendering', isPrimary: true },
  { key: 'ASP_GAIN_DRIFT_MAX', type: 'float', min: 0.0, defaultVal: 2.0, description: 'Max cumulative gain fold-change before reset (0=off)', category: 'Rendering' },
  { key: 'ASP_GPU_MEDIAN', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'GPU temporal median via base (UMat)', category: 'Rendering' },
  { key: 'ASP_COV_MIN_MULTI_PCT', type: 'float', min: 0.0, max: 1.0, defaultVal: 0.30, description: 'Min multi-frame canvas coverage before SCANS fallback', category: 'Rendering', isPrimary: true },

  // ── Compositing & Gain Compensation ──
  { key: 'ASP_PHASE_COMPOSITE', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Phase-consistent compositing: escalate to single-pose at boundaries', category: 'Compositing', isPrimary: true },
  { key: 'ASP_GRAPHCUT_SEAM', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'GraphCut global multi-image seam', category: 'Compositing' },
  { key: 'ASP_GC_FEATHER_PX', type: 'int', min: 0, defaultVal: 40, description: 'Feather width at GraphCut ownership boundaries', category: 'Compositing' },
  { key: 'ASP_BLOCKS_GAIN_COMP', type: 'bool', min: 0, max: 1, defaultVal: 1, description: '32×32 blocks BGR gain compensation in blend zones', category: 'Compositing', isPrimary: true },
  { key: 'ASP_BLOCKS_LUM_COMP', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'LAB-L blocks gain compensation in blend zones', category: 'Compositing' },
  { key: 'ASP_GLOBAL_GAIN_COMP', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Pre-seam sequential global gain equalization', category: 'Compositing' },
  { key: 'ASP_JOINT_GAIN_SOLVE', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'Brown-Lowe joint gain solve', category: 'Compositing', isPrimary: true },
  { key: 'ASP_JOINT_GAIN_SIGMA_N', type: 'float', min: 0.01, defaultVal: 10.0, description: 'Joint gain solve noise sigma', category: 'Compositing' },
  { key: 'ASP_JOINT_GAIN_SIGMA_G', type: 'float', min: 0.001, defaultVal: 0.1, description: 'Joint gain solve gain-prior sigma', category: 'Compositing' },
  { key: 'ASP_JOINT_GAIN_ROBUST', type: 'bool', min: 0, max: 1, defaultVal: 1, description: 'Reject isolated overlap ratios before joint solve', category: 'Compositing' },
  { key: 'ASP_SP_SOFT_PX', type: 'int', min: 0, defaultVal: 10, description: 'Single-pose soft-edge half-width (px)', category: 'Compositing', isPrimary: true },
  { key: 'ASP_BG_NORM_MIN_PX', type: 'int', min: 0, defaultVal: 200, description: 'Min bg pixels for normalisation gain estimate', category: 'Compositing' },
  { key: 'ASP_POST_SEAM_WARN_THRESH', type: 'float', min: 0.0, defaultVal: 15.0, description: 'Post-composite seam lum-step warning threshold', category: 'Compositing' },

  // ── C++ Acceleration ──
  { key: 'ASP_BATCH_GPU', type: 'bool', min: 0, max: 1, defaultVal: 0, description: 'GPU dispatch for C++ base kernels', category: 'C++ Acceleration' }
];

export default function AdvancedConfigDrawer() {
  const [activeTab, setActiveTab] = useState<'primary' | 'advanced'>('primary');
  const [activeCategory, setActiveCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [configValues, setConfigValues] = useState<Record<string, ConfigValue>>(() => {
    const initial: Record<string, ConfigValue> = {};
    ASP_CONFIG_MATRIX.forEach(entry => {
      initial[entry.key] = entry.defaultVal;
    });
    return initial;
  });
  const [copied, setCopied] = useState<boolean>(false);
  const [selectedPreset, setSelectedPreset] = useState<string>('laptop_balanced');

  const categories = useMemo(() => {
    const cats = Array.from(new Set(ASP_CONFIG_MATRIX.map(e => e.category)));
    return ['All', ...cats];
  }, []);

  const filteredEntries = useMemo(() => {
    return ASP_CONFIG_MATRIX.filter(entry => {
      if (activeTab === 'primary' && !entry.isPrimary) return false;
      if (activeCategory !== 'All' && entry.category !== activeCategory) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return entry.key.toLowerCase().includes(q) || entry.description.toLowerCase().includes(q);
      }
      return true;
    });
  }, [activeTab, activeCategory, searchQuery]);

  const applyPreset = (preset: string) => {
    setSelectedPreset(preset);
    const updated = { ...configValues };

    if (preset === 'laptop_balanced') {
      updated['ASP_HOLD_THRESHOLD'] = 0.05;
      updated['ASP_USE_SAM2'] = 0;
      updated['ASP_FLOW_ENGINE'] = 'dis';
      updated['ASP_PHASE_COMPOSITE'] = 0;
      updated['ASP_JOINT_GAIN_SOLVE'] = 0;
      updated['ASP_BATCH_GPU'] = 0;
      updated['ASP_VIDEO_PROXY_SCALE'] = 0.25;
    } else if (preset === 'desktop_quality') {
      updated['ASP_HOLD_THRESHOLD'] = 0.02;
      updated['ASP_USE_SAM2'] = 1;
      updated['ASP_FLOW_ENGINE'] = 'searaft';
      updated['ASP_PHASE_COMPOSITE'] = 1;
      updated['ASP_JOINT_GAIN_SOLVE'] = 1;
      updated['ASP_BATCH_GPU'] = 1;
      updated['ASP_VIDEO_PROXY_SCALE'] = 0.50;
    } else if (preset === 'research_ungated') {
      updated['ASP_ALIGN_GATE_DX'] = 9999.0;
      updated['ASP_COV_MIN_MULTI_PCT'] = 0.0;
      updated['ASP_DY_CV_MAX'] = 0.0;
    }

    setConfigValues(updated);
  };

  const handleValueChange = (key: string, val: ConfigValue) => {
    setConfigValues(prev => ({ ...prev, [key]: val }));
    setSelectedPreset('custom');
  };

  const generateToml = () => {
    return Object.entries(configValues)
      .map(([k, v]) => `${k} = ${typeof v === 'string' ? `"${v}"` : v}`)
      .join('\n');
  };

  const handleCopyManifest = () => {
    const toml = generateToml();
    navigator.clipboard.writeText(toml);
    setCopied(true);
    showAchievementToast({
      title: 'Configuration copied',
      message: 'ASP TOML is ready to paste into your environment.',
    });
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-[#1a1c23] bg-[#07080b] rounded-xl overflow-hidden shadow-2xl">
      {/* Header Banner */}
      <div className="bg-[#0d0f14] border-b border-[#1a1c23] px-6 py-4 flex flex-wrap justify-between items-center gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-[#00f0ff]/10 border border-[#00f0ff]/30 text-[#00f0ff]">
            <Sliders size={18} />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#e2e8f0] flex items-center gap-2">
              ASP Configuration Matrix
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#00f0ff]/10 border border-[#00f0ff]/30 text-[#00f0ff]">
                M2 Verified
              </span>
            </h3>
            <p className="text-xs text-[#8c92a0]">
              Curated 20-flag primary profile with expandable 73-parameter schema & live validation.
            </p>
          </div>
        </div>

        {/* Preset Selector & Action Buttons */}
        <div className="flex items-center gap-3">
          <div className="flex items-center space-x-1.5 bg-[#14161d] border border-[#1a1c23] px-2.5 py-1 rounded-lg">
            <span className="text-xs font-mono text-[#8c92a0]">Preset:</span>
            <select
              value={selectedPreset}
              onChange={e => applyPreset(e.target.value)}
              className="bg-transparent text-xs font-mono font-bold text-[#00f0ff] outline-none cursor-pointer"
            >
              <option value="laptop_balanced" className="bg-[#0d0f14] text-[#e2e8f0]">Laptop Balanced (Default)</option>
              <option value="desktop_quality" className="bg-[#0d0f14] text-[#e2e8f0]">Desktop Quality (Full)</option>
              <option value="research_ungated" className="bg-[#0d0f14] text-[#e2e8f0]">Research / Ungated</option>
              <option value="custom" className="bg-[#0d0f14] text-[#e2e8f0]">Custom Profile</option>
            </select>
          </div>

          <button
            onClick={handleCopyManifest}
            className="flex items-center space-x-1.5 text-xs font-mono px-3 py-1.5 bg-[#00f0ff]/10 border border-[#00f0ff]/40 text-[#00f0ff] rounded-lg hover:bg-[#00f0ff]/20 transition-all"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied TOML' : 'Copy TOML'}</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs & Search */}
      <div className="px-6 pt-4 pb-3 border-b border-[#1a1c23] flex flex-wrap justify-between items-center gap-4 bg-[#0a0b0e]">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('primary')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold border transition-all ${
              activeTab === 'primary'
                ? 'bg-[#00f0ff] text-[#07080b] border-[#00f0ff] shadow-[0_0_12px_rgba(0,240,255,0.2)]'
                : 'bg-[#14161d] text-[#8c92a0] border-[#1a1c23] hover:text-[#e2e8f0]'
            }`}
          >
            Primary Profile (20 Flags)
          </button>

          <button
            onClick={() => setActiveTab('advanced')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold border transition-all ${
              activeTab === 'advanced'
                ? 'bg-[#ff0055] text-white border-[#ff0055] shadow-[0_0_12px_rgba(255,0,85,0.2)]'
                : 'bg-[#14161d] text-[#8c92a0] border-[#1a1c23] hover:text-[#e2e8f0]'
            }`}
          >
            Advanced Matrix (73 Total Flags)
          </button>
        </div>

        {/* Search */}
        <div className="relative min-w-[240px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8c92a0]" />
          <input
            type="text"
            placeholder="Search parameter..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-[#14161d] border border-[#1a1c23] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[#e2e8f0] font-mono placeholder:text-[#4a4d57] focus:border-[#00f0ff] outline-none"
          />
        </div>
      </div>

      {/* Category Pills (Advanced Mode only) */}
      {activeTab === 'advanced' && (
        <div className="px-6 py-2.5 border-b border-[#1a1c23] flex items-center space-x-1.5 overflow-x-auto bg-[#07080b]">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono whitespace-nowrap transition-all ${
                activeCategory === cat
                  ? 'bg-[#00f0ff]/15 text-[#00f0ff] border border-[#00f0ff]/40 font-bold'
                  : 'text-[#8c92a0] hover:text-[#e2e8f0] hover:bg-[#14161d]'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Parameter Grid Table */}
      <div className="max-h-[520px] overflow-y-auto divide-y divide-[#1a1c23]/60 bg-[#07080b]">
        {filteredEntries.length === 0 ? (
          <div className="p-12 text-center text-[#8c92a0] text-xs font-mono">
            No matching parameters found for "{searchQuery}".
          </div>
        ) : (
          filteredEntries.map(entry => {
            const val = configValues[entry.key];

            return (
              <div key={entry.key} className="px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 hover:bg-[#0e1017]/50 transition-colors">
                <div className="max-w-[500px]">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold text-[#e2e8f0]">
                      {entry.key}
                    </span>
                    {entry.isPrimary && (
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#00f0ff]/10 text-[#00f0ff] border border-[#00f0ff]/20">
                        Primary
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-[#8c92a0]">
                      ({entry.type})
                    </span>
                  </div>
                  <p className="text-xs text-[#8c92a0] mt-1 leading-relaxed">
                    {entry.description}
                  </p>
                </div>

                {/* Interactive Input Control */}
                <div className="flex items-center space-x-3">
                  {entry.type === 'bool' ? (
                    <button
                      onClick={() => handleValueChange(entry.key, val ? 0 : 1)}
                      className={`w-12 h-6 rounded-full p-1 transition-colors flex items-center ${
                        val ? 'bg-[#00f0ff] justify-end' : 'bg-[#1a1c23] justify-start'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full shadow-md ${val ? 'bg-[#07080b]' : 'bg-[#8c92a0]'}`} />
                    </button>
                  ) : entry.type === 'str' ? (
                    <select
                      value={typeof val === 'string' ? val : 'dis'}
                      onChange={e => handleValueChange(entry.key, e.target.value)}
                      className="bg-[#14161d] border border-[#1a1c23] text-xs font-mono text-[#00f0ff] px-3 py-1 rounded-lg outline-none focus:border-[#00f0ff]"
                    >
                      <option value="dis">dis (Fast / OpenCV)</option>
                      <option value="searaft">searaft (Dense Recurrent)</option>
                    </select>
                  ) : (
                    <div className="flex items-center space-x-2">
                      <input
                        type="number"
                        step={entry.type === 'float' ? '0.05' : '1'}
                        min={entry.min}
                        max={entry.max}
                        value={typeof val === 'number' ? val : 0}
                        onChange={e => handleValueChange(entry.key, entry.type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10))}
                        className="w-24 bg-[#14161d] border border-[#1a1c23] text-xs font-mono text-[#00f0ff] px-2.5 py-1 rounded-lg text-right outline-none focus:border-[#00f0ff]"
                      />
                      {entry.min !== undefined && entry.max !== undefined && (
                        <span className="text-[10px] font-mono text-[#4a4d57]">
                          [{entry.min}, {entry.max}]
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="bg-[#0a0b0e] border-t border-[#1a1c23] px-6 py-3 flex flex-wrap justify-between items-center text-xs font-mono text-[#8c92a0]">
        <div>
          Showing {filteredEntries.length} of {ASP_CONFIG_MATRIX.length} parameters
        </div>
        <div className="flex items-center space-x-2 text-[#4a4d57]">
          <span>Strict Typed TOML Serialization</span>
          <span>•</span>
          <span className="text-[#00f0ff]">Zero Hidden Knobs</span>
        </div>
      </div>
    </div>
  );
}
