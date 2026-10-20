// EventHub (#878) — the webview's in-app event bus, generated from the
// contracts' channel declarations (Kimi Q3 answer: snapshot + bounded tail,
// sequence numbers, resnapshot on gap; Cursor W2 answer: sidecar emits
// intents/facts, appStore.ts stays ephemeral UI state).
//
// The hub is transport-agnostic: frames arrive through ingest() (wired to
// #875's transport via transport.ts) and snapshots through a SnapshotProvider
// (jobs.list over the bridge client, wired by #876). There is deliberately
// no RPC envelope here — requests ride the shared bridge package.

import type { BridgeEvent } from "../../../contracts/generated/ts/event";
import { ChannelBuffer, type AppendOutcome } from "./buffer";
import { guardEvent } from "./envelope";
import { CHANNEL_NAMES, CHANNEL_REGISTRY, type ChannelName } from "./generated/channels";
import { REDUCERS, type ChannelStates } from "./reducers";

export interface ChannelSnapshot {
  /** sequence number the snapshot was taken at (0 = empty) */
  readonly seq: number;
  readonly snapshot: unknown;
}

export interface SnapshotProvider {
  fetch(channel: ChannelName): Promise<ChannelSnapshot>;
}

export interface IngestResult {
  readonly ok: boolean;
  readonly channel?: ChannelName;
  readonly outcome?: AppendOutcome;
  readonly reason?: string;
}

export interface HubOptions {
  readonly provider: SnapshotProvider;
  readonly tailMax?: number;
  readonly pendingMax?: number;
  /** Called when a sequence gap forces a resnapshot. */
  readonly onGap?: (channel: ChannelName, info: { expected: number; got: number }) => void;
  /** Called when the snapshot provider rejects or fails. */
  readonly onProviderError?: (channel: ChannelName, error: unknown) => void;
}

export class EventHub {
  private readonly buffers = new Map<ChannelName, ChannelBuffer<ChannelStates[ChannelName]>>();
  private readonly listeners = new Map<ChannelName, Set<(state: never) => void>>();
  private readonly knownChannels = new Set<string>(CHANNEL_NAMES);
  private readonly provider: SnapshotProvider;
  private readonly onGap?: HubOptions["onGap"];
  private readonly onProviderError?: HubOptions["onProviderError"];
  private readonly tailMax?: number;
  private readonly pendingMax?: number;
  private resnapshotInFlight = new Set<ChannelName>();

  constructor(options: HubOptions) {
    this.provider = options.provider;
    this.onGap = options.onGap;
    this.onProviderError = options.onProviderError;
    this.tailMax = options.tailMax;
    this.pendingMax = options.pendingMax;
  }

  /** Validate a wire frame and fold it into its channel. */
  ingest(frame: unknown): IngestResult {
    const guarded = guardEvent(frame, this.knownChannels);
    if (!guarded.ok) {
      return { ok: false, reason: guarded.reason };
    }
    const event = guarded.event;
    const channel = event.channel as ChannelName;
    const buffer = this.bufferFor(channel);
    const outcome = buffer.append(event);
    if (outcome.status === "gap") {
      this.onGap?.(channel, { expected: outcome.expected, got: outcome.got });
      buffer.beginCatchUp();
      void this.resnapshot(channel);
    } else if (outcome.status === "appended") {
      this.emit(channel);
    }
    return { ok: true, channel, outcome };
  }

  getState<C extends ChannelName>(channel: C): ChannelStates[C] | undefined {
    return this.bufferFor(channel).state;
  }

  getTail(channel: ChannelName): readonly BridgeEvent[] {
    return this.bufferFor(channel).tail();
  }

  lastSeq(channel: ChannelName): number {
    return this.bufferFor(channel).lastSeq;
  }

  isCatchingUp(channel: ChannelName): boolean {
    return this.bufferFor(channel).catchingUp;
  }

  /**
   * Subscribe to a channel's snapshot state. A late joiner with no state yet
   * triggers a resnapshot and receives the install when it lands.
   */
  subscribe<C extends ChannelName>(channel: C, listener: (state: ChannelStates[C]) => void): () => void {
    let set = this.listeners.get(channel);
    if (!set) {
      set = new Set();
      this.listeners.set(channel, set);
    }
    set.add(listener as (state: never) => void);
    const state = this.getState(channel);
    if (state !== undefined) {
      listener(state);
    } else if (!this.resnapshotInFlight.has(channel)) {
      void this.resnapshot(channel);
    }
    return () => {
      set.delete(listener as (state: never) => void);
    };
  }

  /** Fetch and install a provider snapshot, then replay queued events. */
  async resnapshot(channel: ChannelName): Promise<boolean> {
    if (this.resnapshotInFlight.has(channel)) {
      return false;
    }
    this.resnapshotInFlight.add(channel);
    const buffer = this.bufferFor(channel);
    buffer.beginCatchUp();
    let previousSeq: number | undefined;
    try {
      for (;;) {
        const shot = await this.provider.fetch(channel);
        const result = buffer.installSnapshot(shot.seq, shot.snapshot as ChannelStates[ChannelName]);
        if (result.gapAt === undefined) {
          this.emit(channel);
          return true;
        }
        // The queued events hid another hole; fetch again. Bail out if the
        // provider stops advancing — the same snapshot seq can never cover
        // a larger queue, so retrying would livelock.
        if (previousSeq !== undefined && shot.seq <= previousSeq) {
          throw new Error(
            `snapshot for channel ${channel} did not advance (seq ${shot.seq}); cannot cover gap`,
          );
        }
        previousSeq = shot.seq;
        this.onGap?.(channel, result.gapAt);
      }
    } catch (error) {
      this.onProviderError?.(channel, error);
      return false;
    } finally {
      this.resnapshotInFlight.delete(channel);
    }
  }

  private bufferFor<C extends ChannelName>(channel: C): ChannelBuffer<ChannelStates[C]> {
    let buffer = this.buffers.get(channel) as ChannelBuffer<ChannelStates[C]> | undefined;
    if (!buffer) {
      buffer = new ChannelBuffer<ChannelStates[C]>({
        tailMax: this.tailMax,
        pendingMax: this.pendingMax,
        reducer: REDUCERS[channel],
      });
      this.buffers.set(channel, buffer as ChannelBuffer<ChannelStates[ChannelName]>);
    }
    return buffer;
  }

  private emit(channel: ChannelName): void {
    const set = this.listeners.get(channel);
    if (!set) {
      return;
    }
    const state = this.bufferFor(channel).state;
    if (state === undefined) {
      return;
    }
    for (const listener of set) {
      listener(state as never);
    }
  }
}

export { CHANNEL_NAMES, CHANNEL_REGISTRY };
export type { ChannelName } from "./generated/channels";
export type { BridgeEvent } from "../../../contracts/generated/ts/event";
