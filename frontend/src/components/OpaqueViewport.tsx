import React from 'react';

// --- OpaqueViewport (Wrapper for background consistency) ---
export const OpaqueViewport: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div style={{ backgroundColor: '#2c2f33', width: '100%', height: '100%', overflow: 'auto' }}>
      {children}
    </div>
  );
};