import React, { forwardRef, useState, useImperativeHandle, useRef } from 'react';
import { Trash2, AlertTriangle, FolderOpen, ChevronLeft, ChevronRight, FileSearch } from 'lucide-react';

// Components
import { ClickableLabel } from '../../components/ClickableLabel.tsx';
import { MarqueeScrollArea } from '../../components/MarqueeScrollArea.tsx';
import { useTwoGalleries } from '../../hooks/useTwoGalleries.ts';
import { GalleryItem } from '../../hooks/galleryItem.ts';

interface DeleteTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error', duration?: number) => void;
}

export interface DeleteTabHandle {
  getData: () => any;
}

// --- Helper: Pagination Bar ---
const PaginationBar = ({ 
  currentPage, 
  totalPages, 
  onPageChange, 
  onPrev, 
  onNext 
}: { 
  currentPage: number, 
  totalPages: number, 
  onPageChange: (page: number) => void, 
  onPrev: () => void, 
  onNext: () => void 
}) => {
  return (
    <div className="flex items-center justify-center gap-2 p-2 bg-gray-50 dark:bg-gray-900/50 border-t dark:border-gray-700">
        <button onClick={onPrev} disabled={currentPage === 0} className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"><ChevronLeft size={16}/></button>
        <span className="text-xs font-mono text-gray-600 dark:text-gray-400">Page {currentPage + 1} / {totalPages || 1}</span>
        <button onClick={onNext} disabled={currentPage >= totalPages - 1} className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"><ChevronRight size={16}/></button>
    </div>
  );
};

const DeleteTab = forwardRef<DeleteTabHandle, DeleteTabProps>(({ showModal }, ref) => {
  const { found, selected, actions } = useTwoGalleries(50, 50);

  const [targetPath, setTargetPath] = useState('');
  const [scanMethod, setScanMethod] = useState('All Files (List Directory Contents)');
  const [extensions, setExtensions] = useState('');
  const [requireConfirm, setRequireConfirm] = useState(true);
  
  const inputDirRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'delete',
      target_path: targetPath,
      selected_files: Array.from(selected.items).map(i => i.path),
      options: { scanMethod, extensions, requireConfirm }
    }),
  }));

  const handleBrowse = () => inputDirRef.current?.click();

  const handleScan = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const path = e.target.files[0].webkitRelativePath.split('/')[0] || "Selected Directory";
      setTargetPath(path);
      
      // Simulate Scan
      const images: GalleryItem[] = Array.from(e.target.files)
        .filter(f => f.type.startsWith('image/'))
        .map(f => ({ path: f.name, thumbnail: URL.createObjectURL(f) }));
      
      found.actions.setGalleryItems(images);
      showModal(`Scan complete. Found ${images.length} items.`, "success");
    }
  };

  const handleDeleteDirectory = () => {
    if (!targetPath) return showModal("No target path selected.", "error");
    showModal(`Simulating directory deletion: ${targetPath}`, "error");
  };

  const handleDeleteSelected = () => {
    if (selected.items.length === 0) return showModal("No files selected.", "error");
    showModal(`Simulating deletion of ${selected.items.length} files...`, "error");
  };

  return (
    <div className="flex flex-col h-full p-4 gap-4 bg-gray-50 dark:bg-gray-900 overflow-hidden">
      <input type="file" ref={inputDirRef} onChange={handleScan} className="hidden" 
        // @ts-ignore
        webkitdirectory="true" multiple 
      />

      {/* 1. Settings */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex-shrink-0">
        <h3 className="font-bold text-red-600 dark:text-red-400 mb-4 flex items-center gap-2">
            <Trash2 size={18}/> Delete Targets & Settings
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex gap-2">
                <input type="text" placeholder="Target path to delete or scan..." readOnly value={targetPath} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
                <button onClick={handleBrowse} className="px-3 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded"><FolderOpen size={16}/></button>
            </div>
            <select value={scanMethod} onChange={e => setScanMethod(e.target.value)} className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600">
                <option>All Files (List Directory Contents)</option>
                <option>Exact Match (Same File)</option>
                <option>Similar: Perceptual Hash</option>
                <option>Similar: SSIM</option>
            </select>
            <input type="text" placeholder="Target extensions (e.g. .jpg .png)" value={extensions} onChange={e => setExtensions(e.target.value)} className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
            <label className="flex items-center gap-2 text-sm select-none"><input type="checkbox" checked={requireConfirm} onChange={e => setRequireConfirm(e.target.checked)} className="text-red-500"/> Require confirmation</label>
        </div>
      </div>

      {/* 2. Galleries */}
      <div className="flex-1 flex flex-col min-h-0 gap-4">
        {/* Found Duplicates */}
        <div className="flex-1 flex flex-col min-h-0 border rounded-lg bg-white dark:bg-gray-800 shadow-sm">
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
                <span className="font-bold text-sm flex items-center gap-2"><FileSearch size={16}/> Found Files / Duplicates ({found.items.length})</span>
                <button onClick={actions.selectAllFoundPage} className="text-xs text-blue-600 hover:underline">Select Page</button>
            </div>
            <div className="flex-1 relative min-h-0">
                <MarqueeScrollArea onSelectionChanged={(set, isCtrl) => found.actions.selectBatch(set, isCtrl)}>
                    <div className="flex flex-wrap content-start p-2 gap-2">
                        {found.paginatedItems.map((item, idx) => (
                            <ClickableLabel key={item.path + idx} path={item.path} src={item.thumbnail} isSelected={found.selectedPaths.has(item.path)} onPathClicked={() => actions.toggleSelection(item)} />
                        ))}
                        {found.items.length === 0 && <div className="w-full h-full flex items-center justify-center text-gray-400">No scan results.</div>}
                    </div>
                </MarqueeScrollArea>
            </div>
            <PaginationBar currentPage={found.pagination.currentPage} totalPages={found.pagination.totalPages} onPageChange={found.pagination.setCurrentPage} onPrev={found.pagination.prevPage} onNext={found.pagination.nextPage}/>
        </div>

        {/* Selected for Deletion */}
        <div className="flex flex-col border rounded-lg bg-white dark:bg-gray-800 shadow-sm flex-shrink-0" style={{ minHeight: '150px' }}>
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-red-50 dark:bg-red-900/20">
                <span className="font-bold text-sm text-red-700 dark:text-red-400 flex items-center gap-2"><AlertTriangle size={16}/> Selected for Deletion ({selected.items.length})</span>
                <button onClick={actions.deselectAll} className="text-xs text-red-600 hover:underline">Clear Selection</button>
            </div>
            <div className="flex-1 relative min-h-0">
                <MarqueeScrollArea onSelectionChanged={(set, isCtrl) => selected.actions.selectBatch(set, isCtrl)}>
                    <div className="flex flex-wrap content-start p-2 gap-2">
                        {selected.paginatedItems.map((item, idx) => (
                            <ClickableLabel key={item.path + idx} path={item.path} src={item.thumbnail} isSelected={selected.selectedPaths.has(item.path)} onPathClicked={(path) => selected.actions.selectItem(path, true)} />
                        ))}
                        {selected.items.length === 0 && <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">No files marked for deletion.</div>}
                    </div>
                </MarqueeScrollArea>
            </div>
            <PaginationBar currentPage={selected.pagination.currentPage} totalPages={selected.pagination.totalPages} onPageChange={selected.pagination.setCurrentPage} onPrev={selected.pagination.prevPage} onNext={selected.pagination.nextPage}/>
        </div>
      </div>

      {/* 3. Actions */}
      <div className="flex gap-2 pb-2 flex-shrink-0">
        <button onClick={handleDeleteDirectory} className="flex-1 py-3 bg-red-800 text-white rounded shadow-md hover:bg-red-900 font-bold disabled:opacity-50">Delete Directory & Contents</button>
        <button onClick={handleDeleteSelected} className="flex-1 py-3 bg-gradient-to-r from-red-500 to-orange-600 text-white rounded shadow-md hover:from-red-600 hover:to-orange-700 font-bold disabled:opacity-50" disabled={selected.items.length === 0}>Delete Selected Files ({selected.items.length})</button>
      </div>
    </div>
  );
});

export default DeleteTab;