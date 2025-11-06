// src/App.jsx
import React, { useState, useRef } from 'react';
import { 
  Database, 
  Image, 
  Trash2, 
  Search, 
  LayoutGrid,
  FolderOpen,
  // Removed: Play
} from 'lucide-react';

import Modal from './components/Modal';
import ConvertTab from './tabs/ConvertTab';
import MergeTab from './tabs/MergeTab';
import DeleteTab from './tabs/DeleteTab';
import SearchTab from './tabs/SearchTab';
import DatabaseTab from './tabs/DatabaseTab';
import ScanFSETab from './tabs/ScanFSETab';

const App = () => {
  // --- Global State ---
  const [activeTab, setActiveTab] = useState('convert');
  const [modalState, setModalState] = useState({ isVisible: false, content: '', type: 'info' });
  const scanFSETabRef = useRef();
  const [modal, setModal] = useState({ show: false, message: '', type: 'info', duration: 0, content: null });

  // --- Refs to access data from children (using useImperativeHandle) ---
  const ConvertRef = useRef(null);
  const MergeRef = useRef(null);
  const DeleteRef = useRef(null);
  const SearchRef = useRef(null);
  const DatabaseRef = useRef(null);
  const ScanFSERef = useRef(null);

  const tabRefs = {
    convert: ConvertRef,
    merge: MergeRef,
    delete: DeleteRef,
    search: SearchRef,
    database: DatabaseRef,
    scan: ScanFSERef,
  };
  
  // Function to show the modal from any child component
  const showModal = (message, type = 'info', duration = 0) => {
    setModal({ show: true, message, type, duration, content: (typeof message !== 'string' ? message : null) });
    if (duration > 0) {
      setTimeout(() => setModal(prev => ({ ...prev, show: false })), duration);
    }
  };

  const handleAddImagesToDb = (imagePaths) => {
    // This is where you would integrate with your database logic
    console.log("Images to add to DB:", imagePaths);
    showModal(`Attempting to add ${imagePaths.length} images to the database...`, 'info');
  };
  
  // Removed: handleRunAction function
  
  const TABS = [
    { id: 'convert', label: 'Convert', icon: Image, component: ConvertTab },
    { id: 'merge', label: 'Merge', icon: LayoutGrid, component: MergeTab },
    { id: 'delete', label: 'Delete', icon: Trash2, component: DeleteTab },
    { id: 'search', label: 'Search', icon: Search, component: SearchTab },
    { id: 'database', label: 'Database', icon: Database, component: DatabaseTab },
    { id: 'scan', label: 'Scan', icon: FolderOpen, component: ScanFSETab },
  ];
  
  const CurrentTabComponent = TABS.find(tab => tab.id === activeTab)?.component || ConvertTab;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-4 sm:p-8 font-sans transition-colors duration-300">
      
      <div className="max-w-4xl mx-auto bg-white dark:bg-gray-800 rounded-3xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-700">
        
        {/* Header: Removed the button and changed 'justify-between' to 'justify-start' */}
        <header className="flex items-center justify-start p-4 bg-violet-700 text-white shadow-lg">
          <h1 className="text-2xl font-extrabold tracking-tight">
            Image Database and Toolkit
          </h1>
        </header>

        {/* Tab Navigation */}
        <nav className="flex flex-wrap p-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center px-4 py-2 m-1 text-sm font-semibold rounded-full transition-all duration-300 
                ${activeTab === tab.id
                  ? 'bg-violet-500 text-white shadow-md'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`
              }
            >
              <tab.icon size={16} className="mr-2" />
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        <main className="min-h-[500px] overflow-y-auto">
          <CurrentTabComponent 
            ref={tabRefs[activeTab]} 
            showModal={showModal}
            {...(activeTab === 'scan' && { onAddImagesToDb: handleAddImagesToDb })}
          />
        </main>
      </div>

      {/* Global Modal - Note: modalState needs to be handled outside of this snippet for full functionality */}
      {/* Assuming Modal component is functional as is */}
      <div 
        className={`fixed inset-0 z-50 ${modal.show ? 'block' : 'hidden'} flex items-center justify-center`}
        onClick={() => setModal(prev => ({ ...prev, show: false }))}
      >
        <div 
          className="p-6 bg-white rounded-xl shadow-2xl max-w-sm w-full dark:bg-gray-800"
          onClick={e => e.stopPropagation()} // Prevent closing when clicking inside
        >
          {modal.content || <p className={`text-center ${modal.type === 'error' ? 'text-red-500' : 'text-gray-900 dark:text-gray-100'}`}>{modal.message}</p>}
          <button 
            onClick={() => setModal(prev => ({ ...prev, show: false }))}
            className="mt-4 w-full py-2 bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;
