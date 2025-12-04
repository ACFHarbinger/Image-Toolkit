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
      alert("Error: Invalid Data Path");
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
    let interval: number;
    if (isTraining) {
      interval = setInterval(() => {
        // In a real app, fetch the latest image from backend
        // setPreviewUrl('/api/latest-sample.png'); 
        setLogs(prev => [...prev, `Epoch progress... Loss_D: 0.5, Loss_G: 1.2`]);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [isTraining]);

  return (
    <div className="p-4 bg-white rounded shadow">
      <div className="grid grid-cols-1 gap-4">
        <FormRow label="Dataset Path:">
          <PathInput value={dataPath} onChange={setDataPath} placeholder="Path to dataset folder" />
        </FormRow>
        
        <FormRow label="Output Dir:">
          <PathInput value={savePath} onChange={setSavePath} />
        </FormRow>

        <FormRow label="Epochs:">
          <input type="number" value={epochs} onChange={e => setEpochs(Number(e.target.value))} className="border p-2 rounded w-full" min={1} max={10000} />
        </FormRow>

        <FormRow label="Batch Size:">
          <input type="number" value={batchSize} onChange={e => setBatchSize(Number(e.target.value))} className="border p-2 rounded w-full" min={1} max={512} />
        </FormRow>

        <FormRow label="Learning Rate:">
          <input type="number" value={lr} onChange={e => setLr(Number(e.target.value))} className="border p-2 rounded w-full" step={0.00001} />
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
          <div className="h-32 overflow-y-auto bg-gray-100 p-2 border rounded font-mono text-sm">
            {logs.map((log, i) => <div key={i}>{log}</div>)}
          </div>
        </div>

        <div className="mt-4 border-2 border-dashed border-gray-300 p-4 flex flex-col items-center justify-center min-h-[200px]">
          {previewUrl ? (
            <img src={previewUrl} alt="Training Sample" className="max-w-full h-auto" />
          ) : (
            <span className="text-gray-500">Latest Training Sample</span>
          )}
        </div>
      </div>
    </div>
  );
};