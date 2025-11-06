import React, { forwardRef, useState, useImperativeHandle, useEffect, useRef, useCallback } from 'react';
import { RefreshCcw, Check, FolderOpen, Loader2, Image as ImageIcon, Trash2, Plus, PenSquare, X, Minus, Maximize2, Minimize2, ChevronLeft, ChevronRight } from 'lucide-react';

// --- Configuration Constants ---
const IMAGES_PER_PAGE = 15;
const IMAGES_PER_ROW = 5;

// --- Utility function to convert a File object to a Base64 string ---
const fileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = error => reject(error);
    reader.readAsDataURL(file);
  });
};

// --- Floating Image Window Component (Unchanged) ---
const FloatingImageWindow = ({ windowId, initialImageSrc, initialTitle, onClose, onMinimize, isMinimized, onMaximize, isMaximized, onBringToFront }) => {
  const [position, setPosition] = useState({ x: 50 + (windowId * 20), y: 50 + (windowId * 20) });
  const [isDragging, setIsDragging] = useState(false);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const windowRef = useRef(null);
  
  // Custom Hook for Draggability
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      // Calculate new position based on mouse movement and initial offset
      const newX = e.clientX - offset.x;
      const newY = e.clientY - offset.y;
      setPosition({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, offset]);

  // Handler to start dragging
  const handleMouseDown = (e) => {
    // Check if the target is the header (and not a button within it)
    if (e.target.closest('.window-controls')) return;
    
    // Bring to front on drag start
    onBringToFront(windowId);

    if (isMaximized) return; // Cannot drag when maximized

    const rect = windowRef.current.getBoundingClientRect();
    setOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setIsDragging(true);
  };
  
  // Styling for the window container
  const windowStyle = isMaximized ? {
    top: 0, left: 0, width: '100vw', height: '100vh', 
    transition: 'all 0.3s ease-in-out', zIndex: 9999 + windowId 
  } : {
    top: position.y, left: position.x, 
    transform: isDragging ? 'scale(1.02)' : 'scale(1)',
    transition: isDragging ? 'none' : 'transform 0.1s ease-out',
    zIndex: 100 + windowId, 
  };

  const contentStyle = isMinimized ? { display: 'none' } : { display: 'flex' };

  return (
    <div
      ref={windowRef}
      className={`fixed rounded-lg shadow-2xl bg-white dark:bg-gray-800 backdrop-blur-sm flex flex-col overflow-hidden min-w-[300px] min-h-[150px] transition-transform ${isMaximized ? 'rounded-none' : 'w-[500px] h-[400px]'}`}
      style={windowStyle}
      onClick={() => onBringToFront(windowId)}
    >
      {/* Window Header / Drag Handle */}
      <div 
        className={`flex items-center justify-between p-2 font-semibold text-sm cursor-grab ${isDragging ? 'cursor-grabbing' : 'cursor-grab'} ${isMaximized ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
        onMouseDown={handleMouseDown}
      >
        <span className={`${isMaximized ? 'text-white' : 'dark:text-gray-200'}`}>
          {isMinimized ? `[M] ${initialTitle}` : initialTitle}
        </span>
        
        {/* Window Controls */}
        <div className="flex space-x-2 window-controls">
          <button onClick={() => onMinimize(windowId)} className="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600" title="Minimize">
            <Minus size={14} className="dark:text-white" />
          </button>
          <button onClick={() => onMaximize(windowId)} className="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600" title={isMaximized ? "Restore" : "Maximize"}>
            {isMaximized ? <Minimize2 size={14} className="dark:text-white" /> : <Maximize2 size={14} className="dark:text-white" />}
          </button>
          <button onClick={() => onClose(windowId)} className="p-1 rounded hover:bg-red-500 hover:text-white" title="Close">
            <X size={14} className="dark:text-white" />
          </button>
        </div>
      </div>

      {/* Window Content - Image Preview */}
      <div 
        className="flex-grow flex items-center justify-center p-4 overflow-auto" 
        style={contentStyle}
      >
        <img
          src={initialImageSrc}
          alt={initialTitle}
          // The crucial change: Use max-w-none to allow full size. 
          className="max-w-none w-auto h-auto rounded-lg shadow-xl"
        />
      </div>
      
      {/* Minimized Dock Bar */}
      {isMinimized && (
        <div 
          className="absolute bottom-0 left-0 right-0 p-2 bg-gray-900/90 text-white text-center cursor-pointer"
          onClick={() => onMinimize(windowId)}
          title="Restore Window"
        >
          {initialTitle} (Minimized)
        </div>
      )}
    </div>
  );
};


// --- ScanFSETab Component (The Main Tab) ---

const ScanFSETab = forwardRef(({ showModal, onAddImagesToDb }, ref) => {
  const [images, setImages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [openWindows, setOpenWindows] = useState([]); 
  const [currentPage, setCurrentPage] = useState(1);
  
  // Ref for the hidden file input
  const directoryInputRef = useRef(null);

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'scan_and_select',
      selected_images: images.filter(img => img.selected).map(img => img.path),
    }),
    refresh: handleBrowseDirectory, // The 'refresh' function still triggers directory browsing
  }));

  const handleBrowseDirectory = () => {
    directoryInputRef.current.click();
  };
  
  const selectedCount = images.filter(img => img.selected).length;

  const handleDirectoryChange = async (event) => {
    if (!event.target.files || event.target.files.length === 0) {
      showModal("No directory selected.", "info");
      return;
    }

    setIsLoading(true);
    // Revoke all existing blob URLs and clear images list
    images.forEach(img => img.blobUrl && URL.revokeObjectURL(img.blobUrl));
    setImages([]); 
    setCurrentPage(1); // Reset to first page on new scan
    
    const files = Array.from(event.target.files);
    // Limit increased to 200 to allow for more than 4 pages
    const imageFiles = files.filter(file => file.type.startsWith('image/')).slice(0, 200); 

    if (imageFiles.length === 0) {
      showModal(`Scan complete! No images found.`, 'info', 2000);
      setIsLoading(false);
      return;
    }

    const initialImagesState = await Promise.all(imageFiles.map(async (file) => {
      // Use Blob URL for thumbnails
      const blobUrl = URL.createObjectURL(file);
      
      return {
        fileObject: file, 
        path: file.webkitRelativePath || file.name, 
        name: file.name,
        size: file.size,
        selected: false,
        blobUrl: blobUrl, // Used for thumbnail display
        base64Cache: null, // Base64 cached on first preview or on demand
      };
    }));

    setImages(initialImagesState);
    setIsLoading(false);
    showModal(`Scan complete! Found ${initialImagesState.length} images.`, 'success', 2000);
  };

  // Clean up blob URLs when the component unmounts or images change
  useEffect(() => {
    return () => {
      images.forEach(img => img.blobUrl && URL.revokeObjectURL(img.blobUrl));
    };
  }, [images]);

  const handleToggleSelect = (path) => {
    setImages(prevImages =>
      prevImages.map(img =>
        img.path === path ? { ...img, selected: !img.selected } : img
      )
    );
  };
  
  // --- New Handler for Refreshing/Clearing the Preview ---
  const handleRefreshDirectory = () => {
    // 1. Revoke existing blob URLs from current images to prevent memory leaks
    images.forEach(img => img.blobUrl && URL.revokeObjectURL(img.blobUrl));
    
    // 2. Clear all image data, open windows, and reset pagination
    setImages([]);
    setOpenWindows([]);
    setCurrentPage(1);

    // 3. Provide feedback to the user
    showModal("Image directory preview cleared. Ready to scan a new directory.", "info", 2000);
  };
  
  // --- Window Management Functions ---

  const handleWindowClose = useCallback((idToClose) => {
    setOpenWindows(prev => prev.filter(w => w.id !== idToClose));
  }, []);

  const handleWindowMinimize = useCallback((idToToggle) => {
    setOpenWindows(prev => 
      prev.map(w => 
        w.id === idToToggle ? { ...w, isMinimized: !w.isMinimized } : w
      )
    );
  }, []);

  const handleWindowMaximize = useCallback((idToToggle) => {
    setOpenWindows(prev => 
      prev.map(w => 
        w.id === idToToggle ? { ...w, isMaximized: !w.isMaximized } : w
      )
    );
  }, []);
  
  const handleBringToFront = useCallback((idToBringFront) => {
    setOpenWindows(prev => {
      const targetIndex = prev.findIndex(w => w.id === idToBringFront);
      if (targetIndex === -1 || targetIndex === prev.length - 1) return prev;

      const targetWindow = prev[targetIndex];
      const newWindows = prev.filter(w => w.id !== idToBringFront);
      newWindows.push(targetWindow);
      
      return newWindows.map((w, index) => ({ ...w, id: index }));
    });
  }, []);


  const viewSelectedImages = async () => {
    const selectedImages = images.filter(img => img.selected);
    if (selectedImages.length === 0) {
      showModal("Please select one or more images to view.", "error");
      return;
    }
    
    setIsLoading(true); 

    for (const image of selectedImages) {
      // 1. Check if the window is already open
      if (openWindows.some(w => w.path === image.path)) {
        continue;
      }
      
      let imageSrc = image.base64Cache;
      
      // 2. Generate Base64 on demand if not cached
      if (!imageSrc) {
        try {
          const generatedBase64 = await fileToBase64(image.fileObject);
          imageSrc = generatedBase64;
          
          setImages(prevImages => prevImages.map(img => 
            img.path === image.path ? { ...img, base64Cache: generatedBase64 } : img
          ));
        } catch(e) {
          showModal(`Failed to read file data: ${image.name}. Error: ${e.message}`, "error", 5000);
          continue;
        }
      }

      // 3. Open a new floating window
      setOpenWindows(prev => {
        const newWindow = {
          id: prev.length, // Simple index for z-index management
          path: image.path,
          src: imageSrc,
          title: image.name,
          isMinimized: false,
          isMaximized: false,
        };
        // Bring the new window immediately to the front by pushing it last
        const newArray = [...prev, newWindow];
        return newArray.map((w, index) => ({ ...w, id: index }));
      });
    }
    
    setIsLoading(false); // Re-enable controls
  };
  
  // --- Existing handlers for batch operations ---

  const handleAddSelectedToDb = () => {
    const selectedFiles = images.filter(img => img.selected).map(img => img.fileObject);
    if (selectedFiles.length > 0) {
      onAddImagesToDb(selectedFiles); 
      showModal(`Simulating adding ${selectedFiles.length} images to the database.`, "success");
      setImages(prevImages => prevImages.map(img => ({ ...img, selected: false })));
    } else {
      showModal("No images selected to add to database.", "error");
    }
  };
  
  const handleUpdateSelected = () => {
    const selectedFiles = images.filter(img => img.selected).map(img => img.fileObject);
    if (selectedFiles.length > 0) {
      showModal(`Simulating **updating metadata** for ${selectedFiles.length} selected images in the database.`, "info");
    } else {
      showModal("No images selected to update.", "error");
    }
  };
  
  const handleDeleteSelected = () => {
    const selectedPaths = new Set(images.filter(img => img.selected).map(img => img.path));
    
    if (selectedPaths.size === 0) {
      showModal("No images selected to remove from the list.", "error");
      return;
    }

    setImages(prevImages => 
      prevImages.filter(img => {
        if (selectedPaths.has(img.path)) {
          img.blobUrl && URL.revokeObjectURL(img.blobUrl);
          return false;
        }
        return true; 
      })
    );
    
    setOpenWindows(prev => prev.filter(w => !selectedPaths.has(w.path)));
    
    showModal(`Removed ${selectedPaths.size} images from the list.`, "info", 2000);
  };
  
  // --- PAGINATION LOGIC ---
  const totalPages = Math.ceil(images.length / IMAGES_PER_PAGE);
  const startIndex = (currentPage - 1) * IMAGES_PER_PAGE;
  const endIndex = startIndex + IMAGES_PER_PAGE;
  const currentImages = images.slice(startIndex, endIndex);

  const handlePageChange = (page) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const PageDropdown = ({ totalPages, currentPage, onPageChange }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    useEffect(() => {
      const handleClickOutside = (e) => {
        if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
          setIsOpen(false);
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="px-3 py-1 rounded-full text-sm font-semibold bg-gray-200 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600 transition-all"
        >
          ...
        </button>

        {isOpen && (
          <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 w-48 max-h-60 overflow-y-auto bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 z-50">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
              <button
                key={page}
                onClick={() => {
                  onPageChange(page);
                  setIsOpen(false);
                }}
                className={`w-full px-4 py-2 text-left text-sm transition-colors ${
                  page === currentPage
                    ? 'bg-violet-600 text-white font-bold'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200'
                }`}
              >
                Page {page}
                {page === currentPage && ' (Current)'}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderPaginationButtons = () => {
    if (totalPages <= 1) return null;

    const showCurrentBeforeEllipsis = currentPage > 1 && currentPage < totalPages;

    return (
      <div className="flex items-center justify-center space-x-1">
        {/* Previous */}
        <button
          onClick={() => handlePageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-2 rounded-full hover:bg-violet-600/20 disabled:opacity-50 transition-colors"
          title="Previous Page"
        >
          <ChevronLeft size={18} className="dark:text-white" />
        </button>

        {/* First Page */}
        <button
          onClick={() => handlePageChange(1)}
          className={`px-3 py-1 rounded-full text-sm font-semibold transition-all ${
            currentPage === 1
              ? 'bg-violet-600 text-white shadow-lg'
              : 'bg-gray-200 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600'
          }`}
        >
          1
        </button>

        {/* Current Page Before ... (only if not first or last) */}
        {showCurrentBeforeEllipsis && (
          <button
            onClick={() => handlePageChange(currentPage)}
            className="px-3 py-1 rounded-full text-sm font-semibold bg-violet-600 text-white shadow-lg transition-all"
          >
            {currentPage}
          </button>
        )}

        {/* Ellipsis Dropdown */}
        {totalPages > 2 && (
          <PageDropdown
            totalPages={totalPages}
            currentPage={currentPage}
            onPageChange={handlePageChange}
          />
        )}

        {/* Last Page */}
        {totalPages > 1 && (
          <button
            onClick={() => handlePageChange(totalPages)}
            className={`px-3 py-1 rounded-full text-sm font-semibold transition-all ${
              currentPage === totalPages
                ? 'bg-violet-600 text-white shadow-lg'
                : 'bg-gray-200 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            {totalPages}
          </button>
        )}

        {/* Next */}
        <button
          onClick={() => handlePageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-full hover:bg-violet-600/20 disabled:opacity-50 transition-colors"
          title="Next Page"
        >
          <ChevronRight size={18} className="dark:text-white" />
        </button>
      </div>
    );
  };


  return (
    <div className="flex flex-col h-full p-6 dark:bg-gray-900/50">
      {/* Render Floating Image Windows */}
      {openWindows.map(window => (
        <FloatingImageWindow
          key={window.path} 
          windowId={window.id}
          initialImageSrc={window.src}
          initialTitle={window.title}
          onClose={handleWindowClose}
          onMinimize={handleWindowMinimize}
          isMinimized={window.isMinimized}
          onMaximize={handleWindowMaximize}
          isMaximized={window.isMaximized}
          onBringToFront={handleBringToFront}
        />
      ))}

      {/* Hidden file input for directory selection */}
      <input
        type="file"
        // The webkitdirectory attribute is necessary for directory scanning
        webkitdirectory="true" 
        multiple
        ref={directoryInputRef}
        onChange={handleDirectoryChange}
        style={{ display: 'none' }}
      />

      {/* Control Section (Top) */}
      <fieldset className="p-4 border border-gray-200/50 dark:border-gray-700/50 rounded-lg shadow-sm">
        <legend className="px-2 font-semibold dark:text-gray-200">Scan Directory & Batch Actions</legend>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Select a directory to scan for images. Found: {images.length} images.
        </p>
        <button
          onClick={handleBrowseDirectory}
          className="flex items-center justify-center w-full px-4 py-3 my-2 font-bold text-white transition-all duration-200 transform rounded-md shadow-lg bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 hover:scale-105 disabled:bg-gray-400 disabled:from-gray-400 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          {isLoading ? (
            <RefreshCcw size={20} className="mr-2 animate-spin" />
          ) : (
            <FolderOpen size={20} className="mr-2" />
          )}
          {isLoading ? "Scanning..." : "Choose Directory to Scan"}
        </button>
      </fieldset>
      
      {/* Open Window Button */}
      <button 
        onClick={viewSelectedImages}
        className="w-full px-4 py-2 my-4 font-medium text-white transition-colors bg-indigo-500 rounded-md shadow-sm hover:bg-indigo-600 disabled:bg-gray-400/50 disabled:cursor-not-allowed"
        disabled={selectedCount === 0 || isLoading}
      >
        Open Full Size Image Window(s) ({selectedCount} Selected)
      </button>

      {/* Paginated Image Grid Container */}
      {/* Removed flex-grow here to prevent unwanted stretching/pushing of content */}
      <div className="flex flex-col"> 
        {/* Image Grid Area - Fixed height and background */}
        <div className="mt-2 h-[580px] bg-gray-100 rounded-lg shadow-inner dark:bg-gray-800/50"> 
          {isLoading && <div className="flex items-center justify-center h-full"><Loader2 className="animate-spin text-violet-500" size={32} /></div>}
          {!isLoading && images.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
              <ImageIcon size={48} className="mb-2" />
              <span>Click "Choose Directory" to see images.</span>
            </div>
          )}
          
          {/* Image Grid - p-4 for inner padding, h-full to fit parent */}
          <div className="p-4 grid grid-cols-5 gap-4 h-full -ml-4">
            {currentImages.map(img => (
              <div
                key={img.path}
                onClick={() => handleToggleSelect(img.path)}
                onDoubleClick={viewSelectedImages}
                title={img.path}
                className={`relative w-full overflow-hidden rounded-lg shadow-md cursor-pointer aspect-square transition-all duration-200 ease-in-out
                  ${img.selected ? 'ring-4 ring-offset-2 ring-violet-500 scale-105 shadow-xl' : 'ring-0 shadow-md hover:shadow-lg'}
                `}
              >
                <img 
                  src={img.blobUrl} 
                  alt={img.name} 
                  className="object-cover w-full h-full" 
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.parentElement.style.backgroundColor = '#6d28d9'; 
                    e.target.parentElement.textContent = 'File Error'; 
                  }}
                />
                {img.selected && (
                  <div className="absolute top-0 right-0 p-1 bg-violet-600 rounded-bl-lg">
                    <Check size={16} className="text-white" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Pagination Controls (Added px-4 back for alignment with outer elements) */}
        <div className="flex justify-between items-center py-3 px-4">
          <span className="text-sm dark:text-gray-400">
            Showing {startIndex + 1} - {Math.min(endIndex, images.length)} of {images.length} images.
          </span>
          {renderPaginationButtons()}
        </div>
      </div>
      
      {/* --- BUTTONS SECTION (Bottom) --- */}
      <div className="flex flex-col gap-3 pt-4 sm:flex-row">
        <button 
          onClick={handleAddSelectedToDb}
          className="flex-1 flex items-center justify-center px-4 py-2 font-semibold text-white transition-colors bg-green-600 rounded-md shadow-sm hover:bg-green-700 disabled:bg-gray-400/50 disabled:cursor-not-allowed"
          disabled={selectedCount === 0 || isLoading}
        >
          <Plus size={18} className="mr-2" /> Add {selectedCount} Selected to DB
        </button>
        <button 
          onClick={handleUpdateSelected}
          className="flex-1 flex items-center justify-center px-4 py-2 font-semibold text-white transition-colors bg-blue-600 rounded-md shadow-sm hover:bg-blue-700 disabled:bg-gray-400/50 disabled:cursor-not-allowed"
          disabled={selectedCount === 0 || isLoading}
        >
          <PenSquare size={18} className="mr-2" /> Update {selectedCount} Selected
        </button>
        <button 
          onClick={handleRefreshDirectory} 
          className="flex-1 flex items-center justify-center px-4 py-2 font-semibold text-white transition-colors bg-yellow-500 rounded-md shadow-sm hover:bg-yellow-600 disabled:bg-gray-400/50 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          <RefreshCcw size={18} className="mr-2" /> Refresh Image Directory 
        </button>
        <button 
          onClick={handleDeleteSelected}
          className="flex-1 flex items-center justify-center px-4 py-2 font-semibold text-white transition-colors bg-red-600 rounded-md shadow-sm hover:bg-red-700 disabled:bg-gray-400/50 disabled:cursor-not-allowed"
          disabled={selectedCount === 0 || isLoading}
        >
          <Trash2 size={18} className="mr-2" /> Remove {selectedCount} Selected
        </button>
      </div>
    </div>
  );
});

ScanFSETab.displayName = 'ScanFSETab';
export default ScanFSETab;
