// src/components/FormRow.jsx
import React from 'react';

const FormRow = ({ label, children }) => {
  return (
    <div className="grid grid-cols-1 gap-2 py-4 border-b border-gray-200/50 md:grid-cols-3 md:gap-4 dark:border-gray-700/50 last:border-b-0">
      <label className="font-semibold text-gray-700 dark:text-gray-300 md:text-right md:pt-2">
        {label}
      </label>
      <div className="md:col-span-2">
        {children}
      </div>
    </div>
  );
};

export default FormRow;