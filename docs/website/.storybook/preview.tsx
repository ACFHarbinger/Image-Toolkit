import type { Preview } from "@storybook/react-vite";
import "../src/styles/tailwind.css";

const preview: Preview = {
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    backgrounds: {
      default: "light",
      values: [
        { name: "light", value: "#ffffff" },
        { name: "dark", value: "#0e0f13" },
      ],
    },
  },
};

export default preview;
