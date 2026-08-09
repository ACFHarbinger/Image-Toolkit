import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import Modal from "../../../frontend/src/components/common/Modal";

const meta: Meta<typeof Modal> = {
  title: "frontend/common/Modal",
  component: Modal,
  argTypes: {
    type: { control: "select", options: ["success", "error", "info", "custom"] },
  },
};
export default meta;

type Story = StoryObj<typeof Modal>;

export const Success: Story = {
  args: { isVisible: true, type: "success", content: "Conversion queued for: png, webp", onClose: () => {} },
};

export const ErrorState: Story = {
  args: { isVisible: true, type: "error", content: "Failed to write output — disk full.", onClose: () => {} },
};

export const Interactive: Story = {
  render: () => {
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Storybook render function, not a component
    const [open, setOpen] = useState(true);
    return (
      <Modal
        isVisible={open}
        type="info"
        content="Click the backdrop's Close button to dismiss."
        onClose={() => setOpen(false)}
      />
    );
  },
};
