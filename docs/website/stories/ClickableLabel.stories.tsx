import type { Meta, StoryObj } from "@storybook/react-vite";
import { ClickableLabel } from "../../../frontend/src/components/common/ClickableLabel";

const meta: Meta<typeof ClickableLabel> = {
  title: "frontend/common/ClickableLabel",
  component: ClickableLabel,
};
export default meta;

type Story = StoryObj<typeof ClickableLabel>;

export const FilenameFallback: Story = {
  args: { path: "wallpaper_001.webp", isSelected: false },
};

export const Selected: Story = {
  args: { path: "wallpaper_001.webp", isSelected: true },
};
