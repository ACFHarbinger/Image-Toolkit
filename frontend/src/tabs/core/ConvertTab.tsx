import React, {
  forwardRef,
  useState,
  useImperativeHandle,
  useRef,
} from "react";
import {
  FolderOpen,
  Settings,
  FileOutput,
  Image as ImageIcon,
  CheckSquare,
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
import { SUPPORTED_IMG_FORMATS } from "../../constants";

interface ConvertTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

export interface ConvertTabHandle {
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

const ConvertTab = forwardRef<ConvertTabHandle, ConvertTabProps>(
  ({ showModal }, ref) => {
    // --- Two Galleries Hook ---
    const { found, selected, actions } = useTwoGalleries(50, 50);

    // --- State ---
    const [inputPath, setInputPath] = useState("");
    const [outputFormat, setOutputFormat] = useState("png");
    const [outputPath, setOutputPath] = useState("");
    const [selectedFormats, setSelectedFormats] = useState<Set<string>>(
      new Set(),
    );
    const [deleteOriginal, setDeleteOriginal] = useState(false);
    const [aspectRatioEnabled, setAspectRatioEnabled] = useState(false);
    const [aspectRatioMode, setAspectRatioMode] = useState("crop");
    const [aspectRatioPreset, setAspectRatioPreset] = useState("16:9");
    const [customAR, setCustomAR] = useState({ w: 16, h: 9 });

    // Refs for file inputs
    const inputDirRef = useRef<HTMLInputElement>(null);
    const outputDirRef = useRef<HTMLInputElement>(null);

    useImperativeHandle(ref, () => ({
      getData: () => ({
        action: "convert",
        config: {
          input_path: inputPath,
          output_format: outputFormat,
          output_path: outputPath,
          input_formats: Array.from(selectedFormats),
          delete_original: deleteOriginal,
          aspect_ratio: aspectRatioEnabled ? customAR.w / customAR.h : null,
          aspect_ratio_mode: aspectRatioMode,
        },
        selected_files: Array.from(selected.items).map((i: any) => i.path),
      }),
    }));

    // --- Handlers ---

    const onARPresetChange = (preset: string) => {
      setAspectRatioPreset(preset);
      if (preset !== "Custom") {
        const [w, h] = preset.split(":").map(Number);
        setCustomAR({ w, h });
      }
    };

    const handleBrowseInput = async () => {
      try {
        const dir = (await open({ directory: true, multiple: false })) as
          | string
          | null;
        if (dir) {
          setInputPath(dir);
          // Ask Rust/Tauri to scan files
          const files =
            (await invoke<string[]>("scan_files", {
              directory: dir,
              extensions: SUPPORTED_IMG_FORMATS,
              recursive: true,
            })) || [];
          const images: GalleryItem[] = files.map((p) => ({
            path: p,
            thumbnail: convertFileSrc(p),
            isVideo: false,
          }));
          found.actions.setGalleryItems(images);
          showModal(`Found ${images.length} images.`, "info", 2000);
        }
      } catch (err) {
        console.error(err);
        showModal("Failed to select input directory", "error", 2500);
      }
    };

    const handleBrowseOutput = async () => {
      try {
        const dir = (await open({ directory: true, multiple: false })) as
          | string
          | null;
        if (dir) setOutputPath(dir);
      } catch (err) {
        console.error(err);
        showModal("Failed to select output directory", "error", 2500);
      }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        // Simulate directory selection
        const path =
          e.target.files[0].webkitRelativePath.split("/")[0] ||
          "Selected Directory";
        setInputPath(path);
        handleScanDirectory(e.target.files);
      }
    };

    // Kept for legacy input element path; not used in Tauri flow
    const handleScanDirectory = (files: FileList) => {
      const images: GalleryItem[] = Array.from(files)
        .filter((f) => f.type.startsWith("image/"))
        .map((f) => ({
          path: f.name,
          thumbnail: URL.createObjectURL(f),
          isVideo: false,
        }));
      found.actions.setGalleryItems(images);
      showModal(`Found ${images.length} images.`, "info", 2000);
    };

    const handleOutputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        setOutputPath("Selected Output Directory");
      }
    };

    const toggleFormat = (fmt: string) => {
      const next = new Set(selectedFormats);
      if (next.has(fmt)) next.delete(fmt);
      else next.add(fmt);
      setSelectedFormats(next);
    };

    const buildPairs = (paths: string[]) => {
      const pairs: Array<[string, string]> = [];
      for (const p of paths) {
        const sep = p.includes("\\") && !p.includes("/") ? "\\" : "/";
        const lastSep = p.lastIndexOf(sep);
        const dir = lastSep >= 0 ? p.substring(0, lastSep) : "";
        const base = lastSep >= 0 ? p.substring(lastSep + 1) : p;
        const name = base.replace(/\.[^.]+$/, "");
        const outDir = outputPath && outputPath.length > 0 ? outputPath : dir;
        const outPath = `${outDir}${sep}${name}.${outputFormat}`;
        pairs.push([p, outPath]);
      }
      return pairs;
    };

    const handleConvertAll = async () => {
      if (found.items.length === 0)
        return showModal("No images found to convert.", "error");
      try {
        showModal(
          `Converting all ${found.items.length} images to ${outputFormat.toUpperCase()}...`,
          "info",
        );
        const paths = found.items.map((i) => i.path);
        const pairs = buildPairs(paths);
        const results = await invoke<string[]>("convert_image_batch", {
          pairs,
          outputFormat: outputFormat,
          deleteOriginal: deleteOriginal,
          aspectRatio: aspectRatioEnabled ? customAR.w / customAR.h : null,
          arMode: aspectRatioMode,
        });
        showModal(`Converted ${results.length} images.`, "success", 2500);
      } catch (err) {
        console.error(err);
        showModal(`Conversion failed: ${err}`, "error");
      }
    };

    const handleConvertSelected = async () => {
      if (selected.items.length === 0)
        return showModal("No images selected.", "error");
      try {
        showModal(
          `Converting ${selected.items.length} selected images to ${outputFormat.toUpperCase()}...`,
          "info",
        );
        const paths = selected.items.map((i) => i.path);
        const pairs = buildPairs(paths);
        const results = await invoke<string[]>("convert_image_batch", {
          pairs,
          outputFormat: outputFormat,
          deleteOriginal: deleteOriginal,
          aspectRatio: aspectRatioEnabled ? customAR.w / customAR.h : null,
          arMode: aspectRatioMode,
        });
        showModal(`Converted ${results.length} images.`, "success", 2500);
      } catch (err) {
        console.error(err);
        showModal(`Conversion failed: ${err}`, "error");
      }
    };

    return (
      <div className="flex flex-col h-full p-4 gap-4 bg-gray-50 dark:bg-gray-900 overflow-hidden">
        {/* Hidden Inputs */}
        <input
          type="file"
          ref={inputDirRef}
          onChange={handleInputChange}
          className="hidden"
          // @ts-ignore
          webkitdirectory="true"
          multiple
        />
        <input
          type="file"
          ref={outputDirRef}
          onChange={handleOutputChange}
          className="hidden"
          // @ts-ignore
          webkitdirectory="true"
        />

        {/* 1. Settings Panel */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
            <Settings size={18} className="text-violet-500" /> Convert Settings
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 mb-4">
            {/* Input Path */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-gray-500">
                Input Directory
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Input Directory Path..."
                  readOnly
                  value={inputPath}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600 outline-none focus:ring-1 focus:ring-violet-500"
                />
                <button
                  onClick={handleBrowseInput}
                  className="px-3 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded transition-colors"
                >
                  <FolderOpen size={16} />
                </button>
              </div>
            </div>

            {/* Output Format */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-gray-500">
                Output Format
              </label>
              <select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                className="w-full p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600 outline-none focus:ring-1 focus:ring-violet-500"
              >
                {SUPPORTED_IMG_FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            {/* Output Path */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-gray-500">
                Output Directory (Optional)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Same as input..."
                  readOnly
                  value={outputPath}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600 outline-none focus:ring-1 focus:ring-violet-500"
                />
                <button
                  onClick={handleBrowseOutput}
                  className="px-3 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded transition-colors"
                >
                  <FileOutput size={16} />
                </button>
              </div>
            </div>

            {/* Delete Original & AR Toggle */}
            <div className="flex flex-col gap-3 justify-center">
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={deleteOriginal}
                  onChange={(e) => setDeleteOriginal(e.target.checked)}
                  className="rounded text-violet-500 focus:ring-violet-500 w-4 h-4"
                />
                <span>Delete original files after conversion</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={aspectRatioEnabled}
                  onChange={(e) => setAspectRatioEnabled(e.target.checked)}
                  className="rounded text-violet-500 focus:ring-violet-500 w-4 h-4"
                />
                <span>Change Aspect Ratio</span>
              </label>
            </div>
          </div>

          {/* Aspect Ratio Controls */}
          {aspectRatioEnabled && (
            <div className="mb-4 p-3 bg-violet-50 dark:bg-violet-900/10 rounded-lg border border-violet-100 dark:border-violet-900/30 flex flex-wrap items-center gap-4 animate-in fade-in slide-in-from-top-1 duration-200">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-violet-700 dark:text-violet-400">
                  Mode:
                </span>
                <select
                  value={aspectRatioMode}
                  onChange={(e) => setAspectRatioMode(e.target.value)}
                  className="p-1.5 border rounded text-xs dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="crop">Crop</option>
                  <option value="pad">Pad</option>
                  <option value="stretch">Stretch</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-violet-700 dark:text-violet-400">
                  Ratio:
                </span>
                <select
                  value={aspectRatioPreset}
                  onChange={(e) => onARPresetChange(e.target.value)}
                  className="p-1.5 border rounded text-xs dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="16:9">16:9</option>
                  <option value="4:3">4:3</option>
                  <option value="1:1">1:1</option>
                  <option value="9:16">9:16</option>
                  <option value="3:2">3:2</option>
                  <option value="Custom">Custom</option>
                </select>
              </div>
              {aspectRatioPreset === "Custom" && (
                <div className="flex items-center gap-2 animate-in zoom-in-95 duration-200">
                  <span className="text-xs font-bold text-violet-700 dark:text-violet-400">
                    W:
                  </span>
                  <input
                    type="number"
                    value={customAR.w}
                    onChange={(e) =>
                      setCustomAR({ ...customAR, w: Number(e.target.value) })
                    }
                    className="w-16 p-1.5 border rounded text-xs dark:bg-gray-800 dark:border-gray-700"
                  />
                  <span className="text-xs font-bold text-violet-700 dark:text-violet-400">
                    H:
                  </span>
                  <input
                    type="number"
                    value={customAR.h}
                    onChange={(e) =>
                      setCustomAR({ ...customAR, h: Number(e.target.value) })
                    }
                    className="w-16 p-1.5 border rounded text-xs dark:bg-gray-800 dark:border-gray-700"
                  />
                </div>
              )}
            </div>
          )}

          {/* Format Filter */}
          <div>
            <span className="text-xs font-semibold text-gray-500 mb-2 block">
              Filter Input Formats (Optional)
            </span>
            <div className="flex flex-wrap gap-2">
              {SUPPORTED_IMG_FORMATS.slice(0, 8).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => toggleFormat(fmt)}
                  className={`px-3 py-1 text-xs rounded border transition-colors ${selectedFormats.has(fmt) ? "bg-blue-600 text-white border-blue-600" : "bg-gray-100 dark:bg-gray-700 dark:border-gray-600 hover:bg-gray-200"}`}
                >
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 2. Galleries Area */}
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
                      No images loaded.
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
                <CheckSquare size={16} /> Selected Images (
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

        {/* 3. Action Buttons */}
        <div className="flex gap-2 pb-2 flex-shrink-0">
          <button
            onClick={handleConvertAll}
            className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded shadow-md hover:from-violet-700 hover:to-indigo-700 font-bold transition-all disabled:opacity-50"
            disabled={found.items.length === 0}
          >
            Convert All in Directory
          </button>
          <button
            onClick={handleConvertSelected}
            className="flex-1 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded shadow-md hover:from-emerald-600 hover:to-teal-700 font-bold transition-all disabled:opacity-50"
            disabled={selected.items.length === 0}
          >
            Convert Selected Files ({selected.items.length})
          </button>
        </div>
      </div>
    );
  },
);

export default ConvertTab;
