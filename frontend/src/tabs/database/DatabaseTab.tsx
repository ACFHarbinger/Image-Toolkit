import { forwardRef, useState, useImperativeHandle } from "react";
import {
  Database,
  Trash2,
  Plus,
  Server,
  FileJson,
  FolderTree,
  Tag,
} from "lucide-react";

interface DatabaseTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number,
  ) => void;
}

export interface DatabaseTabHandle {
  getData: () => any;
}

// Simple Table Component for display
const SimpleTable = ({
  headers,
  data,
  onRemove,
}: {
  headers: string[];
  data: string[][];
  onRemove: (idx: number) => void;
}) => (
  <div className="w-full border rounded-md overflow-hidden dark:border-gray-700 bg-white dark:bg-gray-800">
    <div className="flex bg-gray-100 dark:bg-gray-700 font-bold text-xs p-2">
      {headers.map((h, i) => (
        <div key={i} className="flex-1 px-2">
          {h}
        </div>
      ))}
      <div className="w-10"></div>
    </div>
    <div className="max-h-40 overflow-y-auto">
      {data.map((row, idx) => (
        <div
          key={idx}
          className="flex border-t dark:border-gray-700 p-2 text-xs items-center hover:bg-gray-50 dark:hover:bg-gray-700/50"
        >
          {row.map((cell, cIdx) => (
            <div key={cIdx} className="flex-1 px-2 truncate">
              {cell}
            </div>
          ))}
          <button
            onClick={() => onRemove(idx)}
            className="w-8 h-8 flex items-center justify-center text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      {data.length === 0 && (
        <div className="p-4 text-center text-gray-500 text-xs italic">
          No data available.
        </div>
      )}
    </div>
  </div>
);

const DatabaseTab = forwardRef<DatabaseTabHandle, DatabaseTabProps>(
  ({ showModal }, ref) => {
    // --- Connection State ---
    const [dbConfig, setDbConfig] = useState({
      host: "localhost",
      port: "5432",
      user: "postgres",
      password: "",
      name: "imagedb",
    });
    const [isConnected, setIsConnected] = useState(false);

    // --- Mock Data State ---
    const [groups, setGroups] = useState<string[][]>([]);
    const [subgroups, setSubgroups] = useState<string[][]>([]);
    const [tags, setTags] = useState<string[][]>([]);

    // --- Inputs State ---
    const [newGroup, setNewGroup] = useState("");
    const [newSubgroup, setNewSubgroup] = useState("");
    const [parentGroup, setParentGroup] = useState("");
    const [newTag, setNewTag] = useState("");
    const [tagType, setTagType] = useState("");

    useImperativeHandle(ref, () => ({
      getData: () => ({
        action: "database_config",
        config: dbConfig,
      }),
    }));

    const handleConnect = () => {
      if (!dbConfig.host || !dbConfig.user || !dbConfig.name) {
        showModal("Please fill in all connection fields.", "error");
        return;
      }
      setIsConnected(true);
      showModal(`Connected to PostgreSQL DB: ${dbConfig.name}`, "success");
      // Mock loading data
      setGroups([["Photography"], ["Wallpapers"], ["Textures"]]);
      setTags([
        ["sunset", "General"],
        ["4k", "Meta"],
        ["nature", "General"],
      ]);
    };

    const handleDisconnect = () => {
      setIsConnected(false);
      showModal("Disconnected from database.", "info");
    };

    return (
      <div className="p-6 space-y-6 max-w-4xl mx-auto">
        {/* 1. Connection Section */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-gray-800 dark:text-gray-100">
            <Database size={20} className="text-violet-500" /> PostgreSQL
            Connection
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <label className="text-sm">
              Host:{" "}
              <input
                type="text"
                value={dbConfig.host}
                onChange={(e) =>
                  setDbConfig({ ...dbConfig, host: e.target.value })
                }
                className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </label>
            <label className="text-sm">
              Port:{" "}
              <input
                type="text"
                value={dbConfig.port}
                onChange={(e) =>
                  setDbConfig({ ...dbConfig, port: e.target.value })
                }
                className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </label>
            <label className="text-sm">
              User:{" "}
              <input
                type="text"
                value={dbConfig.user}
                onChange={(e) =>
                  setDbConfig({ ...dbConfig, user: e.target.value })
                }
                className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </label>
            <label className="text-sm">
              Password:{" "}
              <input
                type="password"
                value={dbConfig.password}
                onChange={(e) =>
                  setDbConfig({ ...dbConfig, password: e.target.value })
                }
                className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </label>
            <label className="text-sm md:col-span-2">
              Database Name:{" "}
              <input
                type="text"
                value={dbConfig.name}
                onChange={(e) =>
                  setDbConfig({ ...dbConfig, name: e.target.value })
                }
                className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
              />
            </label>
          </div>

          <div className="flex gap-3">
            {!isConnected ? (
              <button
                onClick={handleConnect}
                className="px-4 py-2 bg-violet-600 text-white rounded hover:bg-violet-700 font-medium shadow-sm flex items-center gap-2"
              >
                <Server size={16} /> Connect
              </button>
            ) : (
              <>
                <button
                  onClick={handleDisconnect}
                  className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 font-medium shadow-sm"
                >
                  Disconnect
                </button>
                <button
                  onClick={() =>
                    showModal("Database reset simulated.", "error")
                  }
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 font-medium shadow-sm ml-auto"
                >
                  ⚠️ Reset DB
                </button>
              </>
            )}
          </div>
        </div>

        {/* 2. Statistics Bar */}
        <div
          className={`p-3 rounded-md font-bold text-center text-white shadow-sm ${isConnected ? "bg-green-600" : "bg-red-500"}`}
        >
          {isConnected
            ? `📊 Statistics: Images: 1,240 | Tags: ${tags.length} | Groups: ${groups.length} | Subgroups: ${subgroups.length}`
            : "Not connected to database"}
        </div>

        {/* 3. Populate Section (Only visible if connected) */}
        <div
          className={`space-y-6 transition-opacity duration-300 ${isConnected ? "opacity-100" : "opacity-50 pointer-events-none"}`}
        >
          {/* Auto Populate */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <h4 className="font-bold mb-2 flex items-center gap-2">
              <FolderTree size={18} /> Automatic Population
            </h4>
            <p className="text-xs text-gray-500 mb-3 italic">
              Scans local source path. Top-level folders become Groups,
              second-level become Subgroups.
            </p>
            <button
              onClick={() => showModal("Scanning source directory...", "info")}
              className="w-full py-2 bg-green-500 text-white rounded hover:bg-green-600 font-medium shadow-sm"
            >
              Auto-Sync Groups and Subgroups
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Groups Management */}
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h4 className="font-bold mb-4 border-b pb-2 dark:border-gray-700">
                Manage Groups
              </h4>
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  placeholder="New Group Name"
                  value={newGroup}
                  onChange={(e) => setNewGroup(e.target.value)}
                  className="flex-1 p-2 text-sm border rounded dark:bg-gray-700 dark:border-gray-600"
                />
                <button
                  onClick={() => {
                    setGroups([...groups, [newGroup]]);
                    setNewGroup("");
                  }}
                  className="p-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  <Plus size={18} />
                </button>
              </div>
              <SimpleTable
                headers={["Group Name"]}
                data={groups}
                onRemove={(i) => {
                  const newG = [...groups];
                  newG.splice(i, 1);
                  setGroups(newG);
                }}
              />
            </div>

            {/* Subgroups Management */}
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h4 className="font-bold mb-4 border-b pb-2 dark:border-gray-700">
                Manage Subgroups
              </h4>
              <div className="flex flex-col gap-2 mb-4">
                <select
                  value={parentGroup}
                  onChange={(e) => setParentGroup(e.target.value)}
                  className="w-full p-2 text-sm border rounded dark:bg-gray-700 dark:border-gray-600"
                >
                  <option value="">Select Parent Group...</option>
                  {groups.map((g, i) => (
                    <option key={i} value={g[0]}>
                      {g[0]}
                    </option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="New Subgroup Name"
                    value={newSubgroup}
                    onChange={(e) => setNewSubgroup(e.target.value)}
                    className="flex-1 p-2 text-sm border rounded dark:bg-gray-700 dark:border-gray-600"
                  />
                  <button
                    onClick={() => {
                      setSubgroups([
                        ...subgroups,
                        [newSubgroup, parentGroup || "None"],
                      ]);
                      setNewSubgroup("");
                    }}
                    className="p-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    <Plus size={18} />
                  </button>
                </div>
              </div>
              <SimpleTable
                headers={["Subgroup", "Parent"]}
                data={subgroups}
                onRemove={(i) => {
                  const newS = [...subgroups];
                  newS.splice(i, 1);
                  setSubgroups(newS);
                }}
              />
            </div>
          </div>

          {/* Tags Management */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <h4 className="font-bold mb-4 border-b pb-2 dark:border-gray-700 flex items-center gap-2">
              <Tag size={18} /> Manage Tags
            </h4>

            {/* Create Tag */}
            <div className="flex flex-col md:flex-row gap-2 mb-6">
              <input
                type="text"
                placeholder="Tag Name(s) comma separated"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                className="flex-[2] p-2 text-sm border rounded dark:bg-gray-700 dark:border-gray-600"
              />
              <select
                value={tagType}
                onChange={(e) => setTagType(e.target.value)}
                className="flex-1 p-2 text-sm border rounded dark:bg-gray-700 dark:border-gray-600"
              >
                <option value="">No Type</option>
                <option value="Artist">Artist</option>
                <option value="Series">Series</option>
                <option value="Character">Character</option>
                <option value="General">General</option>
                <option value="Meta">Meta</option>
              </select>
              <button
                onClick={() => {
                  setTags([...tags, [newTag, tagType || "None"]]);
                  setNewTag("");
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 font-medium text-sm"
              >
                Create Tag
              </button>
            </div>

            {/* Bulk Import */}
            <div className="bg-gray-50 dark:bg-gray-900/50 p-3 rounded mb-4 border border-dashed border-gray-300 dark:border-gray-600">
              <h5 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <FileJson size={14} /> Bulk Import from JSON
              </h5>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Select JSON file..."
                  readOnly
                  className="flex-1 p-2 text-xs border rounded bg-white dark:bg-gray-800 dark:border-gray-600"
                />
                <button
                  onClick={() => showModal("JSON Browse Simulated", "info")}
                  className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded text-xs"
                >
                  Browse
                </button>
                <button
                  onClick={() => showModal("Importing...", "info")}
                  className="px-3 py-1 bg-sky-500 text-white hover:bg-sky-600 rounded text-xs"
                >
                  Import
                </button>
              </div>
            </div>

            {/* Existing Tags Table */}
            <SimpleTable
              headers={["Tag Name", "Type"]}
              data={tags}
              onRemove={(i) => {
                const newT = [...tags];
                newT.splice(i, 1);
                setTags(newT);
              }}
            />
          </div>
        </div>
      </div>
    );
  },
);

export default DatabaseTab;
