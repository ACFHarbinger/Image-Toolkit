/** Signal processing utilities for the analytics backbone.
 *
 *  Provides Cooley-Tukey FFT/IFFT, window functions, and power spectrum
 *  computation — used by Phase 3.8A (ghosting autocorrelation, mirrored from
 *  the Rust bench) and Phase 6 (timing trace frequency analysis). */

export interface Complex {
  re: number;
  im: number;
}

const cmul = (a: Complex, b: Complex): Complex => ({
  re: a.re * b.re - a.im * b.im,
  im: a.re * b.im + a.im * b.re,
});

const cadd = (a: Complex, b: Complex): Complex => ({ re: a.re + b.re, im: a.im + b.im });
const csub = (a: Complex, b: Complex): Complex => ({ re: a.re - b.re, im: a.im - b.im });

/** Bit-reversal permutation in-place. */
function bitReverse(a: Complex[]): void {
  const n = a.length;
  let j = 0;
  for (let i = 1; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) [a[i], a[j]] = [a[j], a[i]];
  }
}

/**
 * Cooley-Tukey iterative FFT (radix-2 DIT).
 * Input length must be a power of 2.
 */
export function fft(input: Complex[]): Complex[] {
  const n = input.length;
  if ((n & (n - 1)) !== 0) throw new Error('FFT input length must be a power of 2');
  const a = input.map(c => ({ ...c }));
  bitReverse(a);

  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len;
    const wlen: Complex = { re: Math.cos(ang), im: Math.sin(ang) };
    for (let i = 0; i < n; i += len) {
      let w: Complex = { re: 1, im: 0 };
      for (let j = 0; j < len / 2; j++) {
        const u = a[i + j];
        const v = cmul(a[i + j + len / 2], w);
        a[i + j] = cadd(u, v);
        a[i + j + len / 2] = csub(u, v);
        w = cmul(w, wlen);
      }
    }
  }
  return a;
}

/** Inverse FFT. */
export function ifft(input: Complex[]): Complex[] {
  const conjugated = input.map(c => ({ re: c.re, im: -c.im }));
  const result = fft(conjugated);
  const n = input.length;
  return result.map(c => ({ re: c.re / n, im: -c.im / n }));
}

/** Convert a real-valued signal to a zero-imaginary Complex array. */
export const realToComplex = (xs: number[]): Complex[] =>
  xs.map(re => ({ re, im: 0 }));

/** Power spectrum (magnitude squared) of a real-valued signal.
 *  Input is zero-padded to the next power of 2 if needed. */
export function powerSpectrum(signal: number[]): number[] {
  let n = 1;
  while (n < signal.length) n <<= 1;
  const padded = [...signal, ...new Array<number>(n - signal.length).fill(0)];
  const spectrum = fft(realToComplex(padded));
  // Return only the non-redundant half (DC + positive frequencies).
  return spectrum.slice(0, n / 2 + 1).map(c => c.re * c.re + c.im * c.im);
}

// ── Window functions ─────────────────────────────────────────────────────────

/** Hann window coefficient for sample i of N. */
export const hannWindow = (i: number, N: number): number =>
  0.5 * (1 - Math.cos((2 * Math.PI * i) / (N - 1)));

/** Hamming window coefficient. */
export const hammingWindow = (i: number, N: number): number =>
  0.54 - 0.46 * Math.cos((2 * Math.PI * i) / (N - 1));

/** Apply a window function to a signal. */
export const applyWindow = (
  signal: number[],
  windowFn: (i: number, N: number) => number,
): number[] => signal.map((x, i) => x * windowFn(i, signal.length));

// ── Autocorrelation ──────────────────────────────────────────────────────────

/** Circular autocorrelation via FFT.
 *
 *  Returns the autocorrelation at lags [0 .. N-1].  The DC component at lag 0
 *  is the signal energy.  Used for detecting ghosting (Phase 3.8A). */
export function autocorrelation(signal: number[]): number[] {
  let n = 1;
  while (n < signal.length) n <<= 1;
  const padded = [...signal, ...new Array<number>(n - signal.length).fill(0)];
  const spectrum = fft(realToComplex(padded));
  // Multiply each bin by its conjugate to get |X(f)|².
  const power = spectrum.map(c => ({ re: c.re * c.re + c.im * c.im, im: 0 }));
  const result = ifft(power);
  return result.slice(0, signal.length).map(c => c.re);
}
