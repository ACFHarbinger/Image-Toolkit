// Detect environment: Chrome uses 'chrome' + callbacks, Firefox uses 'browser' + Promises
const api = (typeof browser !== 'undefined') ? browser : chrome;

const saveOptions = () => {
  const folderName = document.getElementById('folder').value;
  // Basic validation to remove forbidden characters (keeping / for subfolders)
  const cleanName = folderName.replace(/[<>:"\\|?*]/g, '');

  const onSaved = () => {
    const status = document.getElementById('status');
    status.textContent = 'Directory Saved!';
    document.getElementById('folder').value = cleanName;
    setTimeout(() => {
      status.textContent = '';
    }, 1500);
  };

  // Handle Chrome (Callback) vs Firefox (Promise)
  const settings = { targetFolder: cleanName, turboMode: document.getElementById('turbo').checked };

  if (typeof browser !== 'undefined') {
    api.storage.local.set(settings).then(onSaved);
  } else {
    api.storage.local.set(settings, onSaved);
  }
};

const restoreOptions = () => {
  const onGot = (result) => {
    document.getElementById('folder').value = result.targetFolder || 'data';
    document.getElementById('turbo').checked = result.turboMode || false;
  };

  if (typeof browser !== 'undefined') {
    api.storage.local.get(['targetFolder', 'turboMode']).then(onGot);
  } else {
    api.storage.local.get(['targetFolder', 'turboMode'], onGot);
  }
};

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);