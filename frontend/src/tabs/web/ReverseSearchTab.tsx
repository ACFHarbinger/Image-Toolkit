import React, {
  forwardRef,
  useState,
  useImperativeHandle,
  useRef,
} from "react";
import {
  ScanSearch,
  FolderOpen,
  Image as ImageIcon,
  Search,
} from "lucide-react";

// Components
import { ClickableLabel } from "../../components/ClickableLabel";
import { MarqueeScrollArea } from "../../components/MarqueeScrollArea";
import { useGallery } from "../../hooks/useGallery";
import { GalleryItem } from "../../hooks/galleryItem";

interface ReverseSearchTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

const ReverseSearchTab = forwardRef((props: ReverseSearchTabProps, ref) => {
  const gallery = useGallery(50);
  const [scanDir, setScanDir] = useState("");
  const dirInputRef = useRef<HTMLInputElement>(null);

  // Settings
  const [filterRes, setFilterRes] = useState(false);
  const [minW, setMinW] = useState(1920);
  const [minH, setMinH] = useState(1080);
  const [browser, setBrowser] = useState("brave");
  const [mode, setMode] = useState("All");

  useImperativeHandle(ref, () => ({
    getData: () => ({ scanDir, selected: Array.from(gallery.selectedPaths) }),
  }));

  const handleScan = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const path =
        e.target.files[0].webkitRelativePath.split("/")[0] ||
        "Selected Directory";
      setScanDir(path);

      const images: GalleryItem[] = Array.from(e.target.files)
        .filter((f) => f.type.startsWith("image/"))
        .map((f) => ({
          path: f.name,
          thumbnail: URL.createObjectURL(f),
          isVideo: false,
        }));

      gallery.actions.setGalleryItems(images);
      props.showModal(`Found ${images.length} images.`, "success");
    }
  };

  const handleSearch = () => {
    if (gallery.selectedPaths.size === 0)
      return props.showModal("Select an image first.", "error");
    if (gallery.selectedPaths.size > 1)
      return props.showModal(
        "Select only one image for reverse search.",
        "error",
      );

    const selectedPath = Array.from(gallery.selectedPaths)[0];
    props.showModal(
      `Starting Reverse Search for: ${selectedPath}\nBrowser: ${browser}\nMode: ${mode}`,
      "info",
    );
  };

  return (
    <div className="p-4 flex flex-col h-full gap-4 bg-gray-50 dark:bg-gray-900">
      <input
        type="file"
        ref={dirInputRef}
        onChange={handleScan}
        className="hidden"
        // @ts-ignore
        webkitdirectory="true"
        multiple
      />

      {/* Configuration Group */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex-shrink-0">
        <h3 className="font-bold mb-4 flex items-center gap-2">
          <ScanSearch size={18} className="text-blue-500" /> Configuration
        </h3>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="Select directory to scan..."
            value={scanDir}
            readOnly
            className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
          />
          <button
            onClick={() => dirInputRef.current?.click()}
            className="px-4 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 rounded flex items-center gap-2"
          >
            <FolderOpen size={16} /> Browse
          </button>
        </div>

        <div className="flex flex-wrap gap-4 items-center">
          <label className="flex items-center gap-2 text-sm select-none">
            <input
              type="checkbox"
              checked={filterRes}
              onChange={(e) => setFilterRes(e.target.checked)}
              className="rounded text-blue-500"
            />
            Filter by Resolution
          </label>

          <div
            className={`flex items-center gap-2 transition-opacity ${filterRes ? "opacity-100" : "opacity-50 pointer-events-none"}`}
          >
            <span className="text-sm">Min:</span>
            <input
              type="number"
              value={minW}
              onChange={(e) => setMinW(Number(e.target.value))}
              className="w-16 p-1 border rounded text-sm dark:bg-gray-700"
            />
            <span className="text-sm">x</span>
            <input
              type="number"
              value={minH}
              onChange={(e) => setMinH(Number(e.target.value))}
              className="w-16 p-1 border rounded text-sm dark:bg-gray-700"
            />
          </div>

          <div className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-2"></div>

          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="p-1 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
          >
            <option>All</option>
            <option>Visual matches</option>
            <option>Exact matches</option>
          </select>

          <select
            value={browser}
            onChange={(e) => setBrowser(e.target.value)}
            className="p-1 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
          >
            <option value="brave">Brave</option>
            <option value="chrome">Chrome</option>
            <option value="firefox">Firefox</option>
            <option value="edge">Edge</option>
          </select>
        </div>
      </div>

      {/* Gallery */}
      <div className="flex-1 flex flex-col min-h-0 border rounded-lg bg-white dark:bg-gray-800 shadow-sm">
        <div className="p-2 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex justify-between items-center">
          <span className="font-bold text-sm flex items-center gap-2">
            <ImageIcon size={16} /> Gallery ({gallery.items.length})
          </span>
          <span className="text-xs text-gray-500 italic">
            Select an image to search
          </span>
        </div>

        <div className="flex-1 relative min-h-0">
          <MarqueeScrollArea
            onSelectionChanged={(set, isCtrl) => {
              // Force single selection behavior for this tab
              if (set.size > 0) {
                const last = Array.from(set).pop();
                if (last) gallery.actions.selectItem(last, false); // clear others
              } else {
                gallery.actions.selectBatch(new Set());
              }
            }}
          >
            <div className="flex flex-wrap content-start p-2 gap-2">
              {gallery.paginatedItems.map((item, idx) => (
                <ClickableLabel
                  key={item.path + idx}
                  path={item.path}
                  src={item.thumbnail}
                  isSelected={gallery.selectedPaths.has(item.path)}
                  onPathClicked={(path) =>
                    gallery.actions.selectItem(path, false)
                  } // Single select
                />
              ))}
              {gallery.items.length === 0 && (
                <div className="w-full h-full flex items-center justify-center text-gray-400">
                  No images.
                </div>
              )}
            </div>
          </MarqueeScrollArea>
        </div>
      </div>

      {/* Action */}
      <button
        onClick={handleSearch}
        disabled={gallery.selectedPaths.size !== 1}
        className="w-full py-3 bg-blue-600 text-white font-bold rounded shadow-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <Search size={20} /> Search Selected Image
      </button>
    </div>
  );
});

export default ReverseSearchTab;
