import React, { useState } from "react";
import { FormRow, PathInput } from "./Shared.tsx";

export const R3GANEvaluateTab: React.FC = () => {
  const [network, setNetwork] = useState("");
  const [datasetPath, setDatasetPath] = useState("");

  // Metrics
  const [fid, setFid] = useState(false);
  const [kid, setKid] = useState(false);
  const [pr, setPr] = useState(false);
  const [inceptionScore, setInceptionScore] = useState(false);

  const handleEvaluate = () => {
    console.log("Evaluating R3GAN:", {
      network,
      datasetPath,
      metrics: { fid, kid, pr, inceptionScore },
    });
    // Add API call logic here
  };

  return (
    <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 space-y-6">
      <div className="border-b dark:border-gray-700 pb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          R3GAN Model Evaluation
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Calculate quality metrics (FID, KID, IS) for trained generative
          models.
        </p>
      </div>

      <FormRow label="Model to Evaluate (.pkl):">
        <PathInput
          value={network}
          onChange={setNetwork}
          type="file"
          placeholder="Path to .pkl network file"
        />
      </FormRow>

      <FormRow label="Reference Dataset:">
        <PathInput
          value={datasetPath}
          onChange={setDatasetPath}
          type="folder"
          placeholder="Path to reference images"
        />
      </FormRow>

      <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="font-bold mb-3 text-sm uppercase text-gray-500 dark:text-gray-400">
          Metrics to Calculate
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition">
            <input
              type="checkbox"
              checked={fid}
              onChange={(e) => setFid(e.target.checked)}
              className="w-5 h-5 text-violet-600 rounded focus:ring-violet-500"
            />
            <span>FID (fid50k_full)</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition">
            <input
              type="checkbox"
              checked={kid}
              onChange={(e) => setKid(e.target.checked)}
              className="w-5 h-5 text-violet-600 rounded focus:ring-violet-500"
            />
            <span>KID (kid50k_full)</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition">
            <input
              type="checkbox"
              checked={pr}
              onChange={(e) => setPr(e.target.checked)}
              className="w-5 h-5 text-violet-600 rounded focus:ring-violet-500"
            />
            <span>Precision/Recall (pr50k3_full)</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition">
            <input
              type="checkbox"
              checked={inceptionScore}
              onChange={(e) => setInceptionScore(e.target.checked)}
              className="w-5 h-5 text-violet-600 rounded focus:ring-violet-500"
            />
            <span>Inception Score (is50k)</span>
          </label>
        </div>
      </div>

      <div className="pt-2">
        <button
          onClick={handleEvaluate}
          className="w-full py-3 bg-green-600 text-white font-bold rounded-lg shadow hover:bg-green-700 transition-colors"
        >
          Start Evaluation
        </button>
      </div>
    </div>
  );
};
