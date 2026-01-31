import React, { useState } from "react";
import { FormRow, PathInput } from "./Shared";

const MODELS = [
  "Meta CLIP 2 (ViT-H-14, Worldwide)",
  "Meta CLIP 2 (ViT-bigG-14, Worldwide)",
  "Meta CLIP 1 (ViT-G-14, 2.5B)",
  "Meta CLIP 1 (ViT-H-14, 2.5B)",
];

export const MetaCLIPInferenceTab: React.FC = () => {
  const [modelVersion, setModelVersion] = useState(MODELS[0]);
  const [imagePath, setImagePath] = useState("");
  const [textPrompts, setTextPrompts] = useState("a diagram\na dog\na cat");

  const handleRunInference = () => {
    console.log("Running MetaCLIP Inference:", {
      modelVersion,
      imagePath,
      textPrompts,
    });
    // Add API call logic here
  };

  return (
    <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 space-y-6">
      <div className="border-b dark:border-gray-700 pb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          Meta CLIP Zero-Shot Classification
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Classify images using state-of-the-art vision-language models.
        </p>
      </div>

      <FormRow label="Model Version:">
        <select
          value={modelVersion}
          onChange={(e) => setModelVersion(e.target.value)}
          className="w-full p-2 border rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-violet-500"
        >
          {MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </FormRow>

      <FormRow label="Image Path:">
        <PathInput
          value={imagePath}
          onChange={setImagePath}
          type="file"
          placeholder="Select image to classify"
        />
      </FormRow>

      <div className="flex flex-col gap-2">
        <label className="font-medium text-gray-700 dark:text-gray-300">
          Text Prompts (one per line):
        </label>
        <textarea
          value={textPrompts}
          onChange={(e) => setTextPrompts(e.target.value)}
          className="w-full h-32 p-3 border rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white font-mono text-sm focus:ring-2 focus:ring-violet-500"
          placeholder="Enter prompts here..."
        />
      </div>

      <div className="pt-4">
        <button
          onClick={handleRunInference}
          className="w-full py-3 bg-violet-600 text-white font-bold rounded-lg shadow hover:bg-violet-700 transition-colors flex items-center justify-center gap-2"
        >
          Run Classification
        </button>
      </div>
    </div>
  );
};
