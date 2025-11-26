// Saves options to browser.storage
const saveOptions = async () => {
  const folderName = document.getElementById('folder').value;
  
  // Basic validation to remove forbidden characters
  const cleanName = folderName.replace(/[<>:"/\\|?*]/g, '');

  await browser.storage.local.set({ targetFolder: cleanName });
  
  const status = document.getElementById('status');
  status.textContent = 'Directory Saved!';
  document.getElementById('folder').value = cleanName;
  
  setTimeout(() => {
    status.textContent = '';
  }, 1500);
};

// Restores select box and checkbox state using the preferences
const restoreOptions = async () => {
  const result = await browser.storage.local.get('targetFolder');
  document.getElementById('folder').value = result.targetFolder || 'data';
};

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);