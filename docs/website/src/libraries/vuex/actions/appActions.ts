import type { ActionTree } from "vuex";
import type { AppState } from "../state/appState";
import { MutationType } from "../mutations/appMutations";
import { ActionType } from "./actionTypes";
import { persistHubTab } from "../services/persistence";

export const actions: ActionTree<AppState, AppState> = {
  [ActionType.SelectHubTab]({ commit }, tabId: string) {
    commit(MutationType.SetActiveHubTab, tabId);
    persistHubTab(tabId);
  },
  [ActionType.ToggleSidebar]({ commit, state }) {
    commit(MutationType.SetSidebarCollapsed, !state.sidebarCollapsed);
  },
};
