import type { App } from "vue";
import { clickOutside } from "./clickOutside";
import { focus } from "./focus";
import { intersect } from "./intersect";

export const directivesPlugin = {
  install(app: App) {
    app.directive("click-outside", clickOutside);
    app.directive("focus", focus);
    app.directive("intersect", intersect);
  },
};
