// src/tabs/DeleteTab.jsx
import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../components/FormRow';
import PathInput from '../components/PathInput';

const DeleteTab = forwardRef(({ showModal }, ref) => {
  const [deletePath, setDeletePath] = useState('');

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'delete',
      delete_path: deletePath,
    }),
  }));

  return (
    <div className="p-6">
      <FormRow label="Path to Delete (File or Dir):">
        <PathInput
          value={deletePath}
          onChange={(e) => setDeletePath(e.target.value)}
          onBrowseFile={() => setDeletePath('/simulated/path/to/delete.jpg')}
          onBrowseDir={() => setDeletePath('/simulated/path/to/directory/')}
        />
      </FormRow>
      <button onClick={() => showModal("Simulating Delete Operation...", "error")} className="w-full px-4 py-2 font-semibold text-white transition-colors bg-red-600 rounded-md shadow-sm hover:bg-red-700">
        Run Delete
      </button>
    </div>
  );
});

export default DeleteTab;