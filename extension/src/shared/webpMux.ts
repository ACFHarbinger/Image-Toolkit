/**
 * Hand-rolled animated-WebP container muxer (§7.15D).
 *
 * The roadmap's original plan for video-clip export was "MediaRecorder →
 * WebM, optional app-side conversion to GIF/WebP via ffmpeg" — i.e. true
 * GIF/WebP export was explicitly framed as an *optional*, app-side (bridge)
 * follow-on, not required for this pass. This task's own scope discipline
 * excludes new backend/bridge work, so the ffmpeg conversion path isn't
 * built here.
 *
 * Instead of stopping at WebM-only, this module gets to genuine animated
 * WebP export with zero new dependencies: `HTMLCanvasElement.toBlob(...,
 * "image/webp")` already lets the browser encode each *individual* video
 * frame as a still WebP image (no browser exposes an *animated*-WebP encoder
 * via any Canvas/WebCodecs API). What's missing is only the *container* —
 * animated WebP is a well-documented RIFF chunk format (VP8X + ANIM +
 * repeated ANMF chunks, each wrapping a per-frame VP8/VP8L(+ALPH) bitstream
 * chunk lifted out of an ordinary single-image WebP file). Muxing that by
 * hand is a few dozen lines of chunk-writing, not an image codec — so unlike
 * GIF (which would need a real from-scratch LZW/palette encoder, i.e.
 * `gif.js`-sized dependency territory), animated WebP was reachable without
 * adding a library. That's why WebP, not GIF, is this feature's export
 * format — a deliberate choice, not an oversight of the issue's title.
 *
 * Reference: https://developers.google.com/speed/webp/docs/riff_container
 */

/** One already-encoded still WebP frame plus how long to show it. */
export interface WebpFrame {
  /** Bytes of a complete single-image WebP file, e.g. from
   * `canvas.toBlob("image/webp")`. */
  bytes: ArrayBuffer;
  durationMs: number;
}

interface RiffChunk {
  fourCC: string;
  data: Uint8Array;
}

/** Parse the top-level RIFF chunks of a WEBP file (after the 12-byte
 * RIFF/size/WEBP header). Chunk payloads are even-padded per the RIFF spec;
 * the returned `data` excludes the padding byte. */
function parseRiffChunks(bytes: Uint8Array): RiffChunk[] {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const chunks: RiffChunk[] = [];
  let offset = 12; // skip "RIFF" + size(4) + "WEBP"
  while (offset + 8 <= bytes.length) {
    const fourCC = String.fromCharCode(
      bytes[offset],
      bytes[offset + 1],
      bytes[offset + 2],
      bytes[offset + 3],
    );
    const size = view.getUint32(offset + 4, true);
    const dataStart = offset + 8;
    const data = bytes.subarray(dataStart, dataStart + size);
    chunks.push({ fourCC, data });
    offset = dataStart + size + (size % 2); // even-padded
  }
  return chunks;
}

/**
 * Extract the frame-payload bytes to embed inside an ANMF chunk: the
 * optional ALPH chunk followed by the VP8/VP8L bitstream chunk, each still
 * wrapped in their own fourCC+size header (that's the format ANMF expects —
 * it is itself a miniature chunk stream, not a raw bitstream).
 */
function extractFramePayload(fileBytes: ArrayBuffer): {
  payload: Uint8Array;
  hasAlpha: boolean;
} {
  const bytes = new Uint8Array(fileBytes);
  const chunks = parseRiffChunks(bytes);
  const keep = chunks.filter(
    (c) => c.fourCC === "ALPH" || c.fourCC === "VP8 " || c.fourCC === "VP8L",
  );
  const parts: Uint8Array[] = [];
  let hasAlpha = false;
  for (const c of keep) {
    if (c.fourCC === "ALPH") hasAlpha = true;
    parts.push(chunkBytes(c.fourCC, c.data));
  }
  const total = parts.reduce((n, p) => n + p.length, 0);
  const payload = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    payload.set(p, off);
    off += p.length;
  }
  return { payload, hasAlpha };
}

/** Wrap `data` in a RIFF sub-chunk: fourCC(4) + size(4, LE) + data + pad. */
function chunkBytes(fourCC: string, data: Uint8Array): Uint8Array {
  const padded = data.length % 2 === 1;
  const out = new Uint8Array(8 + data.length + (padded ? 1 : 0));
  for (let i = 0; i < 4; i++) out[i] = fourCC.charCodeAt(i);
  new DataView(out.buffer).setUint32(4, data.length, true);
  out.set(data, 8);
  return out;
}

function writeUint24LE(out: Uint8Array, offset: number, value: number): void {
  out[offset] = value & 0xff;
  out[offset + 1] = (value >> 8) & 0xff;
  out[offset + 2] = (value >> 16) & 0xff;
}

/**
 * Mux a sequence of still-WebP frames into one animated WebP file.
 * All frames must share `width`×`height` (true by construction here — every
 * frame is drawn from the same fixed-size capture canvas).
 */
export function muxAnimatedWebp(
  frames: WebpFrame[],
  width: number,
  height: number,
  loopCount = 0,
): Blob {
  const anmfChunks: Uint8Array[] = [];
  let hasAlpha = false;

  for (const frame of frames) {
    const { payload, hasAlpha: frameAlpha } = extractFramePayload(frame.bytes);
    if (frameAlpha) hasAlpha = true;

    const header = new Uint8Array(16);
    writeUint24LE(header, 0, 0); // frame X (in 2px units) = 0
    writeUint24LE(header, 3, 0); // frame Y (in 2px units) = 0
    writeUint24LE(header, 6, width - 1);
    writeUint24LE(header, 9, height - 1);
    writeUint24LE(header, 12, Math.max(0, Math.round(frame.durationMs)));
    header[15] = 0b00000010; // disposal=none(bit0=0), blending=overwrite(bit1=1)

    const frameData = new Uint8Array(header.length + payload.length);
    frameData.set(header, 0);
    frameData.set(payload, header.length);
    anmfChunks.push(chunkBytes("ANMF", frameData));
  }

  const vp8x = new Uint8Array(10);
  vp8x[0] = 0b00010010 | (hasAlpha ? 0b00010000 : 0); // ICC(0) ALPHA EXIF(0) XMP(0) ANIM(1)
  writeUint24LE(vp8x, 4, width - 1);
  writeUint24LE(vp8x, 7, height - 1);

  const anim = new Uint8Array(6);
  // Background color (BGRA), fully transparent black.
  anim[0] = 0;
  anim[1] = 0;
  anim[2] = 0;
  anim[3] = 0;
  new DataView(anim.buffer).setUint16(4, loopCount & 0xffff, true);

  const vp8xChunk = chunkBytes("VP8X", vp8x);
  const animChunk = chunkBytes("ANIM", anim);
  const bodyLength =
    4 + // "WEBP"
    vp8xChunk.length +
    animChunk.length +
    anmfChunks.reduce((n, c) => n + c.length, 0);

  const out = new Uint8Array(8 + bodyLength);
  out[0] = 0x52; // R
  out[1] = 0x49; // I
  out[2] = 0x46; // F
  out[3] = 0x46; // F
  new DataView(out.buffer).setUint32(4, bodyLength, true);
  out[8] = 0x57; // W
  out[9] = 0x45; // E
  out[10] = 0x42; // B
  out[11] = 0x50; // P

  let off = 12;
  out.set(vp8xChunk, off);
  off += vp8xChunk.length;
  out.set(animChunk, off);
  off += animChunk.length;
  for (const c of anmfChunks) {
    out.set(c, off);
    off += c.length;
  }

  return new Blob([out], { type: "image/webp" });
}
