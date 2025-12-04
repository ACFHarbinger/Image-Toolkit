import React from 'react';
import { Loader2, FileVideo } from 'lucide-react';

interface LabelProps {
  path: string;
  src?: string; // The image source (or placeholder constant)
  isVideo?: boolean; // New prop to identify content type
  isSelected?: boolean;
  onPathClicked?: (path: string) => void;
  onPathDoubleClicked?: (path: string) => void;
  onPathRightClicked?: (e: React.MouseEvent, path: string) => void;
}

// CHANGE: Export this constant so the parent can use it
export const VIDEO_PLACEHOLDER_CONST = 'VIDEO_WAITING';

// Shared base style logic
const getLabelStyle = (isSelected: boolean): React.CSSProperties => ({
  width: '100px',
  height: '100px',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  backgroundColor: isSelected ? '#36393f' : '#2c2f33',
  border: isSelected ? '3px solid #5865f2' : '1px solid #2c2f33',
  borderRadius: '4px',
  color: '#b9bbbe',
  cursor: 'pointer',
  boxSizing: 'border-box',
  position: 'relative',
  overflow: 'hidden',
  transition: 'all 0.1s ease-in-out',
});

export const ClickableLabel: React.FC<LabelProps> = ({
  path,
  src,
  isVideo,
  isSelected = false,
  onPathClicked,
  onPathDoubleClicked,
  onPathRightClicked,
}) => {
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    onPathRightClicked?.(e, path);
  };

  // Determine what to render inside
  const renderContent = () => {
    // 1. Loading State (Placeholder)
    if (src === VIDEO_PLACEHOLDER_CONST) {
      return (
        <div className="flex flex-col items-center justify-center text-gray-500 gap-1">
          <Loader2 size={20} className="animate-spin text-blue-500" />
          <span className="text-[10px] font-mono">Loading...</span>
        </div>
      );
    }

    // 2. Actual Image/Thumbnail
    if (src) {
      return (
        <>
            <img
            src={src}
            alt="thumbnail"
            className="w-full h-full object-cover"
            loading="lazy"
            />
            {/* Overlay Icon for Video identification */}
            {isVideo && (
                <div className="absolute top-1 right-1 bg-black/60 p-1 rounded-full">
                    <FileVideo size={10} className="text-white" />
                </div>
            )}
        </>
      );
    }

    // 3. Fallback (No src provided)
    return <span className="text-xs text-center p-1 break-all">{path.split(/[/\\]/).pop()}</span>;
  };

  return (
    <div
      data-selectable="true"
      data-path={path}
      style={getLabelStyle(isSelected)}
      onClick={() => onPathClicked?.(path)}
      onDoubleClick={() => onPathDoubleClicked?.(path)}
      onContextMenu={handleContextMenu}
      title={path.split(/[/\\]/).pop()}
      className="group hover:bg-gray-700 hover:scale-[1.02] shadow-sm"
    >
      {renderContent()}
    </div>
  );
};