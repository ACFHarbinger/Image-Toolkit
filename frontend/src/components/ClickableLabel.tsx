import React from 'react';

interface LabelProps {
  path: string;
  src?: string; // The image source
  isSelected?: boolean;
  // Signals
  onPathClicked?: (path: string) => void;
  onPathDoubleClicked?: (path: string) => void;
  onPathRightClicked?: (e: React.MouseEvent, path: string) => void;
}

// Shared base style logic to match Python
const getLabelStyle = (isSelected: boolean): React.CSSProperties => ({
  width: '100px',
  height: '100px',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  backgroundColor: isSelected ? '#36393f' : '#2c2f33',
  border: isSelected ? '3px solid #5865f2' : '1px dashed #4f545c',
  color: '#b9bbbe',
  cursor: 'pointer',
  boxSizing: 'border-box',
  position: 'relative',
});

// --- ClickableLabel ---
export const ClickableLabel: React.FC<LabelProps> = ({
  path,
  src,
  isSelected = false,
  onPathClicked,
  onPathDoubleClicked,
  onPathRightClicked,
}) => {
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault(); // Stop native context menu
    onPathRightClicked?.(e, path);
  };

  return (
    <div
      // data-selectable and data-path are used by MarqueeScrollArea
      data-selectable="true"
      data-path={path}
      style={getLabelStyle(isSelected)}
      onClick={() => onPathClicked?.(path)}
      onDoubleClick={() => onPathDoubleClicked?.(path)}
      onContextMenu={handleContextMenu}
      title={path.split(/[/\\]/).pop()}
    >
      {src ? (
        <img
          src={src}
          alt="thumbnail"
          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
        />
      ) : (
        <span>Loading...</span>
      )}
    </div>
  );
};