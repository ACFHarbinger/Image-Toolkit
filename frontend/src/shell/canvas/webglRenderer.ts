/**
 * WebGL2 / WebGPU tile-quad and seam/ROI vector-overlay renderer for the
 * shared canvas host spike (S-02 / #888).
 */

import { ResolvedTile } from "./cullWorker";
import type { TileTextureSource } from "./tileTextureCache";
import {
  CanvasBlendMode,
  CanvasPoint,
  CanvasRect,
  clampZoom,
  ViewportTransform,
} from "./pyramid";

export type CanvasRendererBackend = "webgpu" | "webgl2" | "headless";

export interface QuadVertexBatch {
  /** Interleaved `[x_ndc, y_ndc, u, v]` for 6 vertices (2 triangles) per quad. */
  vertices: Float32Array;
  quadCount: number;
}

export interface OverlayVertexBatch {
  /** Interleaved `[x_ndc, y_ndc]` line-strip / loop vertices. */
  seamVertices: Float32Array;
  roiVertices: Float32Array;
}

export interface RenderFrameCommand {
  viewport: ViewportTransform;
  tiles: ResolvedTile[];
  layerOpacities: Record<string, number>;
  blendMode: CanvasBlendMode;
  splitWipeRatio: number;
  seamPolygon: CanvasPoint[];
  roiBox: CanvasRect | null;
}

export interface RenderFrameStats {
  backend: CanvasRendererBackend;
  drawnTileCount: number;
  seamVertexCount: number;
  roiVertexCount: number;
  blendMode: CanvasBlendMode;
  splitWipeRatio: number;
  texturedTileCount: number;
}

export const TILE_VERTEX_SHADER_GLSL = `#version 300 es
precision highp float;
layout(location = 0) in vec2 a_position;
layout(location = 1) in vec2 a_texCoord;
out vec2 v_texCoord;
out vec2 v_ndcPos;
void main() {
  v_texCoord = a_texCoord;
  v_ndcPos = a_position;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

export const TILE_FRAGMENT_SHADER_GLSL = `#version 300 es
precision highp float;
in vec2 v_texCoord;
in vec2 v_ndcPos;
uniform sampler2D u_tileTexture;
uniform float u_opacity;
uniform int u_blendMode; // 0 = normal, 1 = difference, 2 = split-wipe
uniform float u_splitWipeNdcX;
uniform int u_layerIndex;
out vec4 outColor;
void main() {
  if (u_blendMode == 2 && u_layerIndex > 0 && v_ndcPos.x < u_splitWipeNdcX) {
    discard;
  }
  vec4 texel = texture(u_tileTexture, v_texCoord);
  outColor = vec4(texel.rgb, texel.a * u_opacity);
}
`;

/**
 * Converts a document-space point `(docX, docY)` into WebGL Normalized Device
 * Coordinates `[-1, 1]` (where `(-1, +1)` is top-left and `(+1, -1)` is
 * bottom-right).
 */
export function docToNdc(
  docX: number,
  docY: number,
  viewport: ViewportTransform,
): [number, number] {
  const z = clampZoom(viewport.zoom);
  const vw = Math.max(1, viewport.viewportWidth);
  const vh = Math.max(1, viewport.viewportHeight);
  const screenX = docX * z + viewport.panX;
  const screenY = docY * z + viewport.panY;
  const ndcX = (screenX / vw) * 2 - 1;
  const ndcY = 1 - (screenY / vh) * 2;
  return [ndcX, ndcY];
}

/**
 * Builds the 6-vertex (2-triangle) interleaved `[x_ndc, y_ndc, u, v]` buffer
 * for a list of visible tiles.
 */
export function buildTileQuadBatch(
  tiles: ResolvedTile[],
  viewport: ViewportTransform,
): QuadVertexBatch {
  const floatsPerQuad = 6 * 4;
  const vertices = new Float32Array(tiles.length * floatsPerQuad);

  for (let i = 0; i < tiles.length; i += 1) {
    const { x, y, width, height } = tiles[i].docRect;
    const [x0, y0] = docToNdc(x, y, viewport);
    const [x1, y1] = docToNdc(x + width, y + height, viewport);
    const base = i * floatsPerQuad;

    // Triangle 1: top-left, bottom-left, top-right
    vertices[base + 0] = x0;
    vertices[base + 1] = y0;
    vertices[base + 2] = 0;
    vertices[base + 3] = 0;

    vertices[base + 4] = x0;
    vertices[base + 5] = y1;
    vertices[base + 6] = 0;
    vertices[base + 7] = 1;

    vertices[base + 8] = x1;
    vertices[base + 9] = y0;
    vertices[base + 10] = 1;
    vertices[base + 11] = 0;

    // Triangle 2: top-right, bottom-left, bottom-right
    vertices[base + 12] = x1;
    vertices[base + 13] = y0;
    vertices[base + 14] = 1;
    vertices[base + 15] = 0;

    vertices[base + 16] = x0;
    vertices[base + 17] = y1;
    vertices[base + 18] = 0;
    vertices[base + 19] = 1;

    vertices[base + 20] = x1;
    vertices[base + 21] = y1;
    vertices[base + 22] = 1;
    vertices[base + 23] = 1;
  }

  return { vertices, quadCount: tiles.length };
}

/**
 * Builds NDC line-strip vertices for the interactive seam polygon and ROI box.
 */
export function buildOverlayBatch(
  seamPolygon: CanvasPoint[],
  roiBox: CanvasRect | null,
  viewport: ViewportTransform,
): OverlayVertexBatch {
  const seamVertices = new Float32Array(seamPolygon.length * 2);
  for (let i = 0; i < seamPolygon.length; i += 1) {
    const [nx, ny] = docToNdc(seamPolygon[i].x, seamPolygon[i].y, viewport);
    seamVertices[i * 2] = nx;
    seamVertices[i * 2 + 1] = ny;
  }

  if (!roiBox || roiBox.width <= 0 || roiBox.height <= 0) {
    return { seamVertices, roiVertices: new Float32Array(0) };
  }

  const corners: CanvasPoint[] = [
    { x: roiBox.x, y: roiBox.y },
    { x: roiBox.x + roiBox.width, y: roiBox.y },
    { x: roiBox.x + roiBox.width, y: roiBox.y + roiBox.height },
    { x: roiBox.x, y: roiBox.y + roiBox.height },
    { x: roiBox.x, y: roiBox.y },
  ];
  const roiVertices = new Float32Array(corners.length * 2);
  for (let i = 0; i < corners.length; i += 1) {
    const [nx, ny] = docToNdc(corners[i].x, corners[i].y, viewport);
    roiVertices[i * 2] = nx;
    roiVertices[i * 2 + 1] = ny;
  }

  return { seamVertices, roiVertices };
}

/**
 * Probes the canvas and environment for WebGPU / WebGL2 availability and
 * executes tile-quad + vector-overlay draws (with a deterministic headless
 * recording fallback when running in jsdom).
 */
export class SharedCanvasRenderer {
  private readonly canvas: HTMLCanvasElement;
  private readonly gl: WebGL2RenderingContext | null;
  readonly backend: CanvasRendererBackend;
  private program: WebGLProgram | null = null;
  private quadBuffer: WebGLBuffer | null = null;
  private lastStats: RenderFrameStats = {
    backend: "headless",
    drawnTileCount: 0,
    texturedTileCount: 0,
    seamVertexCount: 0,
    roiVertexCount: 0,
    blendMode: "normal",
    splitWipeRatio: 0.5,
  };
  private readonly tileTextures = new Map<string, WebGLTexture>();
  /** URL set regardless of backend so stats reflect the JS texture pipeline. */
  private readonly uploadedUrls = new Set<string>();
  private placeholderTexture: WebGLTexture | null = null;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    let glContext: WebGL2RenderingContext | null = null;
    const isUnpatchedJsdom =
      typeof navigator !== "undefined" &&
      typeof navigator.userAgent === "string" &&
      navigator.userAgent.toLowerCase().includes("jsdom") &&
      typeof HTMLCanvasElement !== "undefined" &&
      canvas.getContext === HTMLCanvasElement.prototype.getContext;
    if (!isUnpatchedJsdom) {
      try {
        glContext = canvas.getContext("webgl2") as WebGL2RenderingContext | null;
      } catch {
        glContext = null;
      }
    }
    this.gl = glContext;

    const hasWebGpu =
      typeof navigator !== "undefined" && "gpu" in navigator && Boolean((navigator as { gpu?: unknown }).gpu);
    if (this.gl) {
      this.backend = "webgl2";
      this.initWebGL2(this.gl);
    } else if (hasWebGpu) {
      this.backend = "webgpu";
    } else {
      this.backend = "headless";
    }
    this.lastStats.backend = this.backend;
  }

  private initWebGL2(gl: WebGL2RenderingContext): void {
    const vs = gl.createShader(gl.VERTEX_SHADER);
    const fs = gl.createShader(gl.FRAGMENT_SHADER);
    if (!vs || !fs) {
      return;
    }
    gl.shaderSource(vs, TILE_VERTEX_SHADER_GLSL);
    gl.compileShader(vs);
    gl.shaderSource(fs, TILE_FRAGMENT_SHADER_GLSL);
    gl.compileShader(fs);

    const prog = gl.createProgram();
    if (!prog) {
      return;
    }
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    this.program = prog;
    this.quadBuffer = gl.createBuffer();
    this.placeholderTexture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.placeholderTexture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([31, 41, 55, 255]));
  }

  /** Upload one decoded tile source as a GL texture (NPOT-safe). */
  uploadTileTexture(url: string, source: TileTextureSource): boolean {
    this.uploadedUrls.add(url);
    const gl = this.gl;
    if (!gl) {
      return true; // headless: the JS pipeline recorded the upload
    }
    const texture = gl.createTexture();
    if (!texture) {
      return false;
    }
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 0);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source as TexImageSource);
    const existing = this.tileTextures.get(url);
    if (existing) {
      gl.deleteTexture(existing);
    }
    this.tileTextures.set(url, texture);
    return true;
  }

  /** Free one tile's GL texture (the JS cache entry already left). */
  evictTileTexture(url: string): void {
    const gl = this.gl;
    const texture = this.tileTextures.get(url);
    if (gl && texture) {
      gl.deleteTexture(texture);
    }
    this.tileTextures.delete(url);
    this.uploadedUrls.delete(url);
  }

  /** True when a tile's texture is uploaded (placeholder not needed). */
  hasTileTexture(url: string): boolean {
    return this.uploadedUrls.has(url);
  }

  renderFrame(command: RenderFrameCommand): RenderFrameStats {
    const clampedWipe = Math.min(1, Math.max(0, command.splitWipeRatio));
    const quadBatch = buildTileQuadBatch(command.tiles, command.viewport);
    const overlayBatch = buildOverlayBatch(
      command.seamPolygon,
      command.roiBox,
      command.viewport,
    );

    if (this.gl && this.program && this.quadBuffer) {
      const gl = this.gl;
      gl.viewport(
        0,
        0,
        Math.max(1, command.viewport.viewportWidth),
        Math.max(1, command.viewport.viewportHeight),
      );
      gl.clearColor(0.08, 0.09, 0.11, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(this.program);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, quadBatch.vertices, gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 16, 0);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 16, 8);

      // Per-tile draw so each quad binds its own texture; visible tiles
      // are frustum-culled to a handful, so per-tile uniforms stay cheap.
      const uTileTexture = gl.getUniformLocation(this.program, "u_tileTexture");
      const uOpacity = gl.getUniformLocation(this.program, "u_opacity");
      const uBlendMode = gl.getUniformLocation(this.program, "u_blendMode");
      const uSplitWipe = gl.getUniformLocation(this.program, "u_splitWipeNdcX");
      const uLayerIndex = gl.getUniformLocation(this.program, "u_layerIndex");
      const blendModeValue =
        command.blendMode === "difference" ? 1 : command.blendMode === "split-wipe" ? 2 : 0;
      const layerOrder = Object.keys(command.layerOpacities);
      const splitWipeNdcX = clampedWipe * 2 - 1;
      // Straight alpha from the fragment shader: src alpha, one-minus-src.
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      let texturedTileCount = 0;
      for (let i = 0; i < command.tiles.length; i += 1) {
        const tile = command.tiles[i];
        const texture = this.tileTextures.get(tile.assetUrl) ?? this.placeholderTexture;
        if (texture) {
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, texture);
          gl.uniform1i(uTileTexture, 0);
        }
        if (this.uploadedUrls.has(tile.assetUrl)) {
          texturedTileCount += 1;
        }
        gl.uniform1f(uOpacity, command.layerOpacities[tile.layerId] ?? 1);
        gl.uniform1i(uBlendMode, blendModeValue);
        gl.uniform1f(uSplitWipe, splitWipeNdcX);
        gl.uniform1i(uLayerIndex, Math.max(0, layerOrder.indexOf(tile.layerId)));
        gl.drawArrays(gl.TRIANGLES, i * 6, 6);
      }
      gl.disable(gl.BLEND);
    }

    this.lastStats = {
      backend: this.backend,
      drawnTileCount: quadBatch.quadCount,
      texturedTileCount: this.texturedDrawCount(command),
      seamVertexCount: overlayBatch.seamVertices.length / 2,
      roiVertexCount: overlayBatch.roiVertices.length / 2,
      blendMode: command.blendMode,
      splitWipeRatio: clampedWipe,
    };
    return this.lastStats;
  }

  getLastStats(): RenderFrameStats {
    return this.lastStats;
  }

  dispose(): void {
    if (this.gl) {
      if (this.quadBuffer) {
        this.gl.deleteBuffer(this.quadBuffer);
        this.quadBuffer = null;
      }
      if (this.program) {
        this.gl.deleteProgram(this.program);
        this.program = null;
      }
      for (const texture of this.tileTextures.values()) {
        this.gl.deleteTexture(texture);
      }
      this.tileTextures.clear();
      this.uploadedUrls.clear();
      if (this.placeholderTexture) {
        this.gl.deleteTexture(this.placeholderTexture);
        this.placeholderTexture = null;
      }
    }
  }

  private texturedDrawCount(command: RenderFrameCommand): number {
    let texturedTileCount = 0;
    for (const tile of command.tiles) {
      if (this.uploadedUrls.has(tile.assetUrl)) {
        texturedTileCount += 1;
      }
    }
    return texturedTileCount;
  }
}
