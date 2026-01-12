import React, { useState } from 'react';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import { Image } from 'lucide-react';

const WallpaperTab: React.FC = () => {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [style, setStyle] = useState('Fill');
  const [status, setStatus] = useState('');

  const handleSelectImage = async () => {
    try {
      const file = await open({
        multiple: false,
        filters: [{
          name: 'Images',
          extensions: ['png', 'jpg', 'jpeg', 'webp']
        }]
      });
      
      if (file) {
        setSelectedImage(file as string); // file is string path
      }
    } catch (err) {
      console.error(err);
      setStatus('Error selecting file');
    }
  };

  const handleSetWallpaper = async () => {
    if (!selectedImage) return;

    try {
      setStatus('Setting wallpaper...');
      const pathMap = { "0": selectedImage };
      
      await invoke('set_wallpaper', { 
        pathMap, 
        // Monitor argument is unused in our current simplified Rust implementation but defined in interface
        monitors: [0], 
        style 
      });
      
      setStatus('Wallpaper set successfully!');
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-800/50">
        {selectedImage ? (
          <div className="relative group">
            <img 
              src={convertFileSrc(selectedImage)} 
              alt="Preview" 
              className="max-h-64 rounded-lg shadow-lg object-contain" 
            />
            <p className="mt-2 text-sm text-center text-gray-500 break-all">{selectedImage}</p>
          </div>
        ) : (
          <div className="text-center">
            <Image className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500">No image selected</p>
          </div>
        )}
        
        <button
          onClick={handleSelectImage}
          className="mt-4 px-4 py-2 bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition"
        >
          Select Image
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
        <div className="w-full sm:w-48">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Style</label>
          <select 
            value={style} 
            onChange={(e) => setStyle(e.target.value)}
            className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white p-2"
          >
            <option value="Fill">Fill</option>
            <option value="Fit">Fit</option>
            <option value="Stretch">Stretch</option>
            <option value="Tile">Tile</option>
            <option value="Center">Center</option>
            <option value="Span">Span</option>
          </select>
        </div>

        <button
          onClick={handleSetWallpaper}
          disabled={!selectedImage}
          className={`px-6 py-2 rounded-lg font-medium text-white transition h-10 mt-6
            ${selectedImage 
              ? 'bg-green-500 hover:bg-green-600' 
              : 'bg-gray-400 cursor-not-allowed'
            }`}
        >
          Set Wallpaper
        </button>
      </div>

      {status && (
        <div className={`p-4 rounded-lg text-center ${status.startsWith('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
          {status}
        </div>
      )}
    </div>
  );
};

export default WallpaperTab;
