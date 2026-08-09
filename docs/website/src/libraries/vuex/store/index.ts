import { createStore } from "vuex";
import { initialAppState, type AppState } from "../state/appState";
import { mutations } from "../mutations/appMutations";
import { actions } from "../actions/appActions";
import { readPersistedHubTab } from "../services/persistence";

export const store = createStore<AppState>({
  state: {
    ...initialAppState,
    activeHubTab: readPersistedHubTab(initialAppState.activeHubTab),
  },
  mutations,
  actions,
});

export type { AppState };
