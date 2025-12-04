import React, { useState } from 'react';
import { GANTrainTab } from './train/GANTrainTab.tsx';
import { LoRATrainTab } from './train/LoRATrainTab.tsx';
// Placeholder for R3GAN
const R3GANTrainTab = () => <div className="p-4">R3GAN Training UI Placeholder</div>;

export const UnifiedTrainTab: React.FC = () => {
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
          <option value="r3gan">R3GAN (NVLabs)</option>
          <option value="basic_gan">Basic GAN (Custom)</option>
        </select>
      </div>

      <div className="transition-opacity duration-300">
        {selectedModel === 'anything' && <LoRATrainTab />}
        {selectedModel === 'r3gan' && <R3GANTrainTab />}
        {selectedModel === 'basic_gan' && <GANTrainTab />}
      </div>
    </div>
  );
};