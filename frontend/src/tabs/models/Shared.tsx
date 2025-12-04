import React from 'react';

// Replicating the QFormLayout structure
export const FormRow: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex flex-col sm:flex-row gap-2 mb-4 items-start sm:items-center">
    <label className="w-full sm:w-1/3 font-medium text-gray-700">{label}</label>
    <div className="w-full sm:w-2/3">{children}</div>
  </div>
);

// Replicating QFileDialog + QLineEdit logic
// In a web context, this usually accepts a text string for server-side paths
export const PathInput: React.FC<{
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  type?: 'file' | 'folder';
}> = ({ value, onChange, placeholder, type = 'folder' }) => (
  <div className="flex gap-2">
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="flex-1 p-2 border rounded border-gray-300"
      placeholder={placeholder || `Path to ${type}`}
    />
    <button
      className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded text-sm"
      onClick={() => alert("In a real app, this opens a server-side file picker modal")}
    >
      Browse
    </button>
  </div>
);

export const SectionHeader: React.FC<{ title: string }> = ({ title }) => (
  <h3 className="text-lg font-bold border-b pb-2 mb-4 mt-6">{title}</h3>
);