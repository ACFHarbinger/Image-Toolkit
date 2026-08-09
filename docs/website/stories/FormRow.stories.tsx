import type { Meta, StoryObj } from "@storybook/react-vite";
import FormRow from "../../../frontend/src/components/common/FormRow";

const meta: Meta<typeof FormRow> = {
  title: "frontend/common/FormRow",
  component: FormRow,
};
export default meta;

type Story = StoryObj<typeof FormRow>;

export const WithTextInput: Story = {
  args: { label: "Output format", children: <input defaultValue="png" /> },
};
