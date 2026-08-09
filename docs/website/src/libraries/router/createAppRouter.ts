import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

export function createAppRouter(options: { routes: RouteRecordRaw[] }) {
  const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: options.routes,
    scrollBehavior(to, _from, savedPosition) {
      if (savedPosition) return savedPosition;
      if (to.hash) return { el: to.hash, behavior: "smooth", top: 88 };
      return { top: 0 };
    },
  });
  return router;
}
