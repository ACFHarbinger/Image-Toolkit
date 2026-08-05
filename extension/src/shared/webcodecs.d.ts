/**
 * Minimal ambient types for the WebCodecs `ImageDecoder` API (§7.15B).
 *
 * As of this project's pinned toolchain, `ImageDecoder` is not yet part of
 * TypeScript's bundled `lib.dom.d.ts` (it's still a fairly new, Chromium-only
 * API), so it's declared here covering only the members `frames.ts` actually
 * uses. Runtime availability is feature-detected (`typeof ImageDecoder !==
 * "undefined"`) before anything here is touched — see `frames.ts`.
 */

interface ImageDecodeResult {
  readonly image: VideoFrame;
  readonly complete: boolean;
}

interface ImageDecodeOptions {
  frameIndex?: number;
  completeFramesOnly?: boolean;
}

interface ImageTrack {
  readonly animated: boolean;
  readonly frameCount: number;
  readonly repetitionCount: number;
  selected: boolean;
}

interface ImageTrackList {
  readonly ready: Promise<void>;
  readonly selectedTrack: ImageTrack | null;
  readonly length: number;
}

interface ImageDecoderInit {
  type: string;
  data: BufferSource;
  premultiplyAlpha?: "default" | "premultiply" | "none";
  colorSpaceConversion?: "default" | "none";
  preferAnimation?: boolean;
}

declare class ImageDecoder {
  constructor(init: ImageDecoderInit);
  readonly type: string;
  readonly complete: boolean;
  readonly completed: Promise<void>;
  readonly tracks: ImageTrackList;
  decode(options?: ImageDecodeOptions): Promise<ImageDecodeResult>;
  reset(): void;
  close(): void;
  static isTypeSupported(type: string): Promise<boolean>;
}
