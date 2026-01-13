import React, { useState, useRef, useEffect } from "react";
import {
  FolderOpen,
  Play,
  Pause,
  Volume2,
  Monitor,
  Camera,
  Scissors,
  Film,
  FileVideo,
  Trash2,
  RefreshCcw,
  AlertCircle,
} from "lucide-react";

// Components
import {
  ClickableLabel,
  VIDEO_PLACEHOLDER_CONST,
} from "../../components/ClickableLabel";
import { MarqueeScrollArea } from "../../components/MarqueeScrollArea";
import { useGallery } from "../../hooks/useGallery";
import { GalleryItem } from "../../hooks/galleryItem";

// --- Types & Constants ---
const RESOLUTIONS = [
  { label: "Original", w: 0, h: 0 },
  { label: "480p", w: 854, h: 480 },
  { label: "720p", w: 1280, h: 720 },
  { label: "1080p", w: 1920, h: 1080 },
  { label: "1440p", w: 2560, h: 1440 },
  { label: "4K", w: 3840, h: 2160 },
];

const PLAYER_SIZES = [
  { label: "720p", w: 1280, h: 720 },
  { label: "1080p", w: 1920, h: 1080 },
  { label: "1440p", w: 2560, h: 1440 },
  { label: "4K", w: 3840, h: 2160 },
];

// Fallback Icon if generation fails (SVG Data URI)
const VIDEO_ICON_URI =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150' style='background:%23222'%3E%3Cpath d='M60 45v60l45-30z' fill='%23666'/%3E%3Crect x='5' y='5' width='140' height='140' fill='none' stroke='%23444' stroke-width='2'/%3E%3Ctext x='75' y='130' font-family='sans-serif' font-size='12' fill='%23888' text-anchor='middle'%3EVIDEO%3C/text%3E%3C/svg%3E";

// --- Helper: Real Thumbnail Generation ---
// This function creates a temporary video element, loads the source, seeks to 1s, and snaps a picture.
const generateVideoThumbnail = async (videoUrl: string): Promise<string> => {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.src = videoUrl;
    video.crossOrigin = "anonymous";
    video.muted = true;
    video.preload = "metadata";

    // We try to capture the frame at 1.0 second.
    // If the video is shorter than 1s, it will snap the end.
    video.currentTime = 1.0;

    const cleanup = () => {
      video.removeAttribute("src");
      video.load();
    };

    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas");
        // Low resolution thumbnail is enough for the gallery (speed optimization)
        canvas.width = 160;
        canvas.height = 90;

        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const dataUrl = canvas.toDataURL("image/jpeg", 0.6); // 60% quality JPG
          resolve(dataUrl);
        } else {
          resolve(VIDEO_ICON_URI);
        }
      } catch (e) {
        console.error("Thumbnail generation error", e);
        resolve(VIDEO_ICON_URI);
      } finally {
        cleanup();
      }
    };

    // If it fails or takes too long
    video.onerror = () => {
      cleanup();
      resolve(VIDEO_ICON_URI);
    };

    // Fallback if seek event never fires (timeout after 3s)
    setTimeout(() => {
      resolve(VIDEO_ICON_URI);
      cleanup();
    }, 3000);
  });
};

// Helper to reliably detect videos
const isFileVideo = (file: File) => {
  return (
    file.type.startsWith("video/") ||
    /\.(mp4|mkv|webm|avi|mov|m4v)$/i.test(file.name)
  );
};

export const ImageExtractorTab: React.FC = () => {
  // --- State: Directories ---
  const [sourceDir, setSourceDir] = useState<string>("");
  const [extractDir, setExtractDir] = useState<string>("./Frames");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // --- Refs ---
  const sourceInputRef = useRef<HTMLInputElement>(null);
  const extractInputRef = useRef<HTMLInputElement>(null);
  const blobUrlRef = useRef<Set<string>>(new Set());

  // --- State: Galleries ---
  const [sourceMedia, setSourceMedia] = useState<GalleryItem[]>([]);
  const resultsGallery = useGallery(100);

  // --- State: Video Player ---
  const [currentVideoPath, setCurrentVideoPath] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.5);
  const [playerSizeIndex, setPlayerSizeIndex] = useState(1);
  const [isPlayerVertical, setIsPlayerVertical] = useState(false);
  const [useInternalPlayer, setUseInternalPlayer] = useState(true);

  // --- State: Extraction Settings ---
  const [extractResIndex, setExtractResIndex] = useState(0);
  // FIX: Renamed setter to setIsExtractVertical to avoid redeclaration error (L132)
  const [isExtractVertical, setIsExtractVertical] = useState(false);
  const [gifFps, setGifFps] = useState(15);
  const [muteAudio, setMuteAudio] = useState(false);

  // --- State: Range Selection ---
  const [startTime, setStartTime] = useState<number | null>(null);
  const [endTime, setEndTime] = useState<number | null>(null);

  // --- Helper: Url Tracking ---
  const createTrackedUrl = (file: File) => {
    const url = URL.createObjectURL(file);
    blobUrlRef.current.add(url);
    return url;
  };

  const revokeAllUrls = () => {
    blobUrlRef.current.forEach((url) => URL.revokeObjectURL(url));
    blobUrlRef.current.clear();
  };

  // --- Effects ---

  useEffect(() => {
    return () => {
      revokeAllUrls();
    };
  }, []);

  // Handle Video Events
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const updateTime = () => setCurrentTime(video.currentTime);
    const updateDuration = () => setDuration(video.duration);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    setVideoError(null);

    video.addEventListener("timeupdate", updateTime);
    video.addEventListener("loadedmetadata", updateDuration);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);

    return () => {
      video.removeEventListener("timeupdate", updateTime);
      video.removeEventListener("loadedmetadata", updateDuration);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
    };
  }, [currentVideoPath, useInternalPlayer]);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = volume;
    }
  }, [volume]);

  // --- Helpers ---

  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return "00:00:000";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${min.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}:${ms.toString().padStart(3, "0")}`;
  };

  // --- Handlers: Directory Scanning ---

  const handleBrowseSource = () => {
    if (sourceInputRef.current) sourceInputRef.current.click();
  };

  const handleBrowseOutput = () => {
    if (extractInputRef.current) extractInputRef.current.click();
  };

  // HANDLER: Source Directory
  const onSourceDirectoryChange = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (!event.target.files || event.target.files.length === 0) return;

    setIsLoading(true);
    revokeAllUrls();
    setSourceMedia([]);
    setCurrentVideoPath(null);
    setVideoError(null);

    const files = Array.from(event.target.files);

    const validFiles = files.filter(
      (file) => isFileVideo(file) || file.type === "image/gif",
    );

    if (validFiles.length > 0) {
      const pathParts = validFiles[0].webkitRelativePath.split("/");
      setSourceDir(pathParts.length > 1 ? pathParts[0] : "Selected Directory");
    }

    // 1. Initial State: All videos have a "Waiting" placeholder
    const initialItems: GalleryItem[] = validFiles.map((file) => {
      const blobUrl = createTrackedUrl(file);
      const isVideo = isFileVideo(file);
      return {
        path: blobUrl,
        isVideo: isVideo,
        thumbnail: VIDEO_PLACEHOLDER_CONST,
      };
    });

    setSourceMedia(initialItems);
    setIsLoading(false);

    // 2. Process thumbnails one by one asynchronously
    // This runs in the background so the UI doesn't freeze
    const processThumbnails = async () => {
      // We create a copy to mutate as we go
      const itemsToProcess = [...initialItems];

      for (let i = 0; i < itemsToProcess.length; i++) {
        const item = itemsToProcess[i];

        // Only generate if it's a video and currently a placeholder
        if (item.isVideo && item.thumbnail === VIDEO_PLACEHOLDER_CONST) {
          const thumb = await generateVideoThumbnail(item.path);
          itemsToProcess[i] = { ...item, thumbnail: thumb };

          // Update state progressively (every item, or you could batch every 5)
          setSourceMedia([...itemsToProcess]);
        } else if (!item.isVideo) {
          // If it's a GIF or image, just use the path
          itemsToProcess[i] = { ...item, thumbnail: item.path };
          setSourceMedia([...itemsToProcess]);
        }
      }
    };

    processThumbnails();
  };

  // HANDLER: Output Directory
  const onExtractDirectoryChange = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (!event.target.files || event.target.files.length === 0) return;

    setIsLoading(true);

    const files = Array.from(event.target.files);
    const validFiles = files.filter(
      (file) =>
        file.type.startsWith("image/") || file.type.startsWith("video/"),
    );

    if (validFiles.length > 0) {
      const pathParts = validFiles[0].webkitRelativePath.split("/");
      setExtractDir(pathParts.length > 1 ? pathParts[0] : "Selected Directory");
    }

    const initialItems: GalleryItem[] = validFiles.map((file) => {
      const blobUrl = createTrackedUrl(file);
      const isVideo = isFileVideo(file);
      return {
        path: blobUrl,
        isVideo: isVideo,
        thumbnail: VIDEO_PLACEHOLDER_CONST,
      };
    });

    resultsGallery.actions.setGalleryItems(initialItems);
    setIsLoading(false);

    // Process thumbnails for the results gallery too
    const processThumbnails = async () => {
      const itemsToProcess = [...initialItems];
      for (let i = 0; i < itemsToProcess.length; i++) {
        const item = itemsToProcess[i];
        if (item.isVideo) {
          const thumb = await generateVideoThumbnail(item.path);
          itemsToProcess[i] = { ...item, thumbnail: thumb };
          resultsGallery.actions.setGalleryItems([...itemsToProcess]);
        } else {
          itemsToProcess[i] = { ...item, thumbnail: item.path };
          resultsGallery.actions.setGalleryItems([...itemsToProcess]);
        }
      }
    };

    processThumbnails();
  };

  // --- Handlers: Player ---

  const loadMedia = (path: string) => {
    setCurrentVideoPath(path);
    setStartTime(null);
    setEndTime(null);
    setIsPlaying(false);
    setVideoError(null);

    if (videoRef.current) {
      // Log the file path being loaded
      console.log("Attempting to load media:", path);

      videoRef.current.load();
      // This slight seek to 0.001 is a common workaround for video track initialization issues.
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.currentTime = 0.001;
        }
      }, 100);
    }
  };

  const togglePlayback = () => {
    if (!videoRef.current) return;
    if (isPlaying) videoRef.current.pause();
    else videoRef.current.play();
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) videoRef.current.currentTime = time;
    setCurrentTime(time);
  };

  const getPlayerStyle = () => {
    const base = PLAYER_SIZES[playerSizeIndex];
    const width = isPlayerVertical ? base.h : base.w;
    const height = isPlayerVertical ? base.w : base.h;

    return {
      aspectRatio: `${width}/${height}`,
      maxWidth: "100%",
      maxHeight: "600px",
    };
  };

  // --- Handlers: Extraction ---

  const handleSnapshot = () => {
    if (!videoRef.current) return;
    // Removed unused 'timestamp' variable to fix ESLint warning

    // For snapshot, we can try to actually capture the current frame from the video element
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext("2d");
    let thumb = "https://placehold.co/150x150/0000FF/ffffff?text=Snapshot";

    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0);
      thumb = canvas.toDataURL("image/jpeg");
    }

    const newFile = {
      path: thumb, // In a real app this would be a file URL, here we just use the base64 as both path and thumb
      thumbnail: thumb,
      isVideo: false,
    };
    resultsGallery.actions.setGalleryItems([newFile], true);
  };

  const handleExtractRange = (type: "frames" | "video" | "gif") => {
    if (startTime === null || endTime === null) return;
    alert(
      `Mock: Extracting ${type} from ${formatTime(startTime)} to ${formatTime(endTime)}`,
    );

    const newFile = {
      path: `output_${Date.now()}.${type === "frames" ? "jpg" : type === "gif" ? "gif" : "mp4"}`,
      thumbnail: VIDEO_ICON_URI,
      isVideo: type !== "frames",
    };
    resultsGallery.actions.setGalleryItems([newFile], true);
  };

  // Helper to determine if the current path is an MKV (to inform the video tag)
  const isCurrentPathMkv = currentVideoPath
    ? /\.mkv$/i.test(currentVideoPath)
    : false;

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-4 space-y-4">
      {/* Hidden Inputs for Directory Scanning */}
      <input
        type="file"
        // @ts-ignore
        webkitdirectory="true"
        multiple
        ref={sourceInputRef}
        onChange={onSourceDirectoryChange}
        className="hidden"
      />
      <input
        type="file"
        // @ts-ignore
        webkitdirectory="true"
        multiple
        ref={extractInputRef}
        onChange={onExtractDirectoryChange}
        className="hidden"
      />

      {/* 1. Directories */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Source Directory */}
        <div className="border p-4 rounded bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-bold mb-2">Source Directory</h3>
          <div className="flex gap-2">
            <input
              className="flex-1 border p-2 rounded dark:bg-gray-700 dark:border-gray-600 text-sm"
              value={sourceDir}
              readOnly
              placeholder="No directory selected"
            />
            <button
              onClick={handleBrowseSource}
              disabled={isLoading}
              className="bg-gray-200 dark:bg-gray-700 px-4 py-2 rounded hover:bg-gray-300 dark:hover:bg-gray-600 flex items-center gap-2"
            >
              {isLoading ? (
                <RefreshCcw className="animate-spin" size={16} />
              ) : (
                <FolderOpen size={16} />
              )}
              Browse
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Scans for Video (mp4, mkv, etc) & GIFs
          </p>
        </div>

        {/* Output Directory */}
        <div className="border p-4 rounded bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-bold mb-2">Output Gallery / Directory</h3>
          <div className="flex gap-2">
            <input
              className="flex-1 border p-2 rounded dark:bg-gray-700 dark:border-gray-600 text-sm"
              value={extractDir}
              readOnly
              placeholder="No directory selected"
            />
            <button
              onClick={handleBrowseOutput}
              disabled={isLoading}
              className="bg-gray-200 dark:bg-gray-700 px-4 py-2 rounded hover:bg-gray-300 dark:hover:bg-gray-600 flex items-center gap-2"
            >
              {isLoading ? (
                <RefreshCcw className="animate-spin" size={16} />
              ) : (
                <FolderOpen size={16} />
              )}
              Change
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Scans for any Image or Video to populate gallery
          </p>
        </div>
      </div>

      {/* 2. Source Media Gallery */}
      <div className="border p-4 rounded bg-white dark:bg-gray-800 shadow-sm">
        <h3 className="font-bold mb-2">
          Available Media ({sourceMedia.length})
        </h3>
        <MarqueeScrollArea>
          <div className="flex flex-wrap gap-2 min-h-[120px]">
            {sourceMedia.map((item, idx) => (
              <ClickableLabel
                key={item.path + idx}
                path={item.path}
                src={item.thumbnail}
                isVideo={item.isVideo}
                isSelected={currentVideoPath === item.path}
                onPathClicked={loadMedia}
              />
            ))}
            {sourceMedia.length === 0 && (
              <p className="w-full text-center text-gray-500 py-10">
                Click "Browse" to scan a folder for videos.
              </p>
            )}
          </div>
        </MarqueeScrollArea>
      </div>

      {/* 3. Video Player Area (Conditional) */}
      {currentVideoPath && (
        <div className="border p-4 rounded bg-white dark:bg-gray-800 shadow-sm transition-all">
          <div className="flex justify-between items-center mb-2 border-b pb-2 dark:border-gray-700">
            <h3 className="font-bold">Video Player</h3>
            <div className="flex gap-4 items-center text-sm">
              <button
                onClick={() => setUseInternalPlayer(!useInternalPlayer)}
                className="flex items-center gap-1 text-blue-600 hover:text-blue-500"
              >
                {useInternalPlayer ? (
                  <Monitor size={14} />
                ) : (
                  <FolderOpen size={14} />
                )}
                {useInternalPlayer ? "External Player" : "Internal Player"}
              </button>

              <label className="flex items-center gap-2">
                Size:
                <select
                  className="border rounded p-1 dark:bg-gray-700"
                  value={playerSizeIndex}
                  onChange={(e) => setPlayerSizeIndex(Number(e.target.value))}
                  disabled={!useInternalPlayer}
                >
                  {PLAYER_SIZES.map((s, i) => (
                    <option key={i} value={i}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={isPlayerVertical}
                  onChange={(e) => setIsPlayerVertical(e.target.checked)}
                  disabled={!useInternalPlayer}
                />
                Vertical
              </label>
            </div>
          </div>

          {useInternalPlayer ? (
            <div className="flex flex-col items-center bg-black rounded overflow-hidden relative">
              {/* Using <video> with <source> tag for better MIME type signaling */}
              <video
                ref={videoRef}
                style={getPlayerStyle()}
                className="bg-black"
                onClick={togglePlayback}
                onError={(e) => {
                  const error = e.currentTarget.error;
                  let message =
                    "The format is not supported by this browser or the file is corrupted.";

                  if (error) {
                    if (error.code === error.MEDIA_ERR_SRC_NOT_SUPPORTED) {
                      message =
                        "Error: Media source (likely HEVC/H.265 codec) is not natively supported by your browser/OS.";
                    } else if (error.code === error.MEDIA_ERR_DECODE) {
                      message =
                        "Error: Decoding problem. The video codec (likely HEVC/H.265) is missing or unsupported on your system.";
                    }
                  }

                  // Provide advice to the user
                  setVideoError(
                    message +
                    " If this is an MKV file, try using the 'External Player' option below.",
                  );
                }}
              >
                {/* Dynamically adding source tag with specific type for MKV */}
                {isCurrentPathMkv ? (
                  <source src={currentVideoPath} type="video/x-matroska" />
                ) : (
                  <source src={currentVideoPath} type="video/mp4" />
                )}
                {/* Fallback for browsers that don't support <source> */}
                {/* Setting src here as a secondary fallback if source tags fail */}
                <span
                  style={{ display: "none" }}
                  dangerouslySetInnerHTML={{
                    __html: `<video src="${currentVideoPath}"></video>`,
                  }}
                />
              </video>

              {/* Error Overlay */}
              {videoError && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 text-white z-10 p-4 text-center">
                  <AlertCircle size={40} className="text-red-500 mb-2" />
                  <h4 className="font-bold">Playback Error</h4>
                  <p className="text-sm text-gray-300">{videoError}</p>
                  <button
                    onClick={() => setUseInternalPlayer(false)}
                    className="mt-4 bg-gray-600 hover:bg-gray-700 text-white font-medium py-1 px-3 rounded text-xs transition"
                  >
                    Switch to External Player
                  </button>
                </div>
              )}

              {/* Controls Bar */}
              <div className="w-full bg-gray-900 text-white p-2 flex items-center gap-4">
                <button
                  onClick={togglePlayback}
                  className="hover:text-blue-400"
                >
                  {isPlaying ? <Pause size={20} /> : <Play size={20} />}
                </button>

                <div className="flex items-center gap-2">
                  <Volume2 size={16} />
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={volume}
                    onChange={(e) => setVolume(parseFloat(e.target.value))}
                    className="w-20"
                  />
                </div>

                <span className="font-mono text-xs">
                  {formatTime(currentTime)}
                </span>

                <input
                  type="range"
                  className="flex-1 mx-2"
                  min={0}
                  max={duration || 100}
                  value={currentTime}
                  onChange={handleSeek}
                />

                <span className="font-mono text-xs">
                  {formatTime(duration)}
                </span>
              </div>
            </div>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-900 rounded border border-dashed border-gray-400 text-gray-500">
              <Monitor size={48} className="mb-2 opacity-50" />
              <p>Video playing in external window.</p>
              <p className="text-xs italic mt-1">
                Use slider to sync extraction timestamps.
              </p>
              <input
                type="range"
                className="w-1/2 mt-4"
                min={0}
                max={duration || 100}
                value={currentTime}
                onChange={(e) => setCurrentTime(parseFloat(e.target.value))}
              />
            </div>
          )}
        </div>
      )}

      {/* 4. Extraction Controls (Conditional) */}
      {currentVideoPath && (
        <div className="border p-4 rounded bg-white dark:bg-gray-800 shadow-sm">
          <h3 className="font-bold mb-4">Extraction Settings</h3>

          <div className="flex flex-wrap gap-6 items-end">
            <label className="flex flex-col text-sm">
              Output Size:
              <select
                className="border rounded p-1 mt-1 dark:bg-gray-700"
                value={extractResIndex}
                onChange={(e) => setExtractResIndex(Number(e.target.value))}
              >
                {RESOLUTIONS.map((r, i) => (
                  <option key={i} value={i}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-2 text-sm mb-1">
              <input
                type="checkbox"
                checked={isExtractVertical}
                onChange={(e) => setIsExtractVertical(e.target.checked)}
              />
              Vertical Output
            </label>

            <label className="flex flex-col text-sm w-20">
              GIF FPS:
              <input
                type="number"
                min={1}
                max={60}
                value={gifFps}
                onChange={(e) => setGifFps(Number(e.target.value))}
                className="border rounded p-1 mt-1 dark:bg-gray-700"
              />
            </label>

            <label className="flex items-center gap-2 text-sm mb-1">
              <input
                type="checkbox"
                checked={muteAudio}
                onChange={(e) => setMuteAudio(e.target.checked)}
              />
              Mute Audio
            </label>
          </div>

          <div className="h-px bg-gray-200 dark:bg-gray-700 my-4" />

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2 items-center">
            <button
              onClick={handleSnapshot}
              className="flex items-center gap-2 bg-gray-100 dark:bg-gray-700 px-3 py-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition"
            >
              <Camera size={16} />
              Snapshot Frame
            </button>

            <div className="w-px h-8 bg-gray-300 mx-2" />

            <button
              onClick={() => setStartTime(currentTime)}
              className="px-3 py-2 rounded bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 text-sm font-mono"
            >
              Start: {startTime !== null ? formatTime(startTime) : "--:--"}
            </button>

            <button
              onClick={() => setEndTime(currentTime)}
              className="px-3 py-2 rounded bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 text-sm font-mono"
            >
              End: {endTime !== null ? formatTime(endTime) : "--:--"}
            </button>

            <button
              onClick={() => handleExtractRange("frames")}
              disabled={startTime === null || endTime === null}
              className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed ml-auto"
            >
              <Scissors size={16} />
              Extract Range
            </button>

            <button
              onClick={() => handleExtractRange("video")}
              disabled={startTime === null || endTime === null}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileVideo size={16} />
              Video
            </button>

            <button
              onClick={() => handleExtractRange("gif")}
              disabled={startTime === null || endTime === null}
              className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Film size={16} />
              GIF
            </button>
          </div>
        </div>
      )}

      {/* 5. Results Gallery */}
      <div className="flex-1 flex flex-col border rounded bg-white dark:bg-gray-800 shadow-sm overflow-hidden min-h-[400px]">
        <div className="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50">
          <h3 className="font-bold">
            Extraction Gallery ({resultsGallery.items.length})
          </h3>
          {resultsGallery.selectedPaths.size > 0 && (
            <button
              onClick={resultsGallery.actions.deleteSelected}
              className="flex items-center gap-2 text-red-600 hover:text-red-700 text-sm font-medium"
            >
              <Trash2 size={16} />
              Delete {resultsGallery.selectedPaths.size} Items
            </button>
          )}
        </div>

        <div className="flex-1 relative">
          <MarqueeScrollArea
            onSelectionChanged={(set, isCtrl) =>
              resultsGallery.actions.selectBatch(set, isCtrl)
            }
          >
            <div className="flex flex-wrap content-start p-2 gap-2">
              {resultsGallery.paginatedItems.map((item, idx) => (
                <ClickableLabel
                  key={item.path + idx}
                  path={item.path}
                  src={item.thumbnail}
                  isVideo={item.isVideo}
                  isSelected={currentVideoPath === item.path}
                  onPathClicked={(p) =>
                    resultsGallery.actions.selectItem(p, true)
                  }
                />
              ))}
              {resultsGallery.items.length === 0 && (
                <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 mt-20">
                  <FolderOpen size={48} className="mb-4 opacity-50" />
                  <p>
                    Extracted frames (or scanned output files) will appear here.
                  </p>
                </div>
              )}
            </div>
          </MarqueeScrollArea>
        </div>

        {/* Pagination Bar */}
        <div className="p-2 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex justify-between items-center text-sm">
          <div className="flex items-center gap-2">
            <span>Images per page:</span>
            <select
              className="border rounded p-1 dark:bg-gray-700"
              value={resultsGallery.pagination.itemsPerPage}
              onChange={(e) =>
                resultsGallery.pagination.setItemsPerPage(
                  Number(e.target.value),
                )
              }
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={1000}>1000</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={resultsGallery.pagination.prevPage}
              disabled={resultsGallery.pagination.currentPage === 0}
              className="px-3 py-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
            >
              Previous
            </button>

            <span className="font-mono">
              Page {resultsGallery.pagination.currentPage + 1} /{" "}
              {resultsGallery.pagination.totalPages || 1}
            </span>

            <button
              onClick={resultsGallery.pagination.nextPage}
              disabled={
                resultsGallery.pagination.currentPage >=
                resultsGallery.pagination.totalPages - 1
              }
              className="px-3 py-1 border rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
