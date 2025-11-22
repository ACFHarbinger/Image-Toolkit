import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../components/FormRow.tsx';
import PathInput from '../components/PathInput.tsx';

interface DatabaseTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error' | 'custom') => void;
}

export interface DatabaseTabHandle {
  getData: () => {
    action: string;
    db_path: string;
    image_path: string;
  };
}

const DatabaseTab = forwardRef<DatabaseTabHandle, DatabaseTabProps>(({ showModal }, ref) => {
  const [dbPath, setDbPath] = useState<string>('');
  const [imagePath, setImagePath] = useState<string>('');

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'database',
      db_path: dbPath,
      image_path: imagePath,
    }),
  }));

  return (
    <div className="p-6">
      <FormRow label="Database Path:">
        <PathInput
          value={dbPath}
          onChange={(e) => setDbPath(e.target.value)}
          onBrowseFile={() => setDbPath('/simulated/database.db')}
        />
      </FormRow>
      <FormRow label="Image Path:">
        <PathInput
          value={imagePath}
          onChange={(e) => setImagePath(e.target.value)}
          onBrowseFile={() => setImagePath('/simulated/image.jpg')}
        />
      </FormRow>
      <div className="flex gap-2">
        <button onClick={() => showModal("Simulating Add/Update Image Path...", "success")} className="flex-1 px-4 py-2 font-semibold text-white transition-colors bg-green-600 rounded-md shadow-sm hover:bg-green-700">
          Add/Update Image Path
        </button>
        <button onClick={() => showModal("Simulating Update Metadata...", "success")} className="flex-1 px-4 py-2 font-semibold text-white transition-colors bg-yellow-500 rounded-md shadow-sm hover:bg-yellow-600">
          Update Loaded Metadata
        </button>
        <button onClick={() => showModal("Simulating Delete from Database...", "error")} className="flex-1 px-4 py-2 font-semibold text-white transition-colors bg-red-600 rounded-md shadow-sm hover:bg-red-700">
          Delete from Database
        </button>
      </div>
    </div>
  );
});

export default DatabaseTab;