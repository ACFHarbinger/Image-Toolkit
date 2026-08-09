import { createApp } from "vue";
import App from "./frameworks/vue/App.vue";
import router from "./router";
import { directivesPlugin } from "./frameworks/vue/directives";
import { VuexProvider } from "./libraries/vuex/store/VuexProvider";
import "./styles/theme.css";
import "./styles/markdown.css";
import "./styles/hub.css";

const app = createApp(App);
app.use(router);
app.use(directivesPlugin);
app.use(VuexProvider);
app.mount("#app");
