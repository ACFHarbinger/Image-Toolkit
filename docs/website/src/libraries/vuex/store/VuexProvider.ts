import type { App } from "vue";
import { store } from "./index";

/** Installs the Vuex store on the root app (`app.use(VuexProvider)`). */
export const VuexProvider = {
  install(app: App) {
    app.use(store);
  },
};
