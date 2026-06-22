/**
 * ImagePreview - Full-screen Image Preview Modal
 *
 * Displays images in a modal overlay with keyboard navigation
 * and zoom capabilities.
 */

import React, { useEffect, useState } from 'react';
import { X, ZoomIn, ZoomOut, RotateCw, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store/appStore';

interface ImagePreviewProps {
  path: string;
  onClose: () => void;
  images?: string[]; // Optional: array of images for navigation
  currentIndex?: number;
}

export const ImagePreview: React.FC<ImagePreviewProps> = ({
  path,
  onClose,
  images = [],
  currentIndex = 0,
}) => {
  const { preferences } = useAppStore();
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [currentImageIndex, setCurrentImageIndex] = useState(currentIndex);
  const [imageError, setImageError] = useState(false);

  const isDark = preferences.theme === 'dark';
  const currentPath = images.length > 0 ? images[currentImageIndex] : path;
  const hasMultipleImages = images.length > 1;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          onClose();
          break;
        case 'ArrowLeft':
          if (hasMultipleImages && currentImageIndex > 0) {
            setCurrentImageIndex(currentImageIndex - 1);
            resetView();
          }
          break;
        case 'ArrowRight':
          if (hasMultipleImages && currentImageIndex < images.length - 1) {
            setCurrentImageIndex(currentImageIndex + 1);
            resetView();
          }
          break;
        case '+':
        case '=':
          setZoom((prev) => Math.min(prev + 25, 400));
          break;
        case '-':
          setZoom((prev) => Math.max(prev - 25, 25));
          break;
        case '0':
          resetView();
          break;
        case 'r':
        case 'R':
          setRotation((prev) => (prev + 90) % 360);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, currentImageIndex, images.length, hasMultipleImages]);

  const resetView = () => {
    setZoom(100);
    setRotation(0);
    setImageError(false);
  };

  const handlePrevious = () => {
    if (currentImageIndex > 0) {
      setCurrentImageIndex(currentImageIndex - 1);
      resetView();
    }
  };

  const handleNext = () => {
    if (currentImageIndex < images.length - 1) {
      setCurrentImageIndex(currentImageIndex + 1);
      resetView();
    }
  };

  const handleDownload = async () => {
    try {
      // In Tauri, we can use the shell to open file location
      // or implement a proper download mechanism
      console.log('Download:', currentPath);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Controls Bar */}
      <div
        className="absolute top-0 left-0 right-0 p-4 flex items-center justify-between z-10 bg-gradient-to-b from-black/50 to-transparent"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2">
          <span className="text-white text-sm font-mono">
            {hasMultipleImages && `${currentImageIndex + 1} / ${images.length}`}
          </span>
          <span className="text-white/60 text-xs truncate max-w-md">
            {currentPath}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Zoom Controls */}
          <button
            onClick={() => setZoom((prev) => Math.max(prev - 25, 25))}
            className="p-2 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
            title="Zoom Out (-)"
          >
            <ZoomOut size={20} />
          </button>
          <span className="text-white text-sm font-mono min-w-[60px] text-center">
            {zoom}%
          </span>
          <button
            onClick={() => setZoom((prev) => Math.min(prev + 25, 400))}
            className="p-2 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
            title="Zoom In (+)"
          >
            <ZoomIn size={20} />
          </button>

          {/* Rotate */}
          <button
            onClick={() => setRotation((prev) => (prev + 90) % 360)}
            className="p-2 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
            title="Rotate (R)"
          >
            <RotateCw size={20} />
          </button>

          {/* Download */}
          <button
            onClick={handleDownload}
            className="p-2 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
            title="Download"
          >
            <Download size={20} />
          </button>

          {/* Close */}
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
            title="Close (Esc)"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Navigation Arrows */}
      {hasMultipleImages && (
        <>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handlePrevious();
            }}
            disabled={currentImageIndex === 0}
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors disabled:opacity-30 disabled:cursor-not-allowed z-10"
            title="Previous (←)"
          >
            <ChevronLeft size={32} />
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              handleNext();
            }}
            disabled={currentImageIndex === images.length - 1}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors disabled:opacity-30 disabled:cursor-not-allowed z-10"
            title="Next (→)"
          >
            <ChevronRight size={32} />
          </button>
        </>
      )}

      {/* Image Container */}
      <div
        className="relative flex items-center justify-center max-w-full max-h-full p-16"
        onClick={(e) => e.stopPropagation()}
      >
        {imageError ? (
          <div className="text-white text-center">
            <p className="text-xl mb-2">Failed to load image</p>
            <p className="text-sm text-white/60">{currentPath}</p>
          </div>
        ) : (
          <img
            src={currentPath.startsWith('file://') ? currentPath : `file://${currentPath}`}
            alt="Preview"
            className="max-w-full max-h-full object-contain transition-transform duration-200"
            style={{
              transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
            }}
            onError={() => setImageError(true)}
            draggable={false}
          />
        )}
      </div>

      {/* Help Hint */}
      <div
        className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/50 text-xs font-mono bg-black/30 px-4 py-2 rounded-full"
        onClick={(e) => e.stopPropagation()}
      >
        ← → Navigate | +/- Zoom | R Rotate | 0 Reset | Esc Close
      </div>
    </div>
  );
};
