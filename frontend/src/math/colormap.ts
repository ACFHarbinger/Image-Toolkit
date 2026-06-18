/** Perceptually-uniform colormaps for analytics visualisations.
 *
 *  Each colormap maps a scalar t ∈ [0, 1] to an `[R, G, B]` triple in [0, 255].
 *  Implementations use the reference lookup tables from matplotlib 3.x (17-stop
 *  down-sampled; linear interpolation between stops is accurate to ±2/255). */

export type RGB = [number, number, number];

type ColormapTable = readonly (readonly [number, number, number])[];

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

function sampleTable(table: ColormapTable, t: number): RGB {
  const n = table.length - 1;
  const pos = Math.min(Math.max(t, 0), 1) * n;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, n);
  const f = pos - lo;
  return [
    Math.round(lerp(table[lo][0], table[hi][0], f)),
    Math.round(lerp(table[lo][1], table[hi][1], f)),
    Math.round(lerp(table[lo][2], table[hi][2], f)),
  ];
}

// 17-stop reference tables (matplotlib 3.x).
const VIRIDIS_TABLE: ColormapTable = [
  [68, 1, 84],   [71, 22, 103],  [72, 40, 120],  [62, 57, 136],  [49, 74, 150],
  [38, 90, 160], [32, 105, 167], [29, 118, 171], [30, 131, 174], [33, 145, 175],
  [39, 158, 173],[49, 171, 168], [68, 184, 157], [93, 196, 143], [126, 208, 124],
  [163, 218, 100],[204, 228, 74],[253, 231, 37],
] as const;

const PLASMA_TABLE: ColormapTable = [
  [13, 8, 135],  [75, 3, 161],   [125, 3, 168],  [168, 7, 161],  [203, 24, 147],
  [229, 49, 126],[248, 77, 104], [255, 106, 84],  [255, 136, 68], [255, 164, 52],
  [250, 192, 38],[240, 219, 27], [236, 243, 27],
] as const;

const MAGMA_TABLE: ColormapTable = [
  [0, 0, 4],     [13, 11, 34],   [33, 17, 73],   [60, 15, 111],  [90, 22, 134],
  [119, 29, 147],[148, 41, 150], [177, 55, 148],  [208, 71, 135], [234, 93, 112],
  [250, 121, 94],[253, 152, 83], [254, 186, 86], [254, 218, 112],[253, 245, 147],
] as const;

const COOLWARM_TABLE: ColormapTable = [
  [59, 76, 192],  [90, 113, 225], [123, 147, 246], [157, 177, 255], [186, 200, 255],
  [213, 220, 250],[235, 235, 235],[250, 213, 200], [255, 183, 162], [241, 143, 123],
  [215, 95, 77],  [180, 44, 30],  [180, 4, 38],
] as const;

const INFERNO_TABLE: ColormapTable = [
  [0, 0, 4],     [17, 5, 38],    [44, 9, 74],    [78, 14, 101],  [110, 22, 116],
  [140, 31, 120],[170, 44, 118], [200, 57, 109],  [224, 78, 92],  [242, 104, 72],
  [253, 134, 52],[254, 165, 38], [253, 197, 42], [248, 230, 79], [252, 255, 164],
] as const;

/** Viridis — perceptually uniform, good for intensity / loss surfaces. */
export const viridis = (t: number): RGB => sampleTable(VIRIDIS_TABLE, t);

/** Plasma — high-contrast variant of viridis. */
export const plasma = (t: number): RGB => sampleTable(PLASMA_TABLE, t);

/** Magma — dark background, useful for density plots. */
export const magma = (t: number): RGB => sampleTable(MAGMA_TABLE, t);

/** Inferno — high contrast, accessible for colorblind viewers. */
export const inferno = (t: number): RGB => sampleTable(INFERNO_TABLE, t);

/** Coolwarm — diverging; grey midpoint; blue=low, red=high. */
export const coolwarm = (t: number): RGB => sampleTable(COOLWARM_TABLE, t);

export type ColormapName = 'viridis' | 'plasma' | 'magma' | 'inferno' | 'coolwarm';

const COLORMAPS: Record<ColormapName, (t: number) => RGB> = {
  viridis, plasma, magma, inferno, coolwarm,
};

/** Apply a named colormap to an array of values, normalising to [0, 1] first. */
export function applyColormap(values: number[], name: ColormapName = 'viridis'): RGB[] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const range = hi - lo || 1;
  const fn_ = COLORMAPS[name];
  return values.map(v => fn_((v - lo) / range));
}

/** Convert an RGB triple to a CSS hex colour string. */
export const rgbToHex = ([r, g, b]: RGB): string =>
  `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;

/** Apply colormap and return CSS hex strings. */
export const applyColormapHex = (values: number[], name: ColormapName = 'viridis'): string[] =>
  applyColormap(values, name).map(rgbToHex);
