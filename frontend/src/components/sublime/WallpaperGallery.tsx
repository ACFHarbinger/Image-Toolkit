import React, { useState, useEffect, useCallback } from "react";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { FolderOpen, Image as ImageIcon, Search, Loader2 } from "lucide-react";
import { DraggableImageLabel } from "./DraggableImageLabel";

export const WallpaperGallery: React.FC = () => {
    const [directory, setDirectory] = useState("");
    const [images, setImages] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleBrowse = async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: "Select Wallpaper Directory",
            });
            if (selected && typeof selected === "string") {
                setDirectory(selected);
            }
        } catch (err) {
            console.error("Browse error:", err);
        }
    };

    const scanDirectory = useCallback(async () => {
        if (!directory) return;
        setLoading(true);
        setError("");
        try {
            const files: string[] = await invoke("scan_files", {
                directory,
                extensions: ["jpg", "jpeg", "png", "webp", "bmp", "gif"],
                recursive: false,
            });
            setImages(files);
        } catch (err) {
            console.error("Scan error:", err);
            setError(`Failed to scan directory: ${err}`);
        } finally {
            setLoading(false);
        }
    }, [directory]);

    useEffect(() => {
        if (directory) {
            scanDirectory();
        }
    }, [directory, scanDirectory]);

    return (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col h-[400px]">
            <div className="p-4 border-b dark:border-gray-700 flex items-center justify-between bg-gray-50/50 dark:bg-gray-800/50">
                <h3 className="text-sm font-bold flex items-center gap-2">
                    <ImageIcon size={16} className="text-violet-500" /> Image Gallery
                </h3>
                <button
                    onClick={handleBrowse}
                    className="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors text-gray-500"
                    title="Browse Directory"
                >
                    <FolderOpen size={18} />
                </button>
            </div>

            <div className="p-3 border-b dark:border-gray-700">
                <div className="relative group">
                    <input
                        type="text"
                        value={directory}
                        onChange={(e) => setDirectory(e.target.value)}
                        placeholder="Select directory to browse images..."
                        className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-violet-500 outline-none transition-all"
                    />
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {loading ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-2">
                        <Loader2 size={24} className="animate-spin text-violet-500" />
                        <span className="text-xs">Scanning images...</span>
                    </div>
                ) : error ? (
                    <div className="h-full flex items-center justify-center text-red-500 text-xs text-center p-4 italic">
                        {error}
                    </div>
                ) : images.length > 0 ? (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        {images.map((path) => (
                            <div key={path} className="flex flex-col items-center gap-2">
                                <DraggableImageLabel
                                    path={path}
                                    src={convertFileSrc(path)}
                                    size={100}
                                />
                                <span className="text-[10px] text-gray-500 truncate w-full text-center" title={path.split(/[/\\]/).pop()}>
                                    {path.split(/[/\\]/).pop()}
                                </span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-3 grayscale opacity-60">
                        <ImageIcon size={48} strokeWidth={1} />
                        <p className="text-xs text-center max-w-[200px]">
                            No images found. Select a directory above to start browsing.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};
