import { forwardRef, useState, useImperativeHandle } from 'react';
import { Network, Plus, Trash2, Play, Ban } from 'lucide-react';

interface WebRequestsTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error', duration?: number) => void;
}

const WebRequestsTab = forwardRef((props: WebRequestsTabProps, ref) => {
  const [url, setUrl] = useState('');
  
  // Request Builder State
  const [reqType, setReqType] = useState('GET');
  const [reqParam, setReqParam] = useState('');
  const [requests, setRequests] = useState<string[]>([]);

  // Action Builder State
  const [actType, setActType] = useState('Print Response Status Code');
  const [actParam, setActParam] = useState('');
  const [actions, setActions] = useState<string[]>([]);

  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  useImperativeHandle(ref, () => ({
    getData: () => ({ url, requests, actions })
  }));

  const addRequest = () => {
    const r = reqParam ? `[${reqType}] | Data: ${reqParam}` : `[${reqType}]`;
    setRequests([...requests, r]);
    setReqParam('');
  };

  const addAction = () => {
    const a = actParam ? `${actType} | Param: ${actParam}` : actType;
    setActions([...actions, a]);
    setActParam('');
  };

  const removeRequest = (idx: number) => setRequests(requests.filter((_, i) => i !== idx));
  const removeAction = (idx: number) => setActions(actions.filter((_, i) => i !== idx));

  const handleRun = () => {
    if (!url) return props.showModal("Please set a Base URL.", "error");
    if (requests.length === 0) return props.showModal("Add at least one request.", "error");
    
    setIsRunning(true);
    setLogs(["Starting request sequence..."]);
    
    // Simulate async process
    setTimeout(() => {
        setLogs(prev => [...prev, `Target: ${url}`]);
        requests.forEach((req, i) => {
            setTimeout(() => {
                setLogs(prev => [...prev, `Executing Request ${i+1}: ${req}`]);
                if (i === requests.length - 1) {
                    setIsRunning(false);
                    props.showModal("Requests completed.", "success");
                }
            }, (i + 1) * 1000);
        });
    }, 500);
  };

  return (
    <div className="p-6 flex flex-col gap-6 h-full">
      
      {/* 1. Request Config */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <h3 className="font-bold mb-4 flex items-center gap-2"><Network size={18} className="text-violet-500"/> Request Configuration</h3>
        <input 
            type="text" placeholder="Base URL (https://api.example.com)..." 
            value={url} onChange={e => setUrl(e.target.value)}
            className="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1 min-h-0">
        
        {/* 2. Request Builder */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col">
            <h4 className="font-bold mb-2 text-sm text-gray-600 dark:text-gray-300">1. Request List (Sequence)</h4>
            
            <div className="flex gap-2 mb-2">
                <select value={reqType} onChange={e => setReqType(e.target.value)} className="p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600">
                    <option>GET</option>
                    <option>POST</option>
                </select>
                <input type="text" placeholder="Data / Suffix" value={reqParam} onChange={e => setReqParam(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
                <button onClick={addRequest} className="px-3 bg-blue-600 text-white rounded hover:bg-blue-700"><Plus size={16}/></button>
            </div>

            <div className="flex-1 border rounded bg-gray-50 dark:bg-gray-900 p-2 overflow-y-auto">
                {requests.map((r, i) => (
                    <div key={i} className="flex justify-between items-center p-2 mb-1 bg-white dark:bg-gray-800 rounded shadow-sm text-sm">
                        <span>{i+1}. {r}</span>
                        <button onClick={() => removeRequest(i)} className="text-red-500 hover:bg-red-100 p-1 rounded"><Trash2 size={14}/></button>
                    </div>
                ))}
                {requests.length === 0 && <p className="text-center text-gray-400 text-xs italic mt-4">No requests added.</p>}
            </div>
        </div>

        {/* 3. Action Builder */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col">
            <h4 className="font-bold mb-2 text-sm text-gray-600 dark:text-gray-300">2. Response Actions</h4>
            
            <div className="flex gap-2 mb-2">
                <select value={actType} onChange={e => setActType(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600">
                    <option>Print Response URL</option>
                    <option>Print Status Code</option>
                    <option>Save Content (Binary)</option>
                </select>
                <input type="text" placeholder="Param (e.g. path)" value={actParam} onChange={e => setActParam(e.target.value)} className="w-24 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
                <button onClick={addAction} className="px-3 bg-green-600 text-white rounded hover:bg-green-700"><Plus size={16}/></button>
            </div>

            <div className="flex-1 border rounded bg-gray-50 dark:bg-gray-900 p-2 overflow-y-auto">
                {actions.map((a, i) => (
                    <div key={i} className="flex justify-between items-center p-2 mb-1 bg-white dark:bg-gray-800 rounded shadow-sm text-sm">
                        <span>{a}</span>
                        <button onClick={() => removeAction(i)} className="text-red-500 hover:bg-red-100 p-1 rounded"><Trash2 size={14}/></button>
                    </div>
                ))}
                {actions.length === 0 && <p className="text-center text-gray-400 text-xs italic mt-4">No actions defined.</p>}
            </div>
        </div>

      </div>

      {/* 4. Logs & Control */}
      <div className="bg-black text-green-400 font-mono text-xs p-4 rounded-lg h-32 overflow-y-auto shadow-inner">
        {logs.map((l, i) => <div key={i}>&gt; {l}</div>)}
        {logs.length === 0 && <div className="text-gray-600">Ready to execute requests...</div>}
      </div>

      <div className="flex-shrink-0">
        {!isRunning ? (
            <button onClick={handleRun} className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold rounded shadow-md hover:opacity-90 flex items-center justify-center gap-2">
                <Play size={20}/> Run Requests
            </button>
        ) : (
            <button onClick={() => {setIsRunning(false); setLogs(p => [...p, "Cancelled."]);}} className="w-full py-3 bg-red-600 text-white font-bold rounded shadow-md hover:bg-red-700 flex items-center justify-center gap-2">
                <Ban size={20}/> Cancel
            </button>
        )}
      </div>

    </div>
  );
});

export default WebRequestsTab;