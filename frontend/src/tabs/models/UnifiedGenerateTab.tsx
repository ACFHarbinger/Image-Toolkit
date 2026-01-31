import React, { useState } from "react";
import { GANGenerateTab } from "./gen/GANGenerateTab";
import { LoRAGenerateTab } from "./gen/LoRAGenerateTab";
import { SD3GenerateTab } from "./gen/SD3GenerateTab";
import { R3GANGenerateTab } from "./gen/R3GANGenerateTab";

export const UnifiedGenerateTab: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState("anything");

  return (
    <div className="max-w-4xl mx-auto p-4">
      <div className="mb-6 flex items-center gap-4 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <label className="font-bold whitespace-nowrap text-gray-800 dark:text-gray-100">
          Model Architecture:
        </label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="flex-1 p-2 border rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:ring-2 focus:ring-blue-500"
        >
          <option value="anything">LoRA (Diffusion and GANs)</option>
          <option value="sd3">Stable Diffusion 3.5</option>
          <option value="r3gan">R3GAN (NVLabs)</option>
          <option value="basic_gan">Basic GAN (Custom)</option>
        </select>
      </div>

      <div className="transition-opacity duration-300">
        {selectedModel === "anything" && <LoRAGenerateTab />}
        {selectedModel === "sd3" && <SD3GenerateTab />}
        {selectedModel === "r3gan" && <R3GANGenerateTab />}
        {selectedModel === "basic_gan" && <GANGenerateTab />}
      </div>
    </div>
  );
};
