import React, { useState } from "react";
import { FormRow, PathInput } from "../Shared";

export const GANGenerateTab: React.FC = () => {
  const [checkpoint, setCheckpoint] = useState("");
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
    // Updated background and text color for the main card
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200">
      <FormRow label="Checkpoint:">
        <PathInput
          value={checkpoint}
          onChange={setCheckpoint}
          type="file"
          placeholder="Path to .pth checkpoint"
        />
      </FormRow>

      <div className="flex items-center gap-4 mb-4">
        <span className="font-medium">Count:</span>
        <input
          type="number"
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          // Updated input styling for dark mode
          className="border p-2 rounded w-20 dark:bg-gray-700 dark:border-gray-600"
          min={1}
          max={64}
        />
        <button
          onClick={generateImages}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Generate Images
        </button>
      </div>

      {/* Updated image grid background and border for dark mode */}
      <div className="h-96 overflow-y-auto border dark:border-gray-600 rounded p-4 bg-gray-50 dark:bg-gray-700">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {images.map((src, idx) => (
            // Updated preview item background for dark mode
            <div
              key={idx}
              className="border dark:border-gray-600 p-1 bg-white dark:bg-gray-800 shadow-sm"
            >
              <img
                src={src}
                alt={`Generated ${idx}`}
                className="w-full h-auto"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
