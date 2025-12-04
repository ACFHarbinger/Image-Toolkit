import React, { forwardRef, useState, useImperativeHandle, useEffect, useRef, useCallback } from 'react';
import { RefreshCcw, FolderOpen, Loader2, Image as ImageIcon, Trash2, Plus, PenSquare, X, Minus, Maximize2, Minimize2, Check, ChevronLeft, ChevronRight } from 'lucide-react';

// Components
import { ClickableLabel } from '../../components/ClickableLabel.tsx';
import { MarqueeScrollArea } from '../../components/MarqueeScrollArea.tsx';
import { useTwoGalleries } from '../../hooks/useTwoGalleries.ts';
import { GalleryItem } from '../../hooks/galleryItem.ts';

// --- Interfaces ---

interface FloatingWindowProps {
  windowId: number;
  initialImageSrc: string | null;
  initialTitle: string;
  onClose: (id: number) => void;
  onMinimize: (id: number) => void;
  isMinimized: boolean;
  onMaximize: (id: number) => void;
  isMaximized: boolean;
  onBringToFront: (id: number) => void;
}

interface WindowData {
  id: number;
  path: string;
  src: string | null;
  title: string;
  isMinimized: boolean;
  isMaximized: boolean;
}

interface ScanMetadataTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error', duration?: number) => void;
  onAddImagesToDb: (files: File[]) => void;
}

export interface ScanMetadataTabHandle {
  getData: () => {
    action: string;
    selected_images: string[];
  };
  refresh: () => void;
}

// --- Utility function ---
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = error => reject(error);
    reader.readAsDataURL(file);
  });
};

// --- Helper Component: Pagination Bar ---
const PaginationBar = ({ 
  currentPage, 
  totalPages, 
  itemsPerPage,
  totalItems,
  onPageChange, 
  onItemsPerPageChange,
  onPrev, 
  onNext 
}: { 
  currentPage: number, 
  totalPages: number, 
  itemsPerPage: number,
  totalItems: number,
  onPageChange: (page: number) => void, 
  onItemsPerPageChange: (size: number) => void,
  onPrev: () => void, 
  onNext: () => void 
}) => {
  const startIndex = (currentPage * itemsPerPage) + 1;
  const endIndex = Math.min(startIndex + itemsPerPage - 1, totalItems);

  return (
    <div className="flex items-center justify-between w-full px-2">
        <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">Per page:</span>
            <select 
              className="border rounded p-1 text-xs dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
              value={itemsPerPage}
              onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={300}>300</option>
            </select>
        </div>

        <div className="flex items-center justify-center gap-2">
            <button 
                onClick={onPrev} 
                disabled={currentPage === 0} 
                className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 transition-colors"
                title="Previous Page"
            >
                <ChevronLeft size={16}/>
            </button>
            
            <div className="relative">
                <select 
                    value={currentPage} 
                    onChange={(e) => onPageChange(Number(e.target.value))}
                    className="appearance-none py-1 pl-3 pr-8 text-xs font-medium border rounded bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 outline-none focus:ring-2 focus:ring-violet-500 cursor-pointer shadow-sm min-w-[100px] text-center"
                >
                    {Array.from({ length: Math.max(1, totalPages) }, (_, i) => (
                        <option key={i} value={i}>
                            Page {i + 1} / {totalPages || 1}
                        </option>
                    ))}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500 dark:text-gray-400">
                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                </div>
            </div>

            <button 
                onClick={onNext} 
                disabled={currentPage >= totalPages - 1} 
                className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 transition-colors"
                title="Next Page"
            >
                <ChevronRight size={16}/>
            </button>
        </div>
        
        {/* Added image count display for balanced look */}
        <span className="text-xs text-gray-500 dark:text-gray-400 w-[100px] text-right">
            {totalItems > 0 ? `${startIndex}-${endIndex} of ${totalItems}` : '0 images'}
        </span>
    </div>
  );
};

// --- Floating Image Window Component ---
const FloatingImageWindow: React.FC<FloatingWindowProps> = ({ 
  windowId, initialImageSrc, initialTitle, onClose, onMinimize, isMinimized, onMaximize, isMaximized, onBringToFront 
}) => {
  const [position, setPosition] = useState<{ x: number, y: number }>({ x: 50 + (windowId * 20), y: 50 + (windowId * 20) });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [offset, setOffset] = useState<{ x: number, y: number }>({ x: 0, y: 0 });
  const windowRef = useRef<HTMLDivElement>(null);
  
  // Custom Hook for Draggability
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
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

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.window-controls')) return;
    onBringToFront(windowId);
    if (isMaximized) return;

    if (windowRef.current) {
        const rect = windowRef.current.getBoundingClientRect();
        setOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        setIsDragging(true);
    }
  };
  
  const windowStyle: React.CSSProperties = isMaximized ? {
    top: 0, left: 0, width: '100vw', height: '100vh', 
    transition: 'all 0.3s ease-in-out', zIndex: 9999 + windowId, position: 'fixed'
  } : {
    top: position.y, left: position.x, 
    transform: isDragging ? 'scale(1.02)' : 'scale(1)',
    transition: isDragging ? 'none' : 'transform 0.1s ease-out',
    zIndex: 100 + windowId, 
  };

  const contentStyle: React.CSSProperties = isMinimized ? { display: 'none' } : { display: 'flex' };

  return (
    <div
      ref={windowRef}
      className={`fixed rounded-lg shadow-2xl bg-white dark:bg-gray-800 backdrop-blur-sm flex flex-col overflow-hidden min-w-[300px] min-h-[150px] transition-transform ${isMaximized ? 'rounded-none' : 'w-[500px] h-[400px]'}`}
      style={windowStyle}
      onClick={() => onBringToFront(windowId)}
    >
      <div 
        className={`flex items-center justify-between p-2 font-semibold text-sm cursor-grab ${isDragging ? 'cursor-grabbing' : 'cursor-grab'} ${isMaximized ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
        onMouseDown={handleMouseDown}
      >
        <span className={`${isMaximized ? 'text-white' : 'dark:text-gray-200'}`}>
          {isMinimized ? `[M] ${initialTitle}` : initialTitle}
        </span>
        <div className="flex space-x-2 window-controls">
          <button onClick={() => onMinimize(windowId)} className="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600">
            <Minus size={14} className="dark:text-white" />
          </button>
          <button onClick={() => onMaximize(windowId)} className="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600">
            {isMaximized ? <Minimize2 size={14} className="dark:text-white" /> : <Maximize2 size={14} className="dark:text-white" />}
          </button>
          <button onClick={() => onClose(windowId)} className="p-1 rounded hover:bg-red-500 hover:text-white">
            <X size={14} className="dark:text-white" />
          </button>
        </div>
      </div>
      <div className="flex-grow flex items-center justify-center p-4 overflow-auto" style={contentStyle}>
        {initialImageSrc && <img src={initialImageSrc} alt={initialTitle} className="max-w-none w-auto h-auto rounded-lg shadow-xl" />}
      </div>
      {isMinimized && (
        <div 
          className="absolute bottom-0 left-0 right-0 p-2 bg-gray-900/90 text-white text-center cursor-pointer"
          onClick={() => onMinimize(windowId)}
        >
          {initialTitle} (Minimized)
        </div>
      )}
    </div>
  );
};


// --- ScanMetadataTab Component ---

const ScanMetadataTab = forwardRef<ScanMetadataTabHandle, ScanMetadataTabProps>(({ showModal, onAddImagesToDb }, ref) => {
  // Use the Two Galleries Hook
  const { found, selected, actions } = useTwoGalleries(20, 20); // 20 items per page

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [openWindows, setOpenWindows] = useState<WindowData[]>([]); 
  
  // Refs/State for Output Directory
  const outputDirectoryInputRef = useRef<HTMLInputElement>(null);
  const [outputDir, setOutputDir] = useState<string>('');

  // Refs to store data that isn't strictly needed for UI rendering but needed for logic
  const directoryInputRef = useRef<HTMLInputElement>(null);
  const fileMap = useRef<Record<string, File>>({});
  const base64Cache = useRef<Record<string, string>>({});

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'scan_and_select',
      selected_images: Array.from(selected.items).map(img => img.path),
    }),
    refresh: handleBrowseDirectory,
  }));

  // --- Handlers ---

  const handleBrowseDirectory = () => {
    if (directoryInputRef.current) {
        directoryInputRef.current.click();
    }
  };

  const handleBrowseOutputDirectory = () => {
    if (outputDirectoryInputRef.current) {
        outputDirectoryInputRef.current.click();
    }
  };

  const handleOutputDirectoryChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) return;
    
    // Get the base directory path (assuming webkitRelativePath for directory scanning)
    const file = event.target.files[0];
    const pathParts = file.webkitRelativePath.split('/');
    const dirName = pathParts.length > 1 ? pathParts[0] : file.name;
    
    setOutputDir(dirName);
    showModal(`Output directory set to: ${dirName}`, "info", 2000);
  };
  
  const handleDirectoryChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) {
      showModal("No directory selected.", "info");
      return;
    }

    setIsLoading(true);
    
    // Revoke old URLs
    found.items.forEach(img => img.thumbnail && URL.revokeObjectURL(img.thumbnail));
    
    // Reset State
    actions.deselectAll();
    found.actions.setGalleryItems([]);
    fileMap.current = {};
    base64Cache.current = {};
    setOpenWindows([]);

    const files = Array.from(event.target.files);
    // FIX: Removed .slice(0, 500) to scan ALL images
    const imageFiles = files.filter(file => file.type.startsWith('image/'));

    if (imageFiles.length === 0) {
      showModal(`Scan complete! No images found.`, 'info', 2000);
      setIsLoading(false);
      return;
    }

    const newGalleryItems: GalleryItem[] = imageFiles.map(file => {
      const blobUrl = URL.createObjectURL(file);
      const path = file.webkitRelativePath || file.name;
      
      // Store File object in ref for later use
      fileMap.current[path] = file;

      return {
        path: path,
        thumbnail: blobUrl,
        isVideo: false
      };
    });

    found.actions.setGalleryItems(newGalleryItems);
    setIsLoading(false);
    showModal(`Scan complete! Found ${newGalleryItems.length} images.`, 'success', 2000);
  };

  // Clean up blob URLs
  useEffect(() => {
    return () => {
      found.items.forEach(img => img.thumbnail && URL.revokeObjectURL(img.thumbnail));
    };
  }, [found.items]);

  const handleRefreshDirectory = () => {
    // Revoke
    found.items.forEach(img => img.thumbnail && URL.revokeObjectURL(img.thumbnail));
    // Clear
    found.actions.setGalleryItems([]);
    actions.deselectAll();
    fileMap.current = {};
    setOpenWindows([]);
    showModal("Directory preview cleared.", "info", 2000);
  };
  
  // --- Window Management ---

  const handleWindowClose = useCallback((id: number) => setOpenWindows(p => p.filter(w => w.id !== id)), []);
  const handleWindowMinimize = useCallback((id: number) => setOpenWindows(p => p.map(w => w.id === id ? { ...w, isMinimized: !w.isMinimized } : w)), []);
  const handleWindowMaximize = useCallback((id: number) => setOpenWindows(p => p.map(w => w.id === id ? { ...w, isMaximized: !w.isMaximized } : w)), []);
  
  const handleBringToFront = useCallback((id: number) => {
    setOpenWindows(prev => {
      const idx = prev.findIndex(w => w.id === id);
      if (idx === -1 || idx === prev.length - 1) return prev;
      const win = prev[idx];
      const rest = prev.filter(w => w.id !== id);
      return [...rest, win].map((w, i) => ({ ...w, id: i }));
    });
  }, []);

  const viewSelectedImages = async () => {
    // Use selected gallery items
    const targets = selected.items;
    
    if (targets.length === 0) {
      showModal("Please select one or more images to view from the Selected Gallery.", "error");
      return;
    }
    
    setIsLoading(true); 

    for (const item of targets) {
      if (openWindows.some(w => w.path === item.path)) continue;
      
      let imageSrc = base64Cache.current[item.path];
      
      if (!imageSrc) {
        const file = fileMap.current[item.path];
        if (file) {
            try {
                imageSrc = await fileToBase64(file);
                base64Cache.current[item.path] = imageSrc;
            } catch(e: any) {
                console.error("Failed to load base64", e);
            }
        }
      }

      if (imageSrc) {
        setOpenWindows(prev => [...prev, {
          id: prev.length,
          path: item.path,
          src: imageSrc,
          title: item.path.split('/').pop() || item.path,
          isMinimized: false,
          isMaximized: false,
        }]);
      }
    }
    setIsLoading(false);
  };
  
  // --- Batch Actions ---

  const handleAddSelectedToDb = () => {
    if (!outputDir) {
        showModal("Please select an output directory before adding to DB.", "error");
        return;
    }
    const filesToAdd: File[] = [];
    selected.items.forEach(item => {
        const file = fileMap.current[item.path];
        if (file) filesToAdd.push(file);
    });

    if (filesToAdd.length > 0) {
      // Simulate adding to DB using the selected output directory
      onAddImagesToDb(filesToAdd); 
      showModal(`Adding ${filesToAdd.length} images to database and saving output metadata to ${outputDir}...`, "success");
      actions.deselectAll(); // Clear selection after add
    } else {
      showModal("No images in Selected Gallery to add.", "error");
    }
  };
  
  const handleUpdateSelected = () => {
     if (selected.items.length > 0) {
        showModal(`Simulating update for ${selected.items.length} images.`, "info");
     } else {
        showModal("No images selected.", "error");
     }
  };

  return (
    // The main container is scrollable via the parent App.tsx main tag.
    <div className="flex flex-col h-full p-4 gap-4 dark:bg-gray-900/50">
      {/* Windows */}
      {openWindows.map(w => (
        <FloatingImageWindow key={w.id} windowId={w.id} initialImageSrc={w.src} initialTitle={w.title} onClose={handleWindowClose} onMinimize={handleWindowMinimize} isMinimized={w.isMinimized} onMaximize={handleWindowMaximize} isMaximized={w.isMaximized} onBringToFront={handleBringToFront} />
      ))}

      {/* Hidden file inputs */}
      <input type="file" 
        // @ts-ignore
        webkitdirectory="true" multiple ref={directoryInputRef} onChange={handleDirectoryChange} style={{ display: 'none' }} />
      <input type="file" 
        // @ts-ignore
        webkitdirectory="true" multiple ref={outputDirectoryInputRef} onChange={handleOutputDirectoryChange} style={{ display: 'none' }} />


      {/* Main Content: Split View for Two Galleries */}
      <div className="flex flex-col gap-4"> 
        
        {/* Found Gallery (Source) */}
        <div className="flex flex-col border rounded-lg bg-white dark:bg-gray-800 shadow-sm" style={{minHeight: '400px'}}>
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
                <h3 className="font-bold flex items-center gap-2">
                    <FolderOpen size={16} /> Found Images ({found.items.length})
                </h3>
                <div className="flex items-center gap-2">
                    <button onClick={actions.selectAllFoundPage} className="text-xs text-blue-600 hover:underline">Select Page</button>
                </div>
            </div>
            
            <div className="flex-1 relative" style={{ minHeight: '300px' }}>
                <MarqueeScrollArea onSelectionChanged={(set, isCtrl) => found.actions.selectBatch(set, isCtrl)}>
                    <div className="flex flex-wrap content-start p-2 gap-2">
                        {found.paginatedItems.map((item, idx) => (
                            <ClickableLabel
                                key={item.path + idx}
                                path={item.path}
                                src={item.thumbnail}
                                isSelected={found.selectedPaths.has(item.path)}
                                onPathClicked={() => actions.toggleSelection(item)}
                                onPathDoubleClicked={viewSelectedImages}
                            />
                        ))}
                         {found.items.length === 0 && (
                            <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 mt-10">
                                <ImageIcon size={48} className="mb-2 opacity-50" />
                                <span>No images found.</span>
                            </div>
                        )}
                    </div>
                </MarqueeScrollArea>
            </div>

            {/* Found Pagination */}
            <div className="p-2 border-t dark:border-gray-700 flex justify-center items-center text-sm bg-gray-50 dark:bg-gray-900/50">
                 <PaginationBar 
                    currentPage={found.pagination.currentPage}
                    totalPages={found.pagination.totalPages}
                    itemsPerPage={found.pagination.itemsPerPage}
                    totalItems={found.items.length} 
                    onPageChange={found.pagination.setCurrentPage}
                    onItemsPerPageChange={found.pagination.setItemsPerPage}
                    onPrev={found.pagination.prevPage}
                    onNext={found.pagination.nextPage}
                 />
            </div>
        </div>

        {/* Found Actions (Below Pagination) */}
        <div className="flex gap-4 items-center mt-2 flex-shrink-0">
            <button
            onClick={handleBrowseDirectory}
            className="flex-1 flex items-center justify-center px-4 py-2 font-bold text-white rounded-md bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 disabled:opacity-50"
            disabled={isLoading}
            >
            {isLoading ? <Loader2 className="animate-spin mr-2"/> : <FolderOpen className="mr-2"/>}
            {isLoading ? "Scanning..." : "Scan Directory"}
            </button>
            <button onClick={handleRefreshDirectory} className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600" title="Clear All">
                <RefreshCcw size={20} />
            </button>
        </div>

        {/* Selected Gallery (Target) */}
        <div className="flex flex-col border rounded-lg bg-white dark:bg-gray-800 shadow-sm flex-shrink-0" style={{ minHeight: '150px' }}>
             <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-indigo-50 dark:bg-gray-900/50">
                <h3 className="font-bold flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
                    <Check size={16} /> Selected Images ({selected.items.length})
                </h3>
                {selected.selectedPaths.size > 0 && (
                    <button onClick={actions.removeSelectedTargets} className="text-xs text-red-600 hover:text-red-700 flex items-center gap-1">
                        <Trash2 size={12} /> Remove Highlighted
                    </button>
                )}
            </div>

            <div className="flex-1 relative min-h-0">
                <MarqueeScrollArea onSelectionChanged={(set, isCtrl) => selected.actions.selectBatch(set, isCtrl)}>
                     <div className="flex flex-wrap content-start p-2 gap-2">
                        {selected.paginatedItems.map((item, idx) => (
                            <ClickableLabel
                                key={item.path + idx}
                                path={item.path}
                                src={item.thumbnail}
                                isSelected={selected.selectedPaths.has(item.path)}
                                onPathClicked={(path) => selected.actions.selectItem(path, true)} // Highlight inside selected gallery
                            />
                        ))}
                        {selected.items.length === 0 && (
                            <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm italic">
                                Click images above to select them.
                            </div>
                        )}
                    </div>
                </MarqueeScrollArea>
            </div>
            
             {/* Selected Pagination */}
            <div className="p-2 border-t dark:border-gray-700 flex justify-center items-center text-sm bg-gray-50 dark:bg-gray-900/50">
                 <PaginationBar 
                    currentPage={selected.pagination.currentPage}
                    totalPages={selected.pagination.totalPages}
                    itemsPerPage={selected.pagination.itemsPerPage}
                    totalItems={selected.items.length} 
                    onPageChange={selected.pagination.setCurrentPage}
                    onItemsPerPageChange={selected.pagination.setItemsPerPage}
                    onPrev={selected.pagination.prevPage}
                    onNext={selected.pagination.nextPage}
                 />
            </div>
        </div>

        {/* Output Directory Field */}
        <div className="flex gap-4 items-center flex-shrink-0">
            <input 
                type="text"
                value={outputDir || 'No output directory selected'}
                readOnly
                className="flex-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600 text-sm read-only:bg-gray-100 dark:read-only:bg-gray-700/50"
            />
            <button 
                onClick={handleBrowseOutputDirectory}
                className="px-4 py-2 font-semibold text-white bg-gray-600 rounded hover:bg-gray-700 disabled:opacity-50"
                disabled={isLoading}
            >
                <FolderOpen size={20} className="inline mr-2" /> Output Dir
            </button>
        </div>


      </div>

      {/* Selected Actions (Final Bottom Bar) */}
      <div className="flex gap-2 pb-4 pt-2 border-t dark:border-gray-700 flex-shrink-0">
        <button 
          onClick={viewSelectedImages}
          className="flex-1 px-4 py-2 font-semibold text-white bg-indigo-500 rounded hover:bg-indigo-600 disabled:opacity-50"
          disabled={selected.items.length === 0}
        >
          <Maximize2 size={16} className="inline mr-2" /> View Full Size
        </button>
        <button 
          onClick={handleAddSelectedToDb}
          className="flex-1 px-4 py-2 font-semibold text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
          disabled={selected.items.length === 0}
        >
          <Plus size={16} className="inline mr-2" /> Add to DB
        </button>
        <button 
          onClick={handleUpdateSelected}
          className="flex-1 px-4 py-2 font-semibold text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
          disabled={selected.items.length === 0}
        >
          <PenSquare size={16} className="inline mr-2" /> Update Meta
        </button>
        <button 
            onClick={actions.deselectAll}
            className="flex-1 px-4 py-2 font-semibold text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
            disabled={selected.items.length === 0}
        >
            <Trash2 size={16} className="inline mr-2" /> Clear Selection
        </button>
      </div>
    </div>
  );
});

export default ScanMetadataTab;