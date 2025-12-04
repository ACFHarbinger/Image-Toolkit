import React, { useState, useEffect } from 'react';
import { FormRow, PathInput } from '../Shared.tsx';


export const GANTrainTab: React.FC = () => {
  // State corresponds to QLineEdit/QSpinBox values
  const [dataPath, setDataPath] = useState('');
  // FIX: Replace process.cwd() with a simple string literal, as process is undefined in the browser.
  const [savePath, setSavePath] = useState('./gan_checkpoints'); 
  const [epochs, setEpochs] = useState(50);
  const [batchSize, setBatchSize] = useState(64);
  const [lr, setLr] = useState(0.0002);
  
  // UI State for logs and preview
  const [isTraining, setIsTraining] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Mocking the TrainingWorker logic
  const startTraining = () => {
    if (!dataPath) {
      // Use custom message box instead of alert()
      console.error("Error: Invalid Data Path");
      return;
    }
    setIsTraining(true);
    // Note: 'cuda' detection should happen in the backend/worker, not the frontend.
    setLogs(prev => [...prev, "Initializing training thread...", `Device: ${'cuda'}`]);
    
    // Simulate training progress
    setTimeout(() => setLogs(prev => [...prev, "Starting training loop..."]), 1000);
  };

  // Mocking the QTimer for preview updates
  useEffect(() => {
    let interval: number | undefined;
    if (isTraining) {
      interval = setInterval(() => {
        // In a real app, fetch the latest image from backend
        // This mock call now uses setPreviewUrl, resolving the ESLint warning.
        setPreviewUrl(`https://placehold.co/200x200/4c4c4c/ffffff?text=Epoch+${Math.floor(Math.random() * 50)}`);
        setLogs(prev => [...prev, `Epoch progress... Loss_D: ${Math.random().toFixed(2)}, Loss_G: ${Math.random().toFixed(2)}`]);
      }, 5000) as unknown as number; // Type assertion for setInterval return
    }
    return () => {
      if (interval !== undefined) {
        clearInterval(interval);
      }
    };
  }, [isTraining]);

  return (
    // Updated background and text color for the main card
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200 space-y-4">
      <div className="grid grid-cols-1 gap-4">
        <FormRow label="Dataset Path:">
          <PathInput value={dataPath} onChange={setDataPath} placeholder="Path to dataset folder" />
        </FormRow>
        
        <FormRow label="Output Dir:">
          <PathInput value={savePath} onChange={setSavePath} />
        </FormRow>

        <FormRow label="Epochs:">
          {/* Updated input styling for dark mode */}
          <input type="number" value={epochs} onChange={e => setEpochs(Number(e.target.value))} className="border p-2 rounded w-full dark:bg-gray-700 dark:border-gray-600" min={1} max={10000} />
        </FormRow>

        <FormRow label="Batch Size:">
          <input type="number" value={batchSize} onChange={e => setBatchSize(Number(e.target.value))} className="border p-2 rounded w-full dark:bg-gray-700 dark:border-gray-600" min={1} max={512} />
        </FormRow>

        <FormRow label="Learning Rate:">
          <input type="number" value={lr} onChange={e => setLr(Number(e.target.value))} className="border p-2 rounded w-full dark:bg-gray-700 dark:border-gray-600" step={0.00001} />
        </FormRow>

        <button 
          onClick={startTraining}
          disabled={isTraining}
          className={`w-full py-2 px-4 rounded font-bold text-white ${isTraining ? 'bg-gray-400' : 'bg-green-600 hover:bg-green-700'}`}
        >
          {isTraining ? "Training in Progress..." : "Start Training"}
        </button>

        <div className="mt-4">
          <label className="font-medium">Training Log:</label>
          {/* Updated log background and text for dark mode */}
          <div className="h-32 overflow-y-auto bg-gray-100 dark:bg-gray-700 p-2 border rounded font-mono text-sm dark:text-gray-300">
            {logs.map((log, i) => <div key={i}>{log}</div>)}
          </div>
        </div>

        <div className="mt-4 border-2 border-dashed border-gray-300 dark:border-gray-600 p-4 flex flex-col items-center justify-center min-h-[200px]">
          {previewUrl ? (
            <img src={previewUrl} alt="Training Sample" className="max-w-full h-auto" />
          ) : (
            <span className="text-gray-500 dark:text-gray-400">Latest Training Sample</span>
          )}
        </div>
      </div>
    </div>
  );
};