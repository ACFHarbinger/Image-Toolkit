import React, { useState } from 'react';
import { GANGenerateTab } from './gen/GANGenerateTab.tsx';
import { LoRAGenerateTab } from './gen/LoRAGenerateTab.tsx';
// Placeholders
const SD3GenerateTab = () => <div className="p-4">Stable Diffusion 3.5 UI Placeholder</div>;
const R3GANGenerateTab = () => <div className="p-4">R3GAN Generation UI Placeholder</div>;

export const UnifiedGenerateTab: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState('anything');

  return (
    <div className="max-w-4xl mx-auto p-4">
      <div className="mb-6 flex items-center gap-4 bg-gray-100 p-4 rounded-lg">
        <label className="font-bold whitespace-nowrap">Model Architecture:</label>
        <select 
          value={selectedModel} 
          onChange={(e) => setSelectedModel(e.target.value)}
          className="flex-1 p-2 border rounded border-gray-300 shadow-sm focus:ring-2 focus:ring-blue-500"
        >
          <option value="anything">LoRA (Diffusion and GANs)</option>
          <option value="sd3">Stable Diffusion 3.5</option>
          <option value="r3gan">R3GAN (NVLabs)</option>
          <option value="basic_gan">Basic GAN (Custom)</option>
        </select>
      </div>

      <div className="transition-opacity duration-300">
        {selectedModel === 'anything' && <LoRAGenerateTab />}
        {selectedModel === 'sd3' && <SD3GenerateTab />}
        {selectedModel === 'r3gan' && <R3GANGenerateTab />}
        {selectedModel === 'basic_gan' && <GANGenerateTab />}
      </div>
    </div>
  );
};