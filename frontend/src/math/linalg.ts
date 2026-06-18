/** Linear algebra primitives used by graph layout, colormap interpolation,
 *  and the software-cartography visualisation (Phase 1.3). */

export type Vec2 = [number, number];
export type Vec3 = [number, number, number];
export type Vec4 = [number, number, number, number];

/** Column-major 3×3 matrix (compatible with CSS transform). */
export type Mat3 = [
  number, number, number,
  number, number, number,
  number, number, number,
];

/** Column-major 4×4 matrix. */
export type Mat4 = [
  number, number, number, number,
  number, number, number, number,
  number, number, number, number,
  number, number, number, number,
];

// ── Vec2 ops ─────────────────────────────────────────────────────────────────

export const add2 = ([ax, ay]: Vec2, [bx, by]: Vec2): Vec2 => [ax + bx, ay + by];
export const sub2 = ([ax, ay]: Vec2, [bx, by]: Vec2): Vec2 => [ax - bx, ay - by];
export const scale2 = ([x, y]: Vec2, s: number): Vec2 => [x * s, y * s];
export const dot2 = ([ax, ay]: Vec2, [bx, by]: Vec2): number => ax * bx + ay * by;
export const len2 = ([x, y]: Vec2): number => Math.sqrt(x * x + y * y);
export const norm2 = (v: Vec2): Vec2 => {
  const l = len2(v);
  return l === 0 ? [0, 0] : scale2(v, 1 / l);
};
export const lerp2 = (a: Vec2, b: Vec2, t: number): Vec2 =>
  [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// ── Vec3 ops ─────────────────────────────────────────────────────────────────

export const add3 = ([ax, ay, az]: Vec3, [bx, by, bz]: Vec3): Vec3 => [ax + bx, ay + by, az + bz];
export const sub3 = ([ax, ay, az]: Vec3, [bx, by, bz]: Vec3): Vec3 => [ax - bx, ay - by, az - bz];
export const scale3 = ([x, y, z]: Vec3, s: number): Vec3 => [x * s, y * s, z * s];
export const dot3 = ([ax, ay, az]: Vec3, [bx, by, bz]: Vec3): number => ax * bx + ay * by + az * bz;
export const len3 = ([x, y, z]: Vec3): number => Math.sqrt(x * x + y * y + z * z);
export const norm3 = (v: Vec3): Vec3 => {
  const l = len3(v);
  return l === 0 ? [0, 0, 0] : scale3(v, 1 / l);
};
export const cross3 = ([ax, ay, az]: Vec3, [bx, by, bz]: Vec3): Vec3 => [
  ay * bz - az * by,
  az * bx - ax * bz,
  ax * by - ay * bx,
];
export const lerp3 = (a: Vec3, b: Vec3, t: number): Vec3 =>
  [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

// ── Generic N-dimensional ops ─────────────────────────────────────────────────

export const dotN = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + ai * b[i], 0);

export const lenN = (v: number[]): number => Math.sqrt(dotN(v, v));

export const normN = (v: number[]): number[] => {
  const l = lenN(v);
  return l === 0 ? v.map(() => 0) : v.map(x => x / l);
};

export const scaleN = (v: number[], s: number): number[] => v.map(x => x * s);
export const addN = (a: number[], b: number[]): number[] => a.map((ai, i) => ai + b[i]);
export const subN = (a: number[], b: number[]): number[] => a.map((ai, i) => ai - b[i]);

// ── Mat3 ops ─────────────────────────────────────────────────────────────────

export const mat3Identity = (): Mat3 => [1, 0, 0, 0, 1, 0, 0, 0, 1];

/** Multiply two column-major 3×3 matrices. */
export const mat3Mul = (a: Mat3, b: Mat3): Mat3 => {
  const [a0, a1, a2, a3, a4, a5, a6, a7, a8] = a;
  const [b0, b1, b2, b3, b4, b5, b6, b7, b8] = b;
  return [
    a0 * b0 + a3 * b1 + a6 * b2, a1 * b0 + a4 * b1 + a7 * b2, a2 * b0 + a5 * b1 + a8 * b2,
    a0 * b3 + a3 * b4 + a6 * b5, a1 * b3 + a4 * b4 + a7 * b5, a2 * b3 + a5 * b4 + a8 * b5,
    a0 * b6 + a3 * b7 + a6 * b8, a1 * b6 + a4 * b7 + a7 * b8, a2 * b6 + a5 * b7 + a8 * b8,
  ];
};

export const mat3TranslationScale = (tx: number, ty: number, sx: number, sy: number): Mat3 =>
  [sx, 0, 0, 0, sy, 0, tx, ty, 1];

// ── Clamp / saturate ─────────────────────────────────────────────────────────

export const clamp = (x: number, lo: number, hi: number): number =>
  Math.min(Math.max(x, lo), hi);

export const saturate = (x: number): number => clamp(x, 0, 1);
