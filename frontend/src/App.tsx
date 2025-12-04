import React, { useState, useRef, ReactNode, ComponentType, RefObject } from 'react';
import { 
  Database, 
  Image as ImageIcon, 
  Trash2, 
  Search, 
  LayoutGrid,
  FolderOpen,
  LucideIcon,
  BrainCircuit, 
  Wand2,
  ChevronDown,
  ChevronRight,
  MonitorPlay // Icon for Video/Extractor
} from 'lucide-react';

// --- Core Tabs ---
import ConvertTab from './tabs/core/ConvertTab.tsx';
import MergeTab from './tabs/core/MergeTab.tsx';
import DeleteTab from './tabs/core/DeleteTab.tsx';
import { ImageExtractorTab } from './tabs/core/ImageExtractorTab.tsx';

// --- Database Tabs ---
import SearchTab from './tabs/database/SearchTab.tsx';
import DatabaseTab from './tabs/database/DatabaseTab.tsx';
import ScanFSETab from './tabs/database/ScanFSETab.tsx';

// --- Import Unified Tabs ---
import { UnifiedTrainTab } from './tabs/models/UnifiedTrainTab.tsx';
import { UnifiedGenerateTab } from './tabs/models/UnifiedGenerateTab.tsx';

// --- Interfaces ---

// UPDATED: Added 'extractor' TabId
type TabId = 'convert' | 'merge' | 'delete' | 'extractor' | 'search' | 'database' | 'scan' | 'train' | 'generate';

// 1. Define the shared props interface that ALL tabs receive.
interface BaseTabProps {
  showModal: (message: string | ReactNode, type?: 'info' | 'error' | 'success', duration?: number) => void;
  // All other common props would go here (e.g., isAuthenticated)
}

interface ScanTabProps extends BaseTabProps {
  onAddImagesToDb: (imagePaths: string[]) => void;
}

// 2. Update TabConfig to use a generic ComponentType
interface TabConfig {
  id: TabId;
  label: string;
  icon: LucideIcon;
  // Use generic ComponentType which accepts the base props
  component: ComponentType<any>; 
}

interface TabGroup {
  title: string;
  tabs: TabConfig[];
}

interface ModalData {
  show: boolean;
  message: string;
  type: 'info' | 'error' | 'success';
  duration: number;
  content: React.ReactNode | null;
}

const App: React.FC = () => {
  // --- Global State ---
  const [activeTab, setActiveTab] = useState<TabId>('convert');
  // Changed openDropdown to track the open group *within* the single primary dropdown
  const [openDropdown, setOpenDropdown] = useState<string | null>(null); 
  const [isPrimaryDropdownOpen, setIsPrimaryDropdownOpen] = useState(false); // New state for the main button
  
  const [modal, setModal] = useState<ModalData>({ 
    show: false, 
    message: '', 
    type: 'info', 
    duration: 0, 
    content: null 
  });

  // --- Refs ---
  const ConvertRef = useRef<any>(null);
  const MergeRef = useRef<any>(null);
  const DeleteRef = useRef<any>(null);
  const ExtractorRef = useRef<any>(null); // NEW REF
  const SearchRef = useRef<any>(null);
  const DatabaseRef = useRef<any>(null);
  const ScanFSERef = useRef<any>(null);
  const TrainRef = useRef<any>(null);
  const GenerateRef = useRef<any>(null);
  const primaryDropdownRef = useRef<HTMLDivElement>(null); // Ref for click outside logic

  // UPDATED: Added extractor ref
  const tabRefs: Record<TabId, RefObject<any>> = {
    convert: ConvertRef,
    merge: MergeRef,
    delete: DeleteRef,
    extractor: ExtractorRef, // Mapped new ref
    search: SearchRef,
    database: DatabaseRef,
    scan: ScanFSERef,
    train: TrainRef,
    generate: GenerateRef,
  };
  
  const showModal = (message: string | ReactNode, type: 'info' | 'error' | 'success' = 'info', duration: number = 0) => {
    setModal({ 
      show: true, 
      message: typeof message === 'string' ? message : '', 
      type, 
      duration, 
      content: typeof message !== 'string' ? message : null 
    });

    if (duration > 0) {
      setTimeout(() => setModal(prev => ({ ...prev, show: false })), duration);
    }
  };

  const handleAddImagesToDb = (imagePaths: string[]) => {
    console.log("Images to add to DB:", imagePaths);
    showModal(`Attempting to add ${imagePaths.length} images to the database...`, 'info');
  };
  
  // Define Tab Groups
  const TAB_GROUPS: TabGroup[] = [
    {
      title: 'System Tools',
      tabs: [
        { id: 'convert', label: 'Convert', icon: ImageIcon, component: ConvertTab },
        { id: 'merge', label: 'Merge', icon: LayoutGrid, component: MergeTab },
        { id: 'delete', label: 'Delete', icon: Trash2, component: DeleteTab },
        { id: 'extractor', label: 'Extractor', icon: MonitorPlay, component: ImageExtractorTab }, // ADDED EXTRACTOR
      ]
    },
    {
      title: 'Database Management',
      tabs: [
        { id: 'search', label: 'Search', icon: Search, component: SearchTab },
        { id: 'database', label: 'Database', icon: Database, component: DatabaseTab },
        { id: 'scan', label: 'Scan', icon: FolderOpen, component: ScanFSETab },
      ]
    },
    {
      title: 'Deep Learning',
      tabs: [
        { id: 'train', label: 'Train Model', icon: BrainCircuit, component: UnifiedTrainTab },
        { id: 'generate', label: 'Generate', icon: Wand2, component: UnifiedGenerateTab },
      ]
    }
  ];

  // Flatten tabs for lookup
  const ALL_TABS = TAB_GROUPS.flatMap(group => group.tabs);
  
  const CurrentTabConfig = ALL_TABS.find(tab => tab.id === activeTab);
  const CurrentTabComponent = CurrentTabConfig?.component || ConvertTab;
  const CurrentGroupName = TAB_GROUPS.find(group => group.tabs.some(t => t.id === activeTab))?.title || 'Navigate';


  // 3. Define props shared by all components
  const commonProps: BaseTabProps = {
    showModal: showModal,
  };

  // 4. Define conditional props
  // Note: 'scan' is the only tab needing onAddImagesToDb.
  const conditionalProps = activeTab === 'scan' ? { onAddImagesToDb: handleAddImagesToDb } : {};
  
  const handleTabClick = (tabId: TabId) => {
    setActiveTab(tabId);
    setIsPrimaryDropdownOpen(false);
    setOpenDropdown(null); // Close nested dropdown
  };

  const handleDocumentClick = (event: MouseEvent) => {
    if (primaryDropdownRef.current && !primaryDropdownRef.current.contains(event.target as Node)) {
      setIsPrimaryDropdownOpen(false);
      setOpenDropdown(null);
    }
  };

  React.useEffect(() => {
    document.addEventListener('mousedown', handleDocumentClick);
    return () => {
      document.removeEventListener('mousedown', handleDocumentClick);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-4 sm:p-8 font-sans transition-colors duration-300">
      
      <div className="max-w-6xl mx-auto bg-white dark:bg-gray-800 rounded-3xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-700">
        
        {/* Header */}
        <header className="flex items-center justify-start p-4 bg-violet-700 text-white shadow-lg">
          <h1 className="text-2xl font-extrabold tracking-tight">
            Image Database and Toolkit
          </h1>
        </header>

        {/* Tab Navigation - Single Dropdown Menu Style */}
        <nav className="flex p-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
          <div ref={primaryDropdownRef} className="relative">
            {/* Primary Button showing Current Tab or Group */}
            <button
              onClick={() => setIsPrimaryDropdownOpen(prev => !prev)}
              className={`flex items-center px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-300 
                bg-violet-500 text-white shadow-md hover:bg-violet-600
              `}
            >
              {/* FIX: Conditional rendering of icon */}
              {CurrentTabConfig?.icon && <CurrentTabConfig.icon size={16} className="mr-2" />}
              {CurrentTabConfig?.label || CurrentGroupName}
              <ChevronDown size={16} className={`ml-2 transition-transform duration-200 ${isPrimaryDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Main Dropdown Container */}
            {isPrimaryDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
                {TAB_GROUPS.map(group => (
                  <div key={group.title}>
                    {/* Group Header (acts as toggle for nested menu) */}
                    <button
                      onClick={() => setOpenDropdown(prev => prev === group.title ? null : group.title)}
                      className={`w-full text-left px-4 py-3 text-sm flex items-center justify-between font-bold border-b dark:border-gray-700
                        ${openDropdown === group.title 
                          ? 'bg-gray-100 dark:bg-gray-700 text-violet-600 dark:text-violet-300' 
                          : 'text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-700'
                        }`
                      }
                    >
                      {group.title}
                      <ChevronRight size={16} className={`transition-transform ${openDropdown === group.title ? 'rotate-90' : ''}`} />
                    </button>

                    {/* Nested Tabs */}
                    {openDropdown === group.title && (
                      <div className="bg-gray-50 dark:bg-gray-900/50">
                        {group.tabs.map(tab => (
                          <button
                            key={tab.id}
                            onClick={() => handleTabClick(tab.id)}
                            className={`w-full text-left pl-10 pr-4 py-2 text-xs flex items-center border-l-4 transition-colors
                              ${activeTab === tab.id 
                                ? 'border-violet-500 bg-violet-100 dark:bg-violet-900/20 text-violet-700 font-medium' 
                                : 'border-transparent text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                              }`
                            }
                          >
                            <tab.icon size={14} className="mr-2" />
                            {tab.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </nav>

        {/* Tab Content */}
        <main className="min-h-[600px] overflow-y-auto">
          {/* 5. Pass Props using a spread operator and combining common/conditional props */}
          <CurrentTabComponent 
            ref={tabRefs[activeTab]} 
            {...commonProps}
            {...conditionalProps}
          />
        </main>
      </div>

      {/* Global Modal */}
      <div 
        className={`fixed inset-0 z-50 ${modal.show ? 'block' : 'hidden'} flex items-center justify-center`}
        onClick={() => setModal(prev => ({ ...prev, show: false }))}
      >
        <div 
          className="p-6 bg-white rounded-xl shadow-2xl max-w-sm w-full dark:bg-gray-800"
          onClick={e => e.stopPropagation()} 
        >
          {modal.content || (
            <p className={`text-center ${modal.type === 'error' ? 'text-red-500' : 'text-gray-900 dark:text-gray-100'}`}>
              {modal.message}
            </p>
          )}
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