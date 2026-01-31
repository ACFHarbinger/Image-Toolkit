import { forwardRef, useState, useImperativeHandle, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Search,
  CheckSquare,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

// Components
import { ClickableLabel } from "../../components/ClickableLabel";
import { MarqueeScrollArea } from "../../components/MarqueeScrollArea";
import { useTwoGalleries } from "../../hooks/useTwoGalleries";
import { GalleryItem } from "../../hooks/galleryItem";

interface SearchTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

export interface SearchTabHandle {
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

const SearchTab = forwardRef<SearchTabHandle, SearchTabProps>(
  ({ showModal }, ref) => {
    // --- Two Galleries Hook ---
    const { found, selected, actions } = useTwoGalleries(50, 50);

    // --- Search Criteria State ---
    const [group, setGroup] = useState("");
    const [subgroup, setSubgroup] = useState("");
    const [filename, setFilename] = useState("");
    const [formats, setFormats] = useState<Set<string>>(new Set());

    // Tags state - loaded from database
    const [availableTags, setAvailableTags] = useState<string[]>([]);
    const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
    const [isLoading, setIsLoading] = useState(false);

    // Load available tags from database on mount
    useEffect(() => {
      const loadTags = async () => {
        try {
          const tags = await invoke<string[]>("get_all_tags");
          setAvailableTags(tags);
        } catch (err) {
          console.error("Failed to load tags:", err);
          showModal("Failed to load tags from database", "error");
        }
      };

      loadTags();
    }, []);

    useImperativeHandle(ref, () => ({
      getData: () => ({
        action: "search",
        criteria: {
          group,
          subgroup,
          filename,
          formats: Array.from(formats),
          tags: Array.from(selectedTags),
        },
        selected_images: Array.from(selected.items).map((i) => i.path),
      }),
    }));

    const handleSearch = async () => {
      setIsLoading(true);
      showModal("Searching database...", "info");

      try {
        // Call Tauri backend to search database
        const results = await invoke<any[]>("search_images", {
          query: {
            group_name: group || null,
            subgroup_name: subgroup || null,
            filename_pattern: filename || null,
            input_formats: formats.size > 0 ? Array.from(formats) : null,
            tags: selectedTags.size > 0 ? Array.from(selectedTags) : null,
            limit: 500, // Fetch more results for better UX
          },
        });

        // Convert database results to GalleryItem format
        const galleryItems: GalleryItem[] = results.map((img) => ({
          path: img.file_path,
          thumbnail: `file://${img.file_path}`, // Use actual image path
          isVideo: false,
        }));

        found.actions.setGalleryItems(galleryItems);
        showModal(`Found ${galleryItems.length} images`, "success", 2000);
      } catch (err: any) {
        console.error("Search error:", err);
        showModal(err.message || "Search failed", "error");
        found.actions.setGalleryItems([]);
      } finally {
        setIsLoading(false);
      }
    };

    const toggleFormat = (fmt: string) => {
      const next = new Set(formats);
      if (next.has(fmt)) next.delete(fmt);
      else next.add(fmt);
      setFormats(next);
    };

    const toggleTag = (tag: string) => {
      const next = new Set(selectedTags);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      setSelectedTags(next);
    };

    return (
      <div className="flex flex-col h-full p-4 gap-4 bg-gray-50 dark:bg-gray-900 overflow-hidden">
        {/* 1. Search Panel (Top) */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
            <Search size={18} className="text-violet-500" /> Search Criteria
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <input
              type="text"
              placeholder="Group Name (Optional)"
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
            />
            <input
              type="text"
              placeholder="Subgroup Name (Optional)"
              value={subgroup}
              onChange={(e) => setSubgroup(e.target.value)}
              className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
            />
            <input
              type="text"
              placeholder="Filename Pattern (*.jpg)"
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
            />
          </div>

          {/* Formats & Tags */}
          <div className="flex flex-col md:flex-row gap-4">
            {/* Formats */}
            <div className="flex-1">
              <span className="text-xs font-semibold text-gray-500 mb-2 block">
                Formats
              </span>
              <div className="flex flex-wrap gap-2">
                {["jpg", "png", "gif", "webp"].map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => toggleFormat(fmt)}
                    className={`px-3 py-1 text-xs rounded border transition-colors ${formats.has(fmt) ? "bg-blue-600 text-white border-blue-600" : "bg-gray-100 dark:bg-gray-700 dark:border-gray-600 hover:bg-gray-200"}`}
                  >
                    {fmt.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Tags */}
            <div className="flex-[2]">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-semibold text-gray-500">
                  Tags
                </span>
                <button
                  onClick={() => setSelectedTags(new Set())}
                  className="text-[10px] text-red-500 hover:underline"
                >
                  Clear Tags
                </button>
              </div>
              <div className="h-20 overflow-y-auto border rounded p-2 bg-gray-50 dark:bg-gray-700/50 dark:border-gray-600">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {availableTags.length === 0 ? (
                    <div className="col-span-full text-xs text-gray-400 text-center py-2">
                      No tags available in database
                    </div>
                  ) : (
                    availableTags.map((tag: string) => (
                      <label
                        key={tag}
                        className="flex items-center gap-1 text-xs cursor-pointer select-none"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTags.has(tag)}
                          onChange={() => toggleTag(tag)}
                          className="rounded text-violet-500"
                        />
                        {tag}
                      </label>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="w-full mt-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold rounded shadow-md hover:from-violet-700 hover:to-indigo-700 transition-all active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Searching..." : "Search Database"}
          </button>
        </div>

        {/* 2. Galleries Area (Split View) */}
        <div className="flex-1 flex flex-col min-h-0 gap-4">
          {/* Found Gallery */}
          <div className="flex-1 flex flex-col min-h-0 border rounded-lg bg-white dark:bg-gray-800 shadow-sm">
            <div className="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
              <span className="font-bold text-sm flex items-center gap-2">
                <ImageIcon size={16} /> Search Results ({found.items.length})
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
                      No results found.
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

        {/* 3. Batch Actions (Bottom) */}
        <div className="flex gap-2 pb-2 flex-shrink-0">
          <button
            onClick={() =>
              showModal(
                `Sending ${selected.items.length} items to Scan Tab`,
                "success",
              )
            }
            className="flex-1 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium disabled:opacity-50"
            disabled={selected.items.length === 0}
          >
            Send to Scan Tab
          </button>
          <button
            onClick={() =>
              showModal(
                `Sending ${selected.items.length} items to Merge Tab`,
                "success",
              )
            }
            className="flex-1 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
            disabled={selected.items.length === 0}
          >
            Send to Merge Tab
          </button>
          <button
            onClick={() =>
              showModal(
                `Sending ${selected.items.length} items to Delete Tab`,
                "error",
              )
            }
            className="flex-1 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium disabled:opacity-50"
            disabled={selected.items.length === 0}
          >
            Send to Delete Tab
          </button>
        </div>
      </div>
    );
  },
);

export default SearchTab;
