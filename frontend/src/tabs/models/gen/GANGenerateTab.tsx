import React, { useState } from 'react';
import { FormRow, PathInput } from '../Shared.tsx';

export const GANGenerateTab: React.FC = () => {
  const [checkpoint, setCheckpoint] = useState('');
  const [count, setCount] = useState(8);
  const [images, setImages] = useState<string[]>([]); // URLs of generated images

  const generateImages = () => {
    if (!checkpoint) {
      alert("Error: Checkpoint file not found.");
      return;
    }
    // Simulate generation
    const mockImages = Array(count).fill("https://via.placeholder.com/128");
    setImages(mockImages);
  };

  return (
    <div className="p-4 bg-white rounded shadow">
      <FormRow label="Checkpoint:">
        <PathInput value={checkpoint} onChange={setCheckpoint} type="file" placeholder="Path to .pth checkpoint" />
      </FormRow>

      <div className="flex items-center gap-4 mb-4">
        <span className="font-medium">Count:</span>
        <input 
          type="number" 
          value={count} 
          onChange={e => setCount(Number(e.target.value))} 
          className="border p-2 rounded w-20" 
          min={1} max={64} 
        />
        <button 
          onClick={generateImages}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Generate Images
        </button>
      </div>

      <div className="h-96 overflow-y-auto border rounded p-4 bg-gray-50">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {images.map((src, idx) => (
            <div key={idx} className="border p-1 bg-white shadow-sm">
              <img src={src} alt={`Generated ${idx}`} className="w-full h-auto" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};