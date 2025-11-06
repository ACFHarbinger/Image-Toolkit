// src/components/PathInput.jsx
import React from 'react';
import { File, FolderOpen } from 'lucide-react';

const PathInput = ({ value, onChange, onBrowseFile, onBrowseDir }) => {
  const inputClasses = "w-full px-4 py-2 text-gray-900 bg-white/80 border border-gray-300 rounded-md dark:bg-gray-800/80 dark:text-gray-100 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-all";
  const buttonClasses = "flex-1 px-3 py-1.5 text-sm text-gray-700 bg-white/50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-700 rounded-md shadow-sm transition-colors";

  return (
    <div className="flex flex-col gap-2">
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder="Type path manually..."
        className={inputClasses}
      />
      <div className="flex gap-2">
        {onBrowseFile && (
          <button onClick={onBrowseFile} className={buttonClasses}>
            <File size={16} className="inline mr-1" /> Choose File...
          </button>
        )}
        {onBrowseDir && (
          <button onClick={onBrowseDir} className={buttonClasses}>
            <FolderOpen size={16} className="inline mr-1" /> Choose Directory...
          </button>
        )}
      </div>
    </div>
  );
};

export default PathInput;