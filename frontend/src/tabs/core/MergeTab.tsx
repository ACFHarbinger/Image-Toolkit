import React, {
  forwardRef,
  useState,
  useImperativeHandle,
  useRef,
} from "react";
import {
  LayoutGrid,
  FolderOpen,
  FileOutput,
  CheckSquare,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

// Components
import { ClickableLabel } from "../../components/ClickableLabel";
import { MarqueeScrollArea } from "../../components/MarqueeScrollArea";
import { useTwoGalleries } from "../../hooks/useTwoGalleries";
import { GalleryItem } from "../../hooks/galleryItem";

interface MergeTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

export interface MergeTabHandle {
  getData: () => any;
}

// --- Helper: Pagination Bar ---
const PaginationBar = ({
  currentPage,
  totalPages,
  onPageChange,
  onPrev,
  onNext,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPrev: () => void;
  onNext: () => void;
}) => {
  return (
    <div className="flex items-center justify-center gap-2 p-2 bg-gray-50 dark:bg-gray-900/50 border-t dark:border-gray-700">
      <button
        onClick={onPrev}
        disabled={currentPage === 0}
        className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"
      >
        <ChevronLeft size={16} />
      </button>
      <span className="text-xs font-mono text-gray-600 dark:text-gray-400">
        Page {currentPage + 1} / {totalPages || 1}
      </span>
      <button
        onClick={onNext}
        disabled={currentPage >= totalPages - 1}
        className="p-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
};

const MergeTab = forwardRef<MergeTabHandle, MergeTabProps>(
  ({ showModal }, ref) => {
    const { found, selected, actions } = useTwoGalleries(50, 50);

    const [scanDir, setScanDir] = useState("");
    const [outputDir, setOutputDir] = useState("");
    const [outputFilename, setOutputFilename] = useState("");
    const [direction, setDirection] = useState("horizontal");
    const [spacing, setSpacing] = useState(10);
    const [alignMode, setAlignMode] = useState("center");
    const [gridRows, setGridRows] = useState(2);
    const [gridCols, setGridCols] = useState(2);
    const [duration, setDuration] = useState(500);

    const inputDirRef = useRef<HTMLInputElement>(null);
    const outputDirRef = useRef<HTMLInputElement>(null);

    useImperativeHandle(ref, () => ({
      getData: () => ({
        action: "merge",
        config: {
          scanDir,
          outputDir,
          outputFilename,
          direction,
          spacing,
          alignMode,
          gridRows,
          gridCols,
          duration,
        },
        selected_files: Array.from(selected.items).map((i: any) => i.path),
      }),
    }));

    const handleBrowseInput = async () => {
      try {
        const dir = (await open({ directory: true, multiple: false })) as
          | string
          | null;
        if (dir) {
          setScanDir(dir);
          // Auto scan
          const files =
            (await invoke<string[]>("scan_files", {
              directory: dir,
              recursive: false,
            })) || [];

          const images: GalleryItem[] = files.map((p) => ({
            path: p,
            thumbnail: convertFileSrc(p),
            isVideo: false,
          }));
          found.actions.setGalleryItems(images);
          showModal(`Found ${images.length} images.`, "info");
        }
      } catch (err) {
        console.error(err);
      }
    };

    const handleBrowseOutput = async () => {
      try {
        const dir = (await open({ directory: true, multiple: false })) as
          | string
          | null;
        if (dir) setOutputDir(dir);
      } catch (err) {
        console.error(err);
      }
    };

    // Legacy handler
    const handleScan = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        const path =
          e.target.files[0].webkitRelativePath.split("/")[0] ||
          "Selected Directory";
        setScanDir(path);
      }
    };

    const handleRunMerge = async () => {
      if (selected.items.length < 2)
        return showModal("Select at least 2 images to merge.", "error");
      if (!outputDir)
        return showModal("Please select an output directory.", "error");

      const filename = outputFilename || `merged_${Date.now()}.png`;
      const sep = outputDir.includes("\\") ? "\\" : "/";
      const fullOutputPath = `${outputDir}${sep}${filename}`;

      try {
        showModal(`Merging ${selected.items.length} images...`, "info");
        const paths = selected.items.map((i) => i.path);

        const config = {
          direction,
          spacing,
          alignMode,
          gridRows,
          gridCols,
          duration, // For GIF if implemented later
        };

        const success = await invoke<boolean>("merge_images", {
          imagePaths: paths,
          outputPath: fullOutputPath,
          config,
        });

        if (success) {
          showModal(`Merge complete: ${filename}`, "success");
        } else {
          showModal("Merge failed (unknown error).", "error");
        }
      } catch (err) {
        console.error(err);
        showModal(`Merge error: ${err}`, "error");
      }
    };

    return (
      <div className="flex flex-col h-full p-4 gap-4 bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <input
          type="file"
          ref={inputDirRef}
          onChange={handleScan}
          className="hidden"
          // @ts-ignore
          webkitdirectory="true"
          multiple
        />
        <input
          type="file"
          ref={outputDirRef}
          onChange={(e) => {
            if (e.target.files) setOutputDir("Selected Output");
          }}
          className="hidden"
          // @ts-ignore
          webkitdirectory="true"
        />

        {/* 1. Config */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
            <LayoutGrid size={18} className="text-violet-500" /> Merge Settings
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Input/Output Group */}
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Input Directory..."
                  readOnly
                  value={scanDir}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <button
                  onClick={handleBrowseInput}
                  className="px-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded"
                >
                  <FolderOpen size={16} />
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Output Directory..."
                  readOnly
                  value={outputDir}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <button
                  onClick={handleBrowseOutput}
                  className="px-3 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded"
                >
                  <FileOutput size={16} />
                </button>
              </div>
              <input
                type="text"
                placeholder="Output Filename (e.g. merged.png)"
                value={outputFilename}
                onChange={(e) => setOutputFilename(e.target.value)}
                className="w-full p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
              />
            </div>

            {/* Merge Config */}
            <div className="grid grid-cols-2 gap-2">
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600 col-span-2"
              >
                <option value="horizontal">Horizontal</option>
                <option value="vertical">Vertical</option>
                <option value="grid">Grid</option>
                {/* <option value="gif">GIF Sequence (Not Implemented)</option> */}
              </select>

              {direction === "grid" && (
                <>
                  <label className="text-xs">
                    Rows:{" "}
                    <input
                      type="number"
                      value={gridRows}
                      onChange={(e) => setGridRows(Number(e.target.value))}
                      className="w-12 p-1 border rounded dark:bg-gray-700"
                    />
                  </label>
                  <label className="text-xs">
                    Cols:{" "}
                    <input
                      type="number"
                      value={gridCols}
                      onChange={(e) => setGridCols(Number(e.target.value))}
                      className="w-12 p-1 border rounded dark:bg-gray-700"
                    />
                  </label>
                </>
              )}

              {direction !== "gif" && (
                <>
                  <label className="text-xs">
                    Spacing:{" "}
                    <input
                      type="number"
                      value={spacing}
                      onChange={(e) => setSpacing(Number(e.target.value))}
                      className="w-12 p-1 border rounded dark:bg-gray-700"
                    />
                  </label>
                  <select
                    value={alignMode}
                    onChange={(e) => setAlignMode(e.target.value)}
                    className="p-1 border rounded text-xs dark:bg-gray-700 dark:border-gray-600"
                  >
                    <option value="center">Center</option>
                    <option value="top">Top / Left</option>
                    <option value="bottom">Bottom / Right</option>
                    <option value="stretch">Stretch</option>
                  </select>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 2. Galleries */}
        <div className="flex-1 flex flex-col min-h-0 gap-4">
          {/* Found Gallery */}
          <div className="flex-1 flex flex-col min-h-0 border rounded-lg bg-white dark:bg-gray-800 shadow-sm">
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
              <span className="font-bold text-sm flex items-center gap-2">
                <ImageIcon size={16} /> Found Images ({found.items.length})
              </span>
              <button
                onClick={actions.selectAllFoundPage}
                className="text-xs text-blue-600 hover:underline"
              >
                Select Page
              </button>
            </div>
            <div className="flex-1 relative min-h-0">
              <MarqueeScrollArea
                onSelectionChanged={(set, isCtrl) =>
                  found.actions.selectBatch(set, isCtrl)
                }
              >
                <div className="flex flex-wrap content-start p-2 gap-2">
                  {found.paginatedItems.map((item, idx) => (
                    <ClickableLabel
                      key={item.path + idx}
                      path={item.path}
                      src={item.thumbnail}
                      isSelected={found.selectedPaths.has(item.path)}
                      onPathClicked={() => actions.toggleSelection(item)}
                    />
                  ))}
                  {found.items.length === 0 && (
                    <div className="w-full h-full flex items-center justify-center text-gray-400">
                      No images found.
                    </div>
                  )}
                </div>
              </MarqueeScrollArea>
            </div>
            <PaginationBar
              currentPage={found.pagination.currentPage}
              totalPages={found.pagination.totalPages}
              onPageChange={found.pagination.setCurrentPage}
              onPrev={found.pagination.prevPage}
              onNext={found.pagination.nextPage}
            />
          </div>

          {/* Selected Gallery */}
          <div
            className="flex flex-col border rounded-lg bg-white dark:bg-gray-800 shadow-sm flex-shrink-0"
            style={{ minHeight: "150px" }}
          >
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-indigo-50 dark:bg-gray-900/50">
              <span className="font-bold text-sm text-indigo-700 dark:text-indigo-400 flex items-center gap-2">
                <CheckSquare size={16} /> Selected for Merge (
                {selected.items.length})
              </span>
              <button
                onClick={actions.deselectAll}
                className="text-xs text-red-600 hover:underline"
              >
                Clear Selection
              </button>
            </div>
            <div className="flex-1 relative min-h-0">
              <MarqueeScrollArea
                onSelectionChanged={(set, isCtrl) =>
                  selected.actions.selectBatch(set, isCtrl)
                }
              >
                <div className="flex flex-wrap content-start p-2 gap-2">
                  {selected.paginatedItems.map((item, idx) => (
                    <ClickableLabel
                      key={item.path + idx}
                      path={item.path}
                      src={item.thumbnail}
                      isSelected={selected.selectedPaths.has(item.path)}
                      onPathClicked={(path) =>
                        selected.actions.selectItem(path, true)
                      }
                    />
                  ))}
                  {selected.items.length === 0 && (
                    <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">
                      No images selected.
                    </div>
                  )}
                </div>
              </MarqueeScrollArea>
            </div>
            <PaginationBar
              currentPage={selected.pagination.currentPage}
              totalPages={selected.pagination.totalPages}
              onPageChange={selected.pagination.setCurrentPage}
              onPrev={selected.pagination.prevPage}
              onNext={selected.pagination.nextPage}
            />
          </div>
        </div>

        {/* 3. Action */}
        <div className="pb-2 flex-shrink-0">
          <button
            onClick={handleRunMerge}
            disabled={selected.items.length < 2}
            className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded shadow-md hover:from-violet-700 hover:to-indigo-700 font-bold disabled:opacity-50"
          >
            Run Merge
          </button>
        </div>
      </div>
    );
  },
);

export default MergeTab;
