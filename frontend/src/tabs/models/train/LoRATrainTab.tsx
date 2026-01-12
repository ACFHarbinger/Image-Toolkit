import React, { useState } from "react";
import { FormRow, PathInput, SectionHeader } from "../Shared.tsx";

const MODELS = [
  {
    name: "Illustrious XL V2.0",
    id: "stabilityai/stable-diffusion-xl-base-1.0",
  },
  { name: "Anything V5", id: "stablediffusionapi/anything-v5" },
  { name: "AnimeGANv2", id: "animegan_v2" },
  // ... others
];

export const LoRATrainTab: React.FC = () => {
  const [modelId, setModelId] = useState(MODELS[0].id);
  const [datasetFolder, setDatasetFolder] = useState("");
  const [outputName, setOutputName] = useState("my_model");

  // LoRA specific
  const [triggerPrompt, setTriggerPrompt] = useState("1girl, style of my_char");
  const [rank, setRank] = useState(4);

  // Common
  const [epochs, setEpochs] = useState(5);
  const [batchSize, setBatchSize] = useState(1);
  const [lr, setLr] = useState(0.0001);

  const isGan = modelId === "animegan_v2";

  return (
    // Updated background and text color for the main card
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow space-y-4 text-gray-800 dark:text-gray-200">
      <FormRow label="Base Model:">
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

      <FormRow label="Dataset Folder:">
        <PathInput value={datasetFolder} onChange={setDatasetFolder} />
      </FormRow>

      <FormRow label="Output Name:">
        <input
          type="text"
          value={outputName}
          onChange={(e) => setOutputName(e.target.value)}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </FormRow>

      {/* Conditional visibility based on model selection */}
      {!isGan && (
        // Updated inner container for dark mode
        <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded border dark:border-gray-600">
          <h4 className="font-bold mb-2 text-sm text-gray-500 dark:text-gray-400 uppercase">
            LoRA Configuration
          </h4>
          <FormRow label="Trigger Word:">
            <input
              type="text"
              value={triggerPrompt}
              onChange={(e) => setTriggerPrompt(e.target.value)}
              className="w-full border p-2 rounded dark:bg-gray-600 dark:border-gray-500"
            />
          </FormRow>
          <FormRow label="LoRA Rank:">
            <input
              type="number"
              value={rank}
              onChange={(e) => setRank(Number(e.target.value))}
              className="w-full border p-2 rounded dark:bg-gray-600 dark:border-gray-500"
            />
          </FormRow>
        </div>
      )}

      <SectionHeader title="Training Parameters" />
      <FormRow label="Epochs:">
        <input
          type="number"
          value={epochs}
          onChange={(e) => setEpochs(Number(e.target.value))}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </FormRow>
      <FormRow label="Batch Size:">
        <input
          type="number"
          value={batchSize}
          onChange={(e) => setBatchSize(Number(e.target.value))}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </FormRow>
      <FormRow label="Learning Rate:">
        <input
          type="number"
          value={lr}
          onChange={(e) => setLr(Number(e.target.value))}
          step={0.000001}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </FormRow>

      <div className="flex gap-2 pt-4">
        <button className="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
          Start Training
        </button>
        {/* Updated disabled button style for dark mode */}
        <button
          disabled
          className="flex-1 bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 py-2 rounded cursor-not-allowed"
        >
          Cancel
        </button>
      </div>
      <div className="text-center text-sm text-gray-500 dark:text-gray-400 mt-2">
        Ready
      </div>
    </div>
  );
};
