import React, { useState } from "react";
import { FormRow, PathInput } from "../Shared.tsx";

const BASE_MODELS = [
  "models/sd3.5_large.safetensors",
  "models/sd3.5_large_turbo.safetensors",
  "models/sd3.5_medium.safetensors",
  "models/sd3_medium.safetensors",
];

const CN_MODELS = [
  "None",
  "models/sd3.5_large_controlnet_blur.safetensors",
  "models/sd3.5_large_controlnet_canny.safetensors",
  "models/sd3.5_large_controlnet_depth.safetensors",
];

export const SD3GenerateTab: React.FC = () => {
  const [model, setModel] = useState(BASE_MODELS[0]);
  const [prompt, setPrompt] = useState("cute wallpaper art of a cat");
  const [postfix, setPostfix] = useState("");

  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [steps, setSteps] = useState(28);
  const [skipLayerCfg, setSkipLayerCfg] = useState(false);

  const [cnModel, setCnModel] = useState(CN_MODELS[0]);
  const [cnImage, setCnImage] = useState("inputs/canny.png");

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200 space-y-4">
      <FormRow label="Base Model:">
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        >
          {BASE_MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </FormRow>

      <FormRow label="Prompt:">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600 h-24"
        />
      </FormRow>

      <FormRow label="Output Postfix (opt.):">
        <input
          type="text"
          value={postfix}
          onChange={(e) => setPostfix(e.target.value)}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </FormRow>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <FormRow label="Width:">
          <input
            type="number"
            value={width}
            onChange={(e) => setWidth(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={256}
            max={4096}
          />
        </FormRow>
        <FormRow label="Height:">
          <input
            type="number"
            value={height}
            onChange={(e) => setHeight(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={256}
            max={4096}
          />
        </FormRow>
        <FormRow label="Steps:">
          <input
            type="number"
            value={steps}
            onChange={(e) => setSteps(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={1}
            max={200}
          />
        </FormRow>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <input
          type="checkbox"
          checked={skipLayerCfg}
          onChange={(e) => setSkipLayerCfg(e.target.checked)}
          className="w-4 h-4"
        />
        <span className="font-medium">
          Skip Layer Cfg (Recommended for SD3.5-M)
        </span>
      </div>

      <div className="border-t dark:border-gray-700 pt-4">
        <h4 className="font-bold mb-3">ControlNet Configuration</h4>
        <FormRow label="ControlNet Model:">
          <select
            value={cnModel}
            onChange={(e) => setCnModel(e.target.value)}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          >
            {CN_MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </FormRow>

        {cnModel !== "None" && (
          <FormRow label="Condition Image:">
            <PathInput value={cnImage} onChange={setCnImage} type="file" />
          </FormRow>
        )}
      </div>

      <div className="flex gap-2 pt-4">
        <button className="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700 font-bold">
          Generate SD3.5 Image
        </button>
      </div>
    </div>
  );
};
