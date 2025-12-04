import React, { useState } from 'react';
import { FormRow, PathInput } from '../Shared.tsx';

export const R3GANGenerateTab: React.FC = () => {
  const [network, setNetwork] = useState('');
  const [outDir, setOutDir] = useState('');
  const [seeds, setSeeds] = useState('0-7');
  const [classIdx, setClassIdx] = useState(-1);

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200 space-y-4">
      <FormRow label="Network (.pkl):">
        <PathInput value={network} onChange={setNetwork} type="file" placeholder="Path to .pkl model" />
      </FormRow>

      <FormRow label="Output Directory:">
        <PathInput value={outDir} onChange={setOutDir} type="folder" placeholder="Select output folder" />
      </FormRow>

      <FormRow label="Seeds (e.g. 0-7):">
        <input 
          type="text" 
          value={seeds} 
          onChange={(e) => setSeeds(e.target.value)} 
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600" 
          placeholder="0,1,2 or 0-100"
        />
      </FormRow>

      <FormRow label="Class Index (opt.):">
        <input 
          type="number" 
          value={classIdx} 
          onChange={(e) => setClassIdx(Number(e.target.value))} 
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600" 
          min={-1}
          placeholder="-1 for unconditional"
        />
      </FormRow>

      <div className="flex gap-2 pt-4">
        <button className="flex-1 bg-purple-600 text-white py-2 rounded hover:bg-purple-700 font-bold">Generate R3GAN Images</button>
      </div>
    </div>
  );
};