import type { StorybookConfig } from "@storybook/react-vite";

// Documents Image-Toolkit's real, reusable React components
// (frontend/src/components/common/*) in isolation — the same components
// src/frameworks/react/ComponentGallery.tsx mounts live in the docs site's
// "Framework Islands" hub panel. Built standalone into public/storybook/
// (see package.json's build-storybook / postbuild-equivalent prebuild step)
// and linked from the site, rather than embedded as an island itself.
const config: StorybookConfig = {
  stories: ["../stories/**/*.stories.@(ts|tsx)"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  addons: ["@storybook/addon-docs", "@storybook/addon-a11y"],
  viteFinal: async (viteConfig) => {
    viteConfig.base = process.env.SITE_BASE ? `${process.env.SITE_BASE}storybook/` : "/storybook/";
    return viteConfig;
  },
};

export default config;
