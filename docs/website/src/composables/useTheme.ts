import { ref, watchEffect } from "vue";

type Theme = "light" | "dark";

const stored = typeof localStorage !== "undefined" ? (localStorage.getItem("theme") as Theme | null) : null;
const prefersDark =
  typeof matchMedia !== "undefined" ? matchMedia("(prefers-color-scheme: dark)").matches : false;

const theme = ref<Theme>(stored ?? (prefersDark ? "dark" : "light"));

watchEffect(() => {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme.value);
  localStorage.setItem("theme", theme.value);
});

export function useTheme() {
  const toggle = () => {
    theme.value = theme.value === "dark" ? "light" : "dark";
  };
  return { theme, toggle };
}
