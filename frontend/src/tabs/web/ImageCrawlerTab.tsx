import { forwardRef, useState, useImperativeHandle } from "react";
import { Globe, Download, Settings, Play, Plus, Trash2 } from "lucide-react";

interface ImageCrawlerTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

const ImageCrawlerTab = forwardRef((props: ImageCrawlerTabProps, ref) => {
  const [crawlerType, setCrawlerType] = useState("General Web Crawler");
  const [downloadDir, setDownloadDir] = useState("");

  // General Settings
  const [targetUrl, setTargetUrl] = useState("");
  const [actions, setActions] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState("Find Parent Link (<a>)");
  const [currentParam, setCurrentParam] = useState("");

  // Board Settings
  const [boardUrl, setBoardUrl] = useState("https://danbooru.donmai.us");
  const [tags, setTags] = useState("");
  const [limit, setLimit] = useState("20");

  useImperativeHandle(ref, () => ({
    getData: () => ({ crawlerType, downloadDir, targetUrl }),
  }));

  const addAction = () => {
    const act = currentParam
      ? `${currentAction} | Param: ${currentParam}`
      : currentAction;
    setActions([...actions, act]);
    setCurrentParam("");
  };

  const removeAction = (idx: number) => {
    setActions(actions.filter((_, i) => i !== idx));
  };

  const handleRun = () => {
    props.showModal(
      `Starting ${crawlerType}...\nTarget: ${crawlerType.includes("General") ? targetUrl : boardUrl}`,
      "success",
    );
  };

  return (
    <div className="p-6 flex flex-col gap-6 h-full overflow-y-auto">
      {/* 1. Type Selection */}
      <div className="flex items-center gap-4">
        <label className="font-bold text-gray-700 dark:text-gray-200">
          Crawler Type:
        </label>
        <select
          value={crawlerType}
          onChange={(e) => setCrawlerType(e.target.value)}
          className="flex-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
        >
          <option>General Web Crawler</option>
          <option>Image Board Crawler (Danbooru API)</option>
          <option>Image Board Crawler (Gelbooru API)</option>
          <option>Image Board Crawler (Sankaku Complex API)</option>
        </select>
      </div>

      {/* 2. Specific Settings Area */}
      <div className="flex-1 border rounded-lg p-4 bg-white dark:bg-gray-800 shadow-sm">
        {crawlerType === "General Web Crawler" ? (
          <div className="space-y-4">
            <h3 className="font-bold flex items-center gap-2">
              <Globe size={16} /> Web Scraper Settings
            </h3>

            {/* Login Group */}
            <div className="border p-3 rounded dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30">
              <span className="text-xs font-bold uppercase text-gray-500">
                Login (Optional)
              </span>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
                <input
                  type="text"
                  placeholder="Login URL"
                  className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <input
                  type="text"
                  placeholder="Username"
                  className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <input
                  type="password"
                  placeholder="Password"
                  className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Target URL (e.g. https://site.com/gallery?page=1)"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                className="flex-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </div>

            {/* Actions Builder */}
            <div>
              <span className="text-sm font-semibold">Actions Sequence:</span>
              <div className="flex gap-2 mt-1">
                <select
                  value={currentAction}
                  onChange={(e) => setCurrentAction(e.target.value)}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                >
                  <option>Find Parent Link (&lt;a&gt;)</option>
                  <option>Download Image from Element</option>
                  <option>Click Element by Text</option>
                  <option>Wait X Seconds</option>
                  <option>Find Element by CSS Selector</option>
                </select>
                <input
                  type="text"
                  placeholder="Parameter"
                  value={currentParam}
                  onChange={(e) => setCurrentParam(e.target.value)}
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <button
                  onClick={addAction}
                  className="px-3 bg-blue-600 text-white rounded"
                >
                  <Plus size={16} />
                </button>
              </div>

              <div className="mt-2 h-32 border rounded overflow-y-auto bg-gray-50 dark:bg-gray-900 dark:border-gray-700 p-2">
                {actions.map((act, i) => (
                  <div
                    key={i}
                    className="flex justify-between items-center text-sm p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                  >
                    <span>
                      {i + 1}. {act}
                    </span>
                    <button
                      onClick={() => removeAction(i)}
                      className="text-red-500"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                {actions.length === 0 && (
                  <p className="text-gray-400 text-xs italic text-center mt-4">
                    No actions defined.
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <h3 className="font-bold flex items-center gap-2">
              <Settings size={16} /> API Configuration
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-gray-500">
                  Board URL
                </label>
                <input
                  type="text"
                  value={boardUrl}
                  onChange={(e) => setBoardUrl(e.target.value)}
                  className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500">
                  Resource
                </label>
                <input
                  type="text"
                  placeholder="posts"
                  className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-bold text-gray-500">
                  Tags
                </label>
                <input
                  type="text"
                  placeholder="1girl scenic original"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500">
                  Limit per page
                </label>
                <input
                  type="number"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                  className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500">
                  Max Pages
                </label>
                <input
                  type="number"
                  defaultValue={5}
                  className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
            </div>

            <div className="border-t pt-4 mt-2 dark:border-gray-700">
              <span className="text-xs font-bold text-gray-500">
                Auth (Optional)
              </span>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  placeholder="Username"
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
                <input
                  type="password"
                  placeholder="API Key"
                  className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 3. Output Config */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <h4 className="font-bold mb-2 text-sm flex items-center gap-2">
          <Download size={16} /> Output Configuration
        </h4>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Download Directory..."
            value={downloadDir}
            onChange={(e) => setDownloadDir(e.target.value)}
            className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"
          />
          <button className="px-3 bg-gray-200 dark:bg-gray-700 rounded text-sm">
            Browse
          </button>
        </div>
      </div>

      <button
        onClick={handleRun}
        className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold rounded-lg shadow-md hover:opacity-90 flex items-center justify-center gap-2"
      >
        <Play size={20} /> Run Crawler
      </button>
    </div>
  );
});

export default ImageCrawlerTab;
