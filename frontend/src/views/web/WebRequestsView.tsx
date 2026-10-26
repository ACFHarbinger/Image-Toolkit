import React, { useState } from "react";
import {
  Globe,
  Play,
  Plus,
  Trash2,
  Terminal,
  Send,
  CheckCircle2,
  AlertCircle,
  Clock,
} from "lucide-react";
import type { HostClient } from "../../hostclient";
import type {
  ActionItem,
  ExecuteResult,
  RequestItem,
  SequenceItemResult,
} from "../../../../contracts/generated/ts";

export interface WebRequestsViewProps {
  hostClient?: HostClient;
  showModal?: (message: string, type?: "info" | "error" | "success") => void;
}

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "HEAD" | "PATCH";

export function WebRequestsView({ hostClient, showModal }: WebRequestsViewProps) {
  const [activeTab, setActiveTab] = useState<"sequence" | "single">("sequence");
  const [baseUrl, setBaseUrl] = useState("https://httpbin.org");

  // Sequence state
  const [reqType, setReqType] = useState<HttpMethod>("GET");
  const [reqParam, setReqParam] = useState("/get");
  const [requests, setRequests] = useState<RequestItem[]>([{ type: "GET", param: "/get" }]);

  const [actType, setActType] = useState<ActionItem["type"]>("Print Response Status Code");
  const [actParam, setActParam] = useState("");
  const [actions, setActions] = useState<ActionItem[]>([
    { type: "Print Response Status Code", param: "" },
    { type: "Print Response Content (Text)", param: "" },
  ]);

  // Single request state
  const [singleUrl, setSingleUrl] = useState("https://httpbin.org/json");
  const [singleMethod, setSingleMethod] = useState<HttpMethod>("GET");
  const [singleBody, setSingleBody] = useState("");
  const [singleResult, setSingleResult] = useState<ExecuteResult | null>(null);

  // Common execution state
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [sequenceItems, setSequenceItems] = useState<SequenceItemResult[]>([]);

  const notify = (msg: string, type: "info" | "error" | "success" = "info") => showModal?.(msg, type);

  const addRequest = () => {
    setRequests([...requests, { type: reqType, param: reqParam.trim() }]);
    setReqParam("");
  };

  const addAction = () => {
    setActions([...actions, { type: actType, param: actParam.trim() }]);
    setActParam("");
  };

  const handleRunSequence = async () => {
    if (!baseUrl.trim()) return notify("Please specify a valid base URL.", "error");
    if (requests.length === 0) return notify("Please add at least one request.", "error");
    if (!hostClient) return notify("Host client bridge is not attached.", "error");

    setIsRunning(true);
    setLogs(["[CLIENT] Starting request sequence..."]);
    setSequenceItems([]);

    try {
      const res = await hostClient.webreqSequence({
        base_url: baseUrl.trim(),
        requests,
        actions,
      });
      setLogs(res.logs);
      setSequenceItems(res.items);
      notify(res.message, res.status === "completed" ? "success" : "error");
    } catch (err) {
      const msg = `Sequence failed: ${String(err)}`;
      setLogs((prev) => [...prev, `[ERROR] ${msg}`]);
      notify(msg, "error");
    } finally {
      setIsRunning(false);
    }
  };

  const handleRunSingle = async () => {
    if (!singleUrl.trim()) return notify("Please specify a URL to inspect.", "error");
    if (!hostClient) return notify("Host client bridge is not attached.", "error");

    setIsRunning(true);
    setSingleResult(null);

    try {
      const res = await hostClient.webreqExecute({
        url: singleUrl.trim(),
        method: singleMethod,
        body: singleBody,
      });
      setSingleResult(res);
      notify(res.error ? `Error: ${res.error}` : `HTTP ${res.status_code} in ${res.duration_ms}ms`, res.error ? "error" : "success");
    } catch (err) {
      notify(`Execution failed: ${String(err)}`, "error");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100 p-6 overflow-hidden">
      {/* Header and Mode Toggle */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-3">
          <Globe className="w-6 h-6 text-indigo-500" />
          <h2 className="text-xl font-bold tracking-tight">Web Requests Pipeline</h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-medium">
            B-02 / C++ Native
          </span>
        </div>
        <div className="flex rounded-lg bg-gray-200 dark:bg-gray-800 p-1">
          <button
            type="button"
            onClick={() => setActiveTab("sequence")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === "sequence" ? "bg-white dark:bg-gray-700 shadow-sm text-indigo-600 dark:text-indigo-400" : "text-gray-600 dark:text-gray-400"
            }`}
          >
            Sequential Pipeline
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("single")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === "single" ? "bg-white dark:bg-gray-700 shadow-sm text-indigo-600 dark:text-indigo-400" : "text-gray-600 dark:text-gray-400"
            }`}
          >
            Single Inspector
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0 pt-4">
        <div className="flex flex-col gap-4 overflow-y-auto pr-1">
          {activeTab === "sequence" ? (
            <>
              <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Base Target URL
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.example.com"
                    className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={handleRunSequence}
                    disabled={isRunning}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors"
                  >
                    <Play className="w-4 h-4 fill-current" />
                    {isRunning ? "Running..." : "Run Sequence"}
                  </button>
                </div>
              </div>

              {/* Request Builder */}
              <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col gap-3">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                  1. Request Sequence ({requests.length})
                </span>
                <div className="flex gap-2">
                  <select
                    value={reqType}
                    onChange={(e) => setReqType(e.target.value as HttpMethod)}
                    className="px-2.5 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 font-mono font-medium"
                  >
                    {(["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"] as const).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={reqParam}
                    onChange={(e) => setReqParam(e.target.value)}
                    placeholder="URL suffix (GET) or post data (POST)"
                    className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:ring-1 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={addRequest}
                    className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-sm font-medium rounded-lg flex items-center gap-1"
                  >
                    <Plus className="w-4 h-4" /> Add
                  </button>
                </div>

                <div className="max-h-40 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-700">
                  {requests.map((req, i) => (
                    <div
                      key={`req-${i}-${req.type}-${req.param}`}
                      className="flex items-center justify-between px-3 py-2 text-xs hover:bg-gray-50 dark:hover:bg-gray-750"
                    >
                      <div className="flex items-center gap-2 font-mono">
                        <span className="font-bold text-indigo-500 dark:text-indigo-400">[{req.type}]</span>
                        <span className="text-gray-700 dark:text-gray-300">{req.param || "/"}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setRequests(requests.filter((_, idx) => idx !== i))}
                        className="text-gray-400 hover:text-red-500 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Action Builder */}
              <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col gap-3">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                  2. Response Actions ({actions.length})
                </span>
                <div className="flex gap-2">
                  <select
                    value={actType}
                    onChange={(e) => setActType(e.target.value as any)}
                    className="flex-1 px-2.5 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900"
                  >
                    <option value="Print Response URL">Print Response URL</option>
                    <option value="Print Response Status Code">Print Response Status Code</option>
                    <option value="Print Response Headers">Print Response Headers</option>
                    <option value="Print Response Content (Text)">Print Response Content (Text)</option>
                    <option value="Save Response Content (Binary)">Save Response Content (Binary)</option>
                  </select>
                  {actType === "Save Response Content (Binary)" && (
                    <input
                      type="text"
                      value={actParam}
                      onChange={(e) => setActParam(e.target.value)}
                      placeholder="Destination file path"
                      className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900"
                    />
                  )}
                  <button
                    type="button"
                    onClick={addAction}
                    className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-xs font-medium rounded-lg flex items-center gap-1"
                  >
                    <Plus className="w-4 h-4" /> Add
                  </button>
                </div>

                <div className="max-h-36 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-700">
                  {actions.map((act, i) => (
                    <div
                      key={`act-${i}-${act.type}`}
                      className="flex items-center justify-between px-3 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-750"
                    >
                      <span className="text-gray-700 dark:text-gray-300">{act.type} {act.param ? `(${act.param})` : ""}</span>
                      <button
                        type="button"
                        onClick={() => setActions(actions.filter((_, idx) => idx !== i))}
                        className="text-gray-400 hover:text-red-500 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col gap-4">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                Single Request Execution
              </span>
              <div className="flex gap-2">
                <select
                  value={singleMethod}
                  onChange={(e) => setSingleMethod(e.target.value as HttpMethod)}
                  className="px-2.5 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 font-mono font-medium"
                >
                  {(["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"] as const).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <input
                  type="text"
                  value={singleUrl}
                  onChange={(e) => setSingleUrl(e.target.value)}
                  placeholder="https://api.example.com/data"
                  className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Request Payload (Body)</label>
                <textarea
                  value={singleBody}
                  onChange={(e) => setSingleBody(e.target.value)}
                  placeholder='{"key": "value"}'
                  rows={4}
                  className="w-full p-2.5 text-xs font-mono rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <button
                type="button"
                onClick={handleRunSingle}
                disabled={isRunning}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors"
              >
                <Send className="w-4 h-4" />
                {isRunning ? "Sending..." : "Execute Request"}
              </button>
            </div>
          )}
        </div>

        {/* Right Column: Execution Logs and Live Results */}
        <div className="flex flex-col gap-4 overflow-hidden">
          {activeTab === "single" && singleResult ? (
            <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col gap-3 flex-1 overflow-hidden">
              <div className="flex items-center justify-between border-b pb-2 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 text-xs font-bold rounded ${
                      singleResult.status_code >= 200 && singleResult.status_code < 300
                        ? "bg-green-100 text-green-700 dark:bg-green-950/70 dark:text-green-400"
                        : "bg-red-100 text-red-700 dark:bg-red-950/70 dark:text-red-400"
                    }`}
                  >
                    HTTP {singleResult.status_code}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{singleResult.status_text}</span>
                </div>
                <span className="text-xs text-gray-400 flex items-center gap-1 font-mono">
                  <Clock className="w-3.5 h-3.5" />
                  {singleResult.duration_ms} ms
                </span>
              </div>

              <div className="flex-1 overflow-y-auto flex flex-col gap-2">
                <span className="text-xs font-semibold text-gray-500">Response Content:</span>
                <pre className="p-3 bg-gray-950 text-gray-200 font-mono text-xs rounded-lg overflow-x-auto flex-1 whitespace-pre-wrap">
                  {singleResult.body || "<Empty response body>"}
                </pre>
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col flex-1 overflow-hidden">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-indigo-500" />
                  <span className="text-xs font-bold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                    Console Logs & Results
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setLogs([]);
                    setSequenceItems([]);
                  }}
                  className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  Clear
                </button>
              </div>

              <div className="flex-1 overflow-y-auto bg-gray-950 text-gray-200 p-3 rounded-lg font-mono text-xs space-y-1">
                {logs.length === 0 ? (
                  <span className="text-gray-600 italic">No request executions logged yet.</span>
                ) : (
                  logs.map((log, i) => (
                    <div
                      key={`log-${i}`}
                      className={
                        log.startsWith("[ERROR]") || log.startsWith("[CRITICAL]")
                          ? "text-red-400 font-semibold"
                          : log.startsWith("  > Action:")
                          ? "text-amber-300 pl-2"
                          : log.startsWith("Request complete")
                          ? "text-green-400 font-semibold"
                          : "text-gray-300"
                      }
                    >
                      {log}
                    </div>
                  ))
                )}
              </div>

              {sequenceItems.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs font-bold text-gray-500 uppercase tracking-wider block mb-1.5">
                    Summary Items ({sequenceItems.length})
                  </span>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {sequenceItems.map((it) => (
                      <div
                        key={`item-${it.index}`}
                        className="flex items-center justify-between text-xs py-1 px-2 rounded bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800"
                      >
                        <div className="flex items-center gap-2">
                          {it.error ? (
                            <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                          ) : (
                            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                          )}
                          <span className="font-mono font-medium">[{it.method}] {it.url}</span>
                        </div>
                        <span
                          className={`font-mono text-xs ${
                            it.status_code >= 200 && it.status_code < 300
                              ? "text-green-600 dark:text-green-400"
                              : "text-red-600 dark:text-red-400"
                          }`}
                        >
                          {it.status_code || "ERR"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
