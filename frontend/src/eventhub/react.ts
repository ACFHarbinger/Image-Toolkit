// React binding for the EventHub. Domain state lives in the hub; components
// subscribe to channel snapshots through this hook, which is what keeps
// appStore.ts limited to ephemeral UI state (Cursor W2 answer).

import { useSyncExternalStore } from "react";
import type { EventHub } from "./hub";
import type { ChannelName } from "./generated/channels";
import type { ChannelStates } from "./reducers";

export function useChannelState<C extends ChannelName>(
  hub: EventHub,
  channel: C,
): ChannelStates[C] | undefined {
  return useSyncExternalStore(
    (notify) => hub.subscribe(channel, notify),
    () => hub.getState(channel),
  );
}
