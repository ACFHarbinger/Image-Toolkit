import React, { useState } from "react";
import { FormRow, PathInput } from "../Shared.tsx";

const MODELS = [
  {
    name: "Illustrious XL V2.0",
    id: "stabilityai/stable-diffusion-xl-base-1.0",
  },
  { name: "AnimeGANv2", id: "animegan_v2" },
];

export const LoRAGenerateTab: React.FC = () => {
  const [modelId, setModelId] = useState(MODELS[0].id);

  // Diffusion Params
  const [prompt, setPrompt] = useState("1girl, solo, cat ears, library");
  const [negPrompt, setNegPrompt] = useState(
    "lowres, bad anatomy, text, error",
  );
  const [loraPath, setLoraPath] = useState("output_lora");
  const [steps, setSteps] = useState(25);
  const [guidance, setGuidance] = useState(7.0);

  // GAN Params
  const [inputImage, setInputImage] = useState("");

  const isGan = modelId === "animegan_v2";

  return (
    // Updated background and text color for the main card
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200">
      <FormRow label="Select Model:">
        <select
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          // Updated select styling for dark mode
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </FormRow>

      {/* Dynamic Widgets Group */}
      {!isGan ? (
        <div className="space-y-2 border-l-4 border-blue-500 pl-4 my-4">
          <FormRow label="Prompt:">
            {/* Updated input styling for dark mode */}
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            />
          </FormRow>
          <FormRow label="Negative Prompt:">
            <input
              type="text"
              value={negPrompt}
              onChange={(e) => setNegPrompt(e.target.value)}
              className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            />
          </FormRow>
          <FormRow label="LoRA Path:">
            <input
              type="text"
              value={loraPath}
              onChange={(e) => setLoraPath(e.target.value)}
              className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            />
          </FormRow>
          <div className="grid grid-cols-2 gap-4">
            <FormRow label="Steps:">
              <input
                type="number"
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
                className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </FormRow>
            <FormRow label="Guidance:">
              <input
                type="number"
                value={guidance}
                onChange={(e) => setGuidance(Number(e.target.value))}
                className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
                step={0.1}
              />
            </FormRow>
          </div>
        </div>
      ) : (
        <div className="space-y-2 border-l-4 border-purple-500 pl-4 my-4">
          <FormRow label="Input Image:">
            <PathInput
              value={inputImage}
              onChange={setInputImage}
              type="file"
              placeholder="Select image for style transfer"
            />
          </FormRow>
        </div>
      )}

      {/* Added border-gray-600 for dark mode divider */}
      <div className="border-t border-gray-200 dark:border-gray-600 pt-4 mt-4">
        <FormRow label="Output Filename:">
          <input
            type="text"
            defaultValue="Generated/output.png"
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </FormRow>
        <FormRow label="Batch Size:">
          <input
            type="number"
            defaultValue={1}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            max={8}
          />
        </FormRow>
      </div>

      <div className="flex gap-2 mt-4">
        <button className="flex-1 bg-purple-600 text-white py-2 rounded hover:bg-purple-700">
          {isGan ? "Transfer Style" : "Generate Image"}
        </button>
        {/* Updated disabled button style for dark mode */}
        <button
          disabled
          className="flex-1 bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 py-2 rounded"
        >
          Cancel
        </button>
      </div>
    </div>
  );
};
