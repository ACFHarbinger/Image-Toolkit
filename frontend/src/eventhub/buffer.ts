// EventHub per-channel buffer (#878; Kimi Q3 answer: snapshot + bounded tail
// per channel, sequence numbers, resnapshot on gap).
//
// Pure data structure — no timers, no I/O. The hub owns side effects
// (snapshot providers, subscriptions); this class owns the ordering
// contract:
//
// - Every applied event has seq === lastSeq + 1. Anything older is stale
//   (a duplicate or a pre-snapshot leftover) and is dropped. Anything newer
//   is a gap: the caller resnapshots.
// - While a resnapshot is in flight, events queue (bounded) instead of being
//   applied, so post-gap events never fold onto pre-gap state. On install
//   the queue replays in order; events the snapshot already covers drop, and
//   a second hole re-triggers catch-up.
// - The tail retains only durable events, bounded to tailMax; older durable
//   events are already folded into the state and can be replayed from
//   job_events / events.jsonl when the window is not enough.

import type { BridgeEvent } from "../../../contracts/generated/ts/event";

export const DEFAULT_TAIL_MAX = 256;
export const DEFAULT_PENDING_MAX = 512;

export type AppendOutcome =
  | { readonly status: "appended"; readonly event: BridgeEvent }
  | { readonly status: "stale"; readonly seq: number; readonly lastSeq: number }
  | { readonly status: "queued"; readonly seq: number }
  | { readonly status: "gap"; readonly expected: number; readonly got: number };

export interface InstallResult {
  /** durable events folded from the pending queue after the snapshot landed */
  readonly replayed: number;
  /** set when the queue hid another hole and catch-up must restart */
  readonly gapAt?: { readonly expected: number; readonly got: number };
}

export interface ChannelBufferOptions<S> {
  readonly tailMax?: number;
  readonly pendingMax?: number;
  readonly reducer: (state: S | undefined, event: BridgeEvent) => S;
}

export class ChannelBuffer<S> {
  private stateValue: S | undefined;
  private lastSeqValue = 0;
  private tailEvents: BridgeEvent[] = [];
  private pending: BridgeEvent[] = [];
  private catchUp = false;
  private readonly tailMax: number;
  private readonly pendingMax: number;
  private readonly reducer: (state: S | undefined, event: BridgeEvent) => S;

  constructor(options: ChannelBufferOptions<S>) {
    this.tailMax = options.tailMax ?? DEFAULT_TAIL_MAX;
    this.pendingMax = options.pendingMax ?? DEFAULT_PENDING_MAX;
    this.reducer = options.reducer;
  }

  get state(): S | undefined {
    return this.stateValue;
  }

  get lastSeq(): number {
    return this.lastSeqValue;
  }

  get catchingUp(): boolean {
    return this.catchUp;
  }

  /** Durable events retained for catch-up, oldest first. */
  tail(): readonly BridgeEvent[] {
    return this.tailEvents;
  }

  /** Queue incoming events; a resnapshot is being fetched. */
  beginCatchUp(): void {
    this.catchUp = true;
    this.pending = [];
  }

  append(event: BridgeEvent): AppendOutcome {
    if (this.catchUp) {
      if (this.pending.length >= this.pendingMax) {
        this.pending.shift();
      }
      this.pending.push(event);
      return { status: "queued", seq: event.seq };
    }
    const expected = this.lastSeqValue + 1;
    if (event.seq <= this.lastSeqValue) {
      return { status: "stale", seq: event.seq, lastSeq: this.lastSeqValue };
    }
    if (event.seq > expected) {
      return { status: "gap", expected, got: event.seq };
    }
    this.apply(event);
    return { status: "appended", event };
  }

  /**
   * Install a provider snapshot. `seq` is the sequence number the snapshot
   * was taken at (0 = empty); queued events beyond it replay in order.
   */
  installSnapshot(seq: number, snapshot: S): InstallResult {
    this.stateValue = snapshot;
    this.lastSeqValue = seq;
    this.tailEvents = [];
    this.catchUp = false;
    let replayed = 0;
    let gapAt: { expected: number; got: number } | undefined;
    const queue = [...this.pending].sort((left, right) => left.seq - right.seq);
    this.pending = [];
    for (const event of queue) {
      if (event.seq <= this.lastSeqValue) {
        continue; // already covered by the snapshot
      }
      if (event.seq > this.lastSeqValue + 1) {
        gapAt = { expected: this.lastSeqValue + 1, got: event.seq };
        this.beginCatchUp();
        // Keep the unapplied remainder so the next install can replay it.
        this.pending = queue.slice(queue.indexOf(event));
        break;
      }
      this.apply(event);
      replayed += 1;
    }
    return { replayed, gapAt };
  }

  private apply(event: BridgeEvent): void {
    this.stateValue = this.reducer(this.stateValue, event);
    this.lastSeqValue = event.seq;
    if (event.durable) {
      this.tailEvents.push(event);
      if (this.tailEvents.length > this.tailMax) {
        this.tailEvents.shift();
      }
    }
  }
}
