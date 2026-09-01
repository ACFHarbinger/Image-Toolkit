import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import ToggleButtonGroup from "../../../frontend/src/components/common/ToggleButtonGroup";

const meta: Meta<typeof ToggleButtonGroup> = {
  title: "frontend/common/ToggleButtonGroup",
  component: ToggleButtonGroup,
};
export default meta;

type Story = StoryObj<typeof ToggleButtonGroup>;

function OutputFormatsControl() {
  const [selected, setSelected] = useState<Set<string>>(new Set(["png", "webp"]));
  return (
    <ToggleButtonGroup
      items={["png", "webp", "jpg", "avif"]}
      selectedItems={selected}
      onToggle={(item) => setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(item)) next.delete(item);
        else next.add(item);
        return next;
      })}
    />
  );
}

export const OutputFormats: Story = {
  render: () => <OutputFormatsControl />,
};
