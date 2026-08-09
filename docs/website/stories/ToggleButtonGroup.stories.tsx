import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import ToggleButtonGroup from "../../../frontend/src/components/common/ToggleButtonGroup";

const meta: Meta<typeof ToggleButtonGroup> = {
  title: "frontend/common/ToggleButtonGroup",
  component: ToggleButtonGroup,
};
export default meta;

type Story = StoryObj<typeof ToggleButtonGroup>;

export const OutputFormats: Story = {
  render: () => {
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Storybook render function, not a component
    const [selected, setSelected] = useState<Set<string>>(new Set(["png", "webp"]));
    return (
      <ToggleButtonGroup
        items={["png", "webp", "jpg", "avif"]}
        selectedItems={selected}
        onToggle={(item) =>
          setSelected((prev) => {
            const next = new Set(prev);
            next.has(item) ? next.delete(item) : next.add(item);
            return next;
          })
        }
      />
    );
  },
};
