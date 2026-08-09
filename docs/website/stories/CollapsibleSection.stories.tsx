import type { Meta, StoryObj } from "@storybook/react-vite";
import CollapsibleSection from "../../../frontend/src/components/common/CollapsibleSection";

const meta: Meta<typeof CollapsibleSection> = {
  title: "frontend/common/CollapsibleSection",
  component: CollapsibleSection,
};
export default meta;

type Story = StoryObj<typeof CollapsibleSection>;

export const Closed: Story = {
  args: { title: "Advanced options", children: <p>Hidden until expanded.</p> },
};

export const OpenByDefault: Story = {
  args: { title: "convert --output_format", startOpen: true, children: <p>Visible immediately.</p> },
};
