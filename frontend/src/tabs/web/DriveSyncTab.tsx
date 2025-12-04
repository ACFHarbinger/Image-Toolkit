import { forwardRef, useState, useImperativeHandle } from 'react';
import { Cloud, FolderSync, Settings, Eye, Share2, UploadCloud, DownloadCloud, Trash2, ShieldAlert } from 'lucide-react';

interface DriveSyncTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error', duration?: number) => void;
}

const DriveSyncTab = forwardRef((props: DriveSyncTabProps, ref) => {
  const [provider, setProvider] = useState('Google Drive (Service Account)');
  const [keyFile, setKeyFile] = useState('');
  const [clientSecrets, setClientSecrets] = useState('');
  const [tokenFile, setTokenFile] = useState('');
  const [localPath, setLocalPath] = useState('');
  const [remotePath, setRemotePath] = useState('');
  const [shareEmail, setShareEmail] = useState('');
  const [dryRun, setDryRun] = useState(true);
  
  // Sync Behaviors
  const [localAction, setLocalAction] = useState<'upload' | 'delete_local' | 'ignore'>('upload');
  const [remoteAction, setRemoteAction] = useState<'download' | 'delete_remote' | 'ignore'>('download');

  useImperativeHandle(ref, () => ({
    getData: () => ({
      provider, localPath, remotePath, dryRun
    })
  }));

  const handleSync = () => {
    props.showModal(`Starting Sync [${dryRun ? 'DRY RUN' : 'LIVE'}]...\nLocal: ${localPath}\nRemote: ${remotePath}`, 'info');
  };

  return (
    <div className="p-6 flex flex-col gap-6">
      {/* Configuration Group */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
          <Cloud size={18} className="text-violet-500"/> Cloud Sync Configuration
        </h3>
        
        <div className="space-y-4">
          <label className="block text-sm">
            Cloud Provider:
            <select 
              value={provider} onChange={e => setProvider(e.target.value)}
              className="w-full mt-1 p-2 border rounded dark:bg-gray-700 dark:border-gray-600"
            >
              <option>Google Drive (Service Account)</option>
              <option>Google Drive (Personal Account)</option>
              <option>Dropbox</option>
              <option>OneDrive</option>
            </select>
          </label>

          {provider.includes('Service Account') ? (
            <div className="flex gap-2">
              <input type="text" placeholder="Path to service_account_key.json" value={keyFile} onChange={e => setKeyFile(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
              <button className="px-3 bg-gray-200 dark:bg-gray-700 rounded text-sm">Browse</button>
            </div>
          ) : (
            <>
              <div className="flex gap-2">
                <input type="text" placeholder="Path to client_secrets.json" value={clientSecrets} onChange={e => setClientSecrets(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
                <button className="px-3 bg-gray-200 dark:bg-gray-700 rounded text-sm">Browse</button>
              </div>
              <input type="text" placeholder="Path to store token.json" value={tokenFile} onChange={e => setTokenFile(e.target.value)} className="w-full p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
            </>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Local Source</span>
              <div className="flex gap-2 mt-1">
                <input type="text" placeholder="Local directory..." value={localPath} onChange={e => setLocalPath(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
                <button className="px-3 bg-gray-200 dark:bg-gray-700 rounded text-sm">Browse</button>
              </div>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Remote Destination</span>
              <input type="text" placeholder="Remote folder (e.g. Backups/2024)" value={remotePath} onChange={e => setRemotePath(e.target.value)} className="w-full mt-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
            </div>
          </div>

          {provider.includes('Service Account') && (
            <div className="flex items-center gap-2">
              <label className="whitespace-nowrap text-sm">Share With:</label>
              <input type="text" placeholder="user@email.com (Optional)" value={shareEmail} onChange={e => setShareEmail(e.target.value)} className="flex-1 p-2 border rounded text-sm dark:bg-gray-700 dark:border-gray-600"/>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 mt-4">
          <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium flex items-center gap-2">
            <Eye size={14}/> View Remote Map
          </button>
          {provider.includes('Service Account') && (
            <button className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm font-medium flex items-center gap-2">
              <Share2 size={14}/> Share Folder
            </button>
          )}
          <label className="flex items-center gap-2 text-sm ml-auto select-none cursor-pointer">
            <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} className="rounded text-violet-500"/>
            Perform Dry Run (Simulate)
          </label>
        </div>
      </div>

      {/* Sync Behavior Group */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2">
          <Settings size={18} className="text-gray-500"/> Sync Behavior
        </h3>
        
        <div className="space-y-4">
          {/* Local Orphans */}
          <div>
            <p className="text-sm font-bold text-blue-500 mb-2">Files found ONLY Locally (Local Orphans):</p>
            <div className="flex gap-4">
              <label className="flex items-center gap-1 text-sm cursor-pointer">
                <input type="radio" name="local" checked={localAction === 'upload'} onChange={() => setLocalAction('upload')} />
                <UploadCloud size={14}/> Upload to Remote
              </label>
              <label className="flex items-center gap-1 text-sm cursor-pointer text-red-500">
                <input type="radio" name="local" checked={localAction === 'delete_local'} onChange={() => setLocalAction('delete_local')} />
                <Trash2 size={14}/> Delete from Local
              </label>
              <label className="flex items-center gap-1 text-sm cursor-pointer text-gray-500">
                <input type="radio" name="local" checked={localAction === 'ignore'} onChange={() => setLocalAction('ignore')} />
                <ShieldAlert size={14}/> Do Nothing
              </label>
            </div>
          </div>

          {/* Remote Orphans */}
          <div>
            <p className="text-sm font-bold text-green-500 mb-2">Files found ONLY Remote (Remote Orphans):</p>
            <div className="flex gap-4">
              <label className="flex items-center gap-1 text-sm cursor-pointer">
                <input type="radio" name="remote" checked={remoteAction === 'download'} onChange={() => setRemoteAction('download')} />
                <DownloadCloud size={14}/> Download to Local
              </label>
              <label className="flex items-center gap-1 text-sm cursor-pointer text-red-500">
                <input type="radio" name="remote" checked={remoteAction === 'delete_remote'} onChange={() => setRemoteAction('delete_remote')} />
                <Trash2 size={14}/> Delete from Remote
              </label>
              <label className="flex items-center gap-1 text-sm cursor-pointer text-gray-500">
                <input type="radio" name="remote" checked={remoteAction === 'ignore'} onChange={() => setRemoteAction('ignore')} />
                <ShieldAlert size={14}/> Do Nothing
              </label>
            </div>
          </div>
        </div>
      </div>

      <button onClick={handleSync} className="w-full py-4 bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-bold rounded-lg shadow-lg hover:from-blue-700 hover:to-cyan-700 flex items-center justify-center gap-2 text-lg">
        <FolderSync size={24}/> Run Synchronization Now
      </button>
    </div>
  );
});

export default DriveSyncTab;