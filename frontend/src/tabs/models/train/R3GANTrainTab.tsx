import React, { useState } from "react";
import { FormRow, PathInput } from "../Shared.tsx";

const PRESETS = [
  "CIFAR10",
  "FFHQ-64",
  "FFHQ-256",
  "ImageNet-32",
  "ImageNet-64",
];

export const R3GANTrainTab: React.FC = () => {
  const [outDir, setOutDir] = useState("./training-runs");
  const [datasetZip, setDatasetZip] = useState("");
  const [preset, setPreset] = useState(PRESETS[0]);
  const [gpus, setGpus] = useState(8);
  const [batchSize, setBatchSize] = useState(256);

  // Checkboxes
  const [mirror, setMirror] = useState(false);
  const [aug, setAug] = useState(false);
  const [cond, setCond] = useState(false);

  const [tick, setTick] = useState(1);
  const [snap, setSnap] = useState(200);

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded shadow text-gray-800 dark:text-gray-200 space-y-4">
      <FormRow label="Output Directory:">
        <PathInput value={outDir} onChange={setOutDir} type="folder" />
      </FormRow>

      <FormRow label="Dataset (.zip):">
        <PathInput
          value={datasetZip}
          onChange={setDatasetZip}
          type="file"
          placeholder="Path to dataset zip"
        />
      </FormRow>

      <FormRow label="Preset:">
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value)}
          className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        >
          {PRESETS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </FormRow>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormRow label="GPUs:">
          <input
            type="number"
            value={gpus}
            onChange={(e) => setGpus(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={1}
          />
        </FormRow>
        <FormRow label="Batch Size:">
          <input
            type="number"
            value={batchSize}
            onChange={(e) => setBatchSize(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={1}
            max={8192}
          />
        </FormRow>
      </div>

      <div className="flex flex-col gap-2 p-3 border rounded dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={mirror}
            onChange={(e) => setMirror(e.target.checked)}
            className="w-4 h-4"
          />
          <span>Mirror Data</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={aug}
            onChange={(e) => setAug(e.target.checked)}
            className="w-4 h-4"
          />
          <span>Use Augmentation</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={cond}
            onChange={(e) => setCond(e.target.checked)}
            className="w-4 h-4"
          />
          <span>Conditional GAN</span>
        </label>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormRow label="Log Frequency (ticks):">
          <input
            type="number"
            value={tick}
            onChange={(e) => setTick(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={1}
          />
        </FormRow>
        <FormRow label="Snapshot Freq (snaps):">
          <input
            type="number"
            value={snap}
            onChange={(e) => setSnap(Number(e.target.value))}
            className="w-full border p-2 rounded dark:bg-gray-700 dark:border-gray-600"
            min={1}
          />
        </FormRow>
      </div>

      <div className="flex gap-2 pt-4">
        <button className="flex-1 bg-green-600 text-white py-2 rounded hover:bg-green-700 font-bold">
          Start R3GAN Training
        </button>
      </div>
    </div>
  );
};
