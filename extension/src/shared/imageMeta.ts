/**
 * Client-side image metadata extraction (§7.16A).
 *
 * Pure TypeScript parsers — no bridge required:
 *  - PNG: dimensions (IHDR) + tEXt/iTXt/zTXt text chunks (zlib-compressed
 *    payloads inflated with the browser's DecompressionStream when available).
 *  - JPEG: dimensions (SOF segments), COM comment, XMP packet, and a compact
 *    EXIF IFD0 reader (Make/Model/Software/DateTime/Artist/…).
 *  - AI-generation metadata detection: a1111 `parameters`, ComfyUI
 *    `prompt`/`workflow` JSON, NovelAI, InvokeAI.
 */

export interface AiMetadata {
  /** Best-effort producer name (a1111 / ComfyUI / NovelAI / InvokeAI). */
  tool: string;
  /** Raw parameter payload (prompt text or JSON string). */
  raw: string;
}

export interface ImageMetadata {
  format: "png" | "jpeg" | "unknown";
  width?: number;
  height?: number;
  /** PNG text chunks / JPEG comment+XMP, keyed by chunk keyword. */
  text: Record<string, string>;
  exif: Record<string, string>;
  ai?: AiMetadata;
}

// ── helpers ─────────────────────────────────────────────────────────────────

const LATIN1 = new TextDecoder("latin1");
const UTF8 = new TextDecoder("utf-8");

async function inflate(data: Uint8Array): Promise<string | null> {
  if (typeof DecompressionStream === "undefined") return null;
  try {
    const stream = new Blob([data.slice().buffer as ArrayBuffer])
      .stream()
      .pipeThrough(new DecompressionStream("deflate"));
    const buf = await new Response(stream).arrayBuffer();
    return UTF8.decode(buf);
  } catch {
    return null;
  }
}

function detectAi(text: Record<string, string>): AiMetadata | undefined {
  if (text["parameters"]) {
    return { tool: "Stable Diffusion WebUI (a1111)", raw: text["parameters"] };
  }
  if (text["workflow"] || text["prompt"]) {
    return {
      tool: "ComfyUI",
      raw: text["workflow"] ?? text["prompt"],
    };
  }
  if (text["Software"]?.startsWith("NovelAI") && text["Comment"]) {
    return { tool: "NovelAI", raw: text["Comment"] };
  }
  if (text["invokeai_metadata"]) {
    return { tool: "InvokeAI", raw: text["invokeai_metadata"] };
  }
  return undefined;
}

// ── PNG ─────────────────────────────────────────────────────────────────────

const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

function isPng(bytes: Uint8Array): boolean {
  return PNG_SIG.every((b, i) => bytes[i] === b);
}

async function parsePng(bytes: Uint8Array): Promise<ImageMetadata> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const meta: ImageMetadata = { format: "png", text: {}, exif: {} };

  let off = 8;
  while (off + 8 <= bytes.length) {
    const length = view.getUint32(off);
    const type = LATIN1.decode(bytes.subarray(off + 4, off + 8));
    const data = bytes.subarray(off + 8, off + 8 + length);

    if (type === "IHDR" && length >= 8) {
      meta.width = view.getUint32(off + 8);
      meta.height = view.getUint32(off + 12);
    } else if (type === "tEXt") {
      const sep = data.indexOf(0);
      if (sep > 0) {
        meta.text[LATIN1.decode(data.subarray(0, sep))] = LATIN1.decode(
          data.subarray(sep + 1),
        );
      }
    } else if (type === "iTXt") {
      const sep = data.indexOf(0);
      if (sep > 0) {
        const keyword = LATIN1.decode(data.subarray(0, sep));
        const compressed = data[sep + 1] === 1;
        // Skip compressionMethod, then language tag and translated keyword
        let p = sep + 3;
        p = data.indexOf(0, p) + 1; // end of language tag
        p = data.indexOf(0, p) + 1; // end of translated keyword
        if (p > 0 && p <= data.length) {
          const payload = data.subarray(p);
          const value = compressed
            ? await inflate(payload)
            : UTF8.decode(payload);
          if (value !== null) meta.text[keyword] = value;
        }
      }
    } else if (type === "zTXt") {
      const sep = data.indexOf(0);
      if (sep > 0) {
        const value = await inflate(data.subarray(sep + 2));
        if (value !== null) {
          meta.text[LATIN1.decode(data.subarray(0, sep))] = value;
        }
      }
    } else if (type === "IEND") {
      break;
    }
    off += 12 + length; // length + type + data + crc
  }

  meta.ai = detectAi(meta.text);
  return meta;
}

// ── JPEG ────────────────────────────────────────────────────────────────────

/** EXIF IFD0 tags worth showing (compact reader — ASCII values only). */
const EXIF_TAGS: Record<number, string> = {
  0x010e: "ImageDescription",
  0x010f: "Make",
  0x0110: "Model",
  0x0131: "Software",
  0x0132: "DateTime",
  0x013b: "Artist",
  0x8298: "Copyright",
};

function parseExif(data: Uint8Array, out: Record<string, string>): void {
  // data starts after the "Exif\0\0" marker: TIFF header
  if (data.length < 8) return;
  const le = data[0] === 0x49 && data[1] === 0x49; // "II" little-endian
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const u16 = (o: number) => view.getUint16(o, le);
  const u32 = (o: number) => view.getUint32(o, le);
  if (u16(2) !== 42) return;

  const ifdOff = u32(4);
  if (ifdOff + 2 > data.length) return;
  const count = u16(ifdOff);
  for (let i = 0; i < count; i++) {
    const e = ifdOff + 2 + i * 12;
    if (e + 12 > data.length) break;
    const tag = u16(e);
    const type = u16(e + 2);
    const n = u32(e + 4);
    const name = EXIF_TAGS[tag];
    if (!name || type !== 2) continue; // ASCII only
    const valOff = n <= 4 ? e + 8 : u32(e + 8);
    if (valOff + n > data.length) continue;
    const value = LATIN1.decode(data.subarray(valOff, valOff + n - 1)).trim();
    if (value) out[name] = value;
  }
}

const XMP_HEADER = "http://ns.adobe.com/xap/1.0/\0";

function parseJpeg(bytes: Uint8Array): ImageMetadata {
  const meta: ImageMetadata = { format: "jpeg", text: {}, exif: {} };
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);

  let off = 2; // skip FFD8
  while (off + 4 <= bytes.length) {
    if (bytes[off] !== 0xff) break;
    const marker = bytes[off + 1];
    if (marker === 0xd9 || marker === 0xda) break; // EOI / SOS
    const length = view.getUint16(off + 2);
    const seg = bytes.subarray(off + 4, off + 2 + length);

    if ((marker >= 0xc0 && marker <= 0xc3) || marker === 0xc5 || marker === 0xc6 || marker === 0xc7) {
      // SOFn: [precision u8][height u16][width u16]
      meta.height = view.getUint16(off + 5);
      meta.width = view.getUint16(off + 7);
    } else if (marker === 0xfe) {
      const comment = LATIN1.decode(seg).trim();
      if (comment) meta.text["Comment"] = comment;
    } else if (marker === 0xe1) {
      const head = LATIN1.decode(seg.subarray(0, Math.min(64, seg.length)));
      if (head.startsWith("Exif\0\0")) {
        parseExif(seg.subarray(6), meta.exif);
      } else if (head.startsWith(XMP_HEADER)) {
        meta.text["XMP"] = UTF8.decode(seg.subarray(XMP_HEADER.length)).trim();
      }
    }
    off += 2 + length;
  }

  // Some tools put a1111 parameters into the JPEG comment or EXIF UserComment
  if (meta.text["Comment"]?.includes("Steps:")) {
    meta.ai = { tool: "Stable Diffusion (JPEG comment)", raw: meta.text["Comment"] };
  }
  return meta;
}

// ── entry point ─────────────────────────────────────────────────────────────

export async function parseImageMetadata(
  bytes: Uint8Array,
): Promise<ImageMetadata> {
  if (isPng(bytes)) return parsePng(bytes);
  if (bytes[0] === 0xff && bytes[1] === 0xd8) return parseJpeg(bytes);
  return { format: "unknown", text: {}, exif: {} };
}
