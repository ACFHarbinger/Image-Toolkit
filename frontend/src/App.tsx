import React, {
  useState,
  useRef,
  ReactNode,
  ComponentType,
  RefObject,
  useEffect,
} from "react";
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
  MonitorPlay,
  Monitor,
  Cloud,
  Globe,
  ScanSearch,
  Network,
  ScanEye,
  BarChart3,
  Settings,
  LogOut,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { useAppStore } from "./store/appStore";
import { LoginDialog } from "./components/dialogs/LoginDialog";
import { SettingsDialog } from "./components/dialogs/SettingsDialog";
import { ImagePreview } from "./components/sublime/ImagePreview";
import { TaskProgress } from "./components/sublime/TaskProgress";

// --- Core Tabs ---
import ConvertTab from "./tabs/core/ConvertTab";
import MergeTab from "./tabs/core/MergeTab";
import DeleteTab from "./tabs/core/DeleteTab";
import WallpaperTab from "./tabs/core/WallpaperTab";
import { ImageExtractorTab } from "./tabs/core/ImageExtractorTab";

// --- Database Tabs ---
import SearchTab from "./tabs/database/SearchTab";
import DatabaseTab from "./tabs/database/DatabaseTab";
import ScanMetadataTab from "./tabs/database/ScanMetadataTab";

// --- Web Integration Tabs ---
import DriveSyncTab from "./tabs/web/DriveSyncTab";
import ImageCrawlerTab from "./tabs/web/ImageCrawlerTab";
import ReverseSearchTab from "./tabs/web/ReverseSearchTab";
import WebRequestsTab from "./tabs/web/WebRequestsTab";

// --- Model Tabs ---
import { UnifiedTrainTab } from "./tabs/models/UnifiedTrainTab";
import { UnifiedGenerateTab } from "./tabs/models/UnifiedGenerateTab";
import { MetaCLIPInferenceTab } from "./tabs/models/MetaCLIPInferenceTab";
import { R3GANEvaluateTab } from "./tabs/models/R3GANEvaluateTab";

// --- Analytics Tabs ---
import { BenchmarkDashboard } from "./tabs/apollo/BenchmarkDashboard";

// --- Image Editor Tabs ---
import { HieEditorTab } from "./tabs/editor/HieEditorTab";
import { frontendPages } from "./shell/catalog";

// --- Interfaces ---

type TabId =
  | "convert"
  | "merge"
  | "delete"
  | "extractor"
  | "wallpaper"
  | "search"
  | "database"
  | "scan"
  | "train"
  | "generate"
  | "inference"
  | "evaluate"
  | "drive"
  | "crawler"
  | "revsearch"
  | "webreq"
  | "benchmarks"
  | "hie_editor";

interface BaseTabProps {
  showModal: (
    message: string | ReactNode,
    type?: "info" | "error" | "success",
    duration?: number,
  ) => void;
}

interface TabConfig {
  id: TabId;
  label: string;
  icon: LucideIcon;
  component: ComponentType<any>;
}

interface TabGroup {
  title: string;
  tabs: TabConfig[];
}

interface ModalData {
  show: boolean;
  message: string;
  type: "info" | "error" | "success";
  duration: number;
  content: React.ReactNode | null;
}

const App: React.FC = () => {
  // --- Global State from Store ---
  const {
    isLoggedIn,
    showSettings,
    showImagePreview,
    previewImagePath,
    logout,
    openSettings,
    closeSettings,
    closeImagePreview,
    setDatabaseConnected,
  } = useAppStore();

  // --- Local State ---
  const [activeTab, setActiveTab] = useState<TabId>("convert");
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [isPrimaryDropdownOpen, setIsPrimaryDropdownOpen] = useState(false);
  const [dbStatus, setDbStatus] = useState<"checking" | "connected" | "disconnected">("checking");

  const [modal, setModal] = useState<ModalData>({
    show: false,
    message: "",
    type: "info",
    duration: 0,
    content: null,
  });

  // --- Check Database Connection ---
  useEffect(() => {
    const checkDatabase = async () => {
      try {
        await invoke("test_database_connection");
        setDbStatus("connected");
        setDatabaseConnected(true);
      } catch (err) {
        console.error("Database connection failed:", err);
        setDbStatus("disconnected");
        setDatabaseConnected(false);
      }
    };

    if (isLoggedIn) {
      checkDatabase();
    }
  }, [isLoggedIn, setDatabaseConnected]);

  // --- Refs ---
  const ConvertRef = useRef<any>(null);
  const MergeRef = useRef<any>(null);
  const DeleteRef = useRef<any>(null);
  const WallpaperRef = useRef<any>(null);
  const ExtractorRef = useRef<any>(null);
  const SearchRef = useRef<any>(null);
  const DatabaseRef = useRef<any>(null);
  const ScanMetadataRef = useRef<any>(null);
  const TrainRef = useRef<any>(null);
  const GenerateRef = useRef<any>(null);
  const MetaClipRef = useRef<any>(null);
  const EvaluateRef = useRef<any>(null);
  const DriveRef = useRef<any>(null);
  const CrawlerRef = useRef<any>(null);
  const RevSearchRef = useRef<any>(null);
  const WebReqRef = useRef<any>(null);
  const BenchmarksRef = useRef<any>(null);
  const HieEditorRef = useRef<any>(null);

  const primaryDropdownRef = useRef<HTMLDivElement>(null);

  const tabRefs: Record<TabId, RefObject<any>> = {
    convert: ConvertRef,
    merge: MergeRef,
    delete: DeleteRef,
    wallpaper: WallpaperRef,
    extractor: ExtractorRef,
    search: SearchRef,
    database: DatabaseRef,
    scan: ScanMetadataRef,
    train: TrainRef,
    generate: GenerateRef,
    inference: MetaClipRef,
    evaluate: EvaluateRef,
    drive: DriveRef,
    crawler: CrawlerRef,
    revsearch: RevSearchRef,
    webreq: WebReqRef,
    benchmarks: BenchmarksRef,
    hie_editor: HieEditorRef,
  };

  const showModal = (
    message: string | ReactNode,
    type: "info" | "error" | "success" = "info",
    duration: number = 0,
  ) => {
    setModal({
      show: true,
      message: typeof message === "string" ? message : "",
      type,
      duration,
      content: typeof message !== "string" ? message : null,
    });

    if (duration > 0) {
      setTimeout(
        () => setModal((prev) => ({ ...prev, show: false })),
        duration,
      );
    }
  };

  const handleAddImagesToDb = (imagePaths: string[]) => {
    console.log("Images to add to DB:", imagePaths);
    showModal(
      `Attempting to add ${imagePaths.length} images to the database...`,
      "info",
    );
  };

  const TAB_COMPONENTS: Record<TabId, ComponentType<any>> = {
    convert: ConvertTab,
    merge: MergeTab,
    delete: DeleteTab,
    extractor: ImageExtractorTab,
    wallpaper: WallpaperTab,
    search: SearchTab,
    database: DatabaseTab,
    scan: ScanMetadataTab,
    train: UnifiedTrainTab,
    generate: UnifiedGenerateTab,
    inference: MetaCLIPInferenceTab,
    evaluate: R3GANEvaluateTab,
    drive: DriveSyncTab,
    crawler: ImageCrawlerTab,
    revsearch: ReverseSearchTab,
    webreq: WebRequestsTab,
    benchmarks: BenchmarkDashboard,
    hie_editor: HieEditorTab,
  };
  const TAB_ICONS: Record<TabId, LucideIcon> = {
    convert: ImageIcon,
    merge: LayoutGrid,
    delete: Trash2,
    extractor: MonitorPlay,
    wallpaper: Monitor,
    search: Search,
    database: Database,
    scan: FolderOpen,
    train: BrainCircuit,
    generate: Wand2,
    inference: ScanEye,
    evaluate: BarChart3,
    drive: Cloud,
    crawler: Globe,
    revsearch: ScanSearch,
    webreq: Network,
    benchmarks: BarChart3,
    hie_editor: Layers,
  };

  // Labels, categories and order come from the shared catalog. This file
  // only attaches the React component and icon for ids that already exist.
  const TAB_GROUPS: TabGroup[] = [];
  for (const entry of frontendPages()) {
    const id = entry.legacy_frontend_id as TabId;
    const component = TAB_COMPONENTS[id];
    if (!component) {
      continue;
    }
    let group = TAB_GROUPS.find((item) => item.title === entry.category);
    if (!group) {
      group = { title: entry.category, tabs: [] };
      TAB_GROUPS.push(group);
    }
    group.tabs.push({
      id,
      label: entry.title,
      icon: TAB_ICONS[id],
      component,
    });
  }

  const ALL_TABS = TAB_GROUPS.flatMap((group) => group.tabs);
  const CurrentTabConfig = ALL_TABS.find((tab) => tab.id === activeTab);
  const CurrentTabComponent = CurrentTabConfig?.component || ConvertTab;
  const CurrentGroupName =
    TAB_GROUPS.find((group) => group.tabs.some((t) => t.id === activeTab))
      ?.title || "Navigate";

  const commonProps: BaseTabProps = {
    showModal: showModal,
  };

  const conditionalProps =
    activeTab === "scan" ? { onAddImagesToDb: handleAddImagesToDb } : {};

  const handleTabClick = (tabId: TabId) => {
    setActiveTab(tabId);
    setIsPrimaryDropdownOpen(false);
    setOpenDropdown(null);
  };

  const handleDocumentClick = (event: MouseEvent) => {
    if (
      primaryDropdownRef.current &&
      !primaryDropdownRef.current.contains(event.target as Node)
    ) {
      setIsPrimaryDropdownOpen(false);
      setOpenDropdown(null);
    }
  };

  React.useEffect(() => {
    document.addEventListener("mousedown", handleDocumentClick);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
    };
  }, []);

  // Show login dialog if not logged in
  if (!isLoggedIn) {
    return <LoginDialog />;
  }

  return (
    <div className="min-h-screen bg-it-window-bg text-it-text p-4 sm:p-8 font-sans transition-colors duration-300">
      <div className="max-w-6xl mx-auto bg-it-surface rounded-3xl shadow-2xl overflow-hidden border border-it-border">
        {/* Header */}
        <header className="flex items-center justify-between p-4 bg-it-accent text-white shadow-lg">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-extrabold tracking-tight">
              Image Database and Toolkit
            </h1>

            {/* Database Status Indicator */}
            <div className="flex items-center gap-2 text-sm">
              {dbStatus === "checking" && (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span className="text-white/80">Checking DB...</span>
                </>
              )}
              {dbStatus === "connected" && (
                <>
                  <CheckCircle2 size={16} className="text-green-300" />
                  <span className="text-green-300">DB Connected</span>
                </>
              )}
              {dbStatus === "disconnected" && (
                <>
                  <AlertCircle size={16} className="text-red-300" />
                  <span className="text-red-300">DB Offline</span>
                </>
              )}
            </div>
          </div>

          {/* User Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={openSettings}
              className="p-2 rounded-lg hover:bg-it-accent-hover transition-colors"
              title="Settings"
            >
              <Settings size={20} />
            </button>
            <button
              onClick={logout}
              className="p-2 rounded-lg hover:bg-it-accent-hover transition-colors"
              title="Logout"
            >
              <LogOut size={20} />
            </button>
          </div>
        </header>

        {/* Tab Navigation */}
        <nav className="flex p-2 border-b border-it-border bg-it-window-bg">
          <div ref={primaryDropdownRef} className="relative">
            <button
              onClick={() => setIsPrimaryDropdownOpen((prev) => !prev)}
              className={`flex items-center px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-300 
                bg-it-accent text-white shadow-md hover:bg-it-accent-hover
              `}
            >
              {(() => {
                const Icon = CurrentTabConfig?.icon;
                return Icon ? <Icon size={16} className="mr-2" /> : null;
              })()}
              {CurrentTabConfig?.label || CurrentGroupName}
              <ChevronDown
                size={16}
                className={`ml-2 transition-transform duration-200 ${isPrimaryDropdownOpen ? "rotate-180" : ""}`}
              />
            </button>

            {isPrimaryDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-72 bg-it-surface rounded-xl shadow-xl border border-it-border z-50 overflow-hidden">
                {TAB_GROUPS.map((group) => (
                  <div key={group.title}>
                    <button
                      onClick={() =>
                        setOpenDropdown((prev) =>
                          prev === group.title ? null : group.title,
                        )
                      }
                      className={`w-full text-left px-4 py-3 text-sm flex items-center justify-between font-bold border-b border-it-border
                        ${openDropdown === group.title
                          ? "bg-it-surface text-it-accent"
                          : "text-it-text hover:bg-it-surface"
                        }`}
                    >
                      {group.title}
                      <ChevronRight
                        size={16}
                        className={`transition-transform ${openDropdown === group.title ? "rotate-90" : ""}`}
                      />
                    </button>

                    {openDropdown === group.title && (
                      <div className="bg-it-window-bg">
                        {group.tabs.map((tab) => {
                          const TabIcon = tab.icon;
                          return (
                            <button
                              key={tab.id}
                              onClick={() => handleTabClick(tab.id)}
                              className={`w-full text-left pl-10 pr-4 py-2 text-xs flex items-center border-l-4 transition-colors
                                 ${activeTab === tab.id
                                  ? "border-it-accent bg-it-surface text-it-accent font-medium"
                                  : "border-transparent text-it-muted-text hover:bg-it-surface"
                                }`}
                            >
                              <TabIcon size={14} className="mr-2" />
                              {tab.label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </nav>

        {/* Tab Content */}
        <main className={activeTab === "benchmarks" ? "h-[78vh]" : "min-h-[600px] overflow-y-auto"}>
          {activeTab === "benchmarks" ? (
            <BenchmarkDashboard />
          ) : (
            <CurrentTabComponent
              ref={tabRefs[activeTab]}
              {...commonProps}
              {...conditionalProps}
            />
          )}
        </main>
      </div>

      {/* Global Modal */}
      <div
        className={`fixed inset-0 z-50 ${modal.show ? "block" : "hidden"} flex items-center justify-center`}
        onClick={() => setModal((prev) => ({ ...prev, show: false }))}
      >
        <div
          className="p-6 bg-it-surface rounded-xl shadow-2xl max-w-sm w-full border border-it-border"
          onClick={(e) => e.stopPropagation()}
        >
          {modal.content || (
            <p
              className={`text-center ${modal.type === "error" ? "text-red-500" : "text-it-text"}`}
            >
              {modal.message}
            </p>
          )}
          <button
            onClick={() => setModal((prev) => ({ ...prev, show: false }))}
            className="mt-4 w-full py-2 bg-it-accent text-white rounded-lg hover:bg-it-accent-hover transition"
          >
            Close
          </button>
        </div>
      </div>

      {/* Settings Dialog */}
      {showSettings && <SettingsDialog onClose={closeSettings} />}

      {/* Image Preview */}
      {showImagePreview && previewImagePath && (
        <ImagePreview path={previewImagePath || ""} onClose={closeImagePreview} />
      )}

      {/* Background Task Progress */}
      <TaskProgress />
    </div>
  );
};

export default App;
