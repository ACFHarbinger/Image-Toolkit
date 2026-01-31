/**
 * Global Application State Store (Using React Context)
 * 
 * This store manages:
 * - Authentication state
 * - Background task progress
 * - User preferences (theme, settings)
 * - Application configuration
 */

import { createContext, useContext } from 'react';

// ===== Types & Interfaces =====

export interface BackgroundTask {
  id: string;
  type: 'conversion' | 'merge' | 'video_extraction' | 'database_scan' | 'crawl' | 'sync';
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number; // 0-100
  message: string;
  startTime: number;
  endTime?: number;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  autoSave: boolean;
  defaultOutputPath?: string;
  tabConfigurations: Record<string, any>;
}

export interface VaultCredentials {
  accountName: string;
  isAuthenticated: boolean;
}

export interface AppState {
  // Authentication
  vault: VaultCredentials | null;
  isLoggedIn: boolean;
  
  // Background Tasks
  tasks: Map<string, BackgroundTask>;
  
  // User Preferences
  preferences: UserPreferences;
  
  // UI State
  showSettings: boolean;
  showLogViewer: boolean;
  showImagePreview: boolean;
  previewImagePath: string | null;
  
  // Database state
  databaseConnected: boolean;
}

export interface AppActions {
  // Authentication
  login: (accountName: string) => void;
  logout: () => void;
  
  // Background Tasks
  addTask: (task: BackgroundTask) => void;
  updateTask: (id: string, updates: Partial<BackgroundTask>) => void;
  removeTask: (id: string) => void;
  clearCompletedTasks: () => void;
  
  // User Preferences
  updatePreferences: (preferences: Partial<UserPreferences>) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  
  // UI Actions
  openSettings: () => void;
  closeSettings: () => void;
  openLogViewer: () => void;
  closeLogViewer: () => void;
  openImagePreview: (path: string) => void;
  closeImagePreview: () => void;
  
  // Database
  setDatabaseConnected: (connected: boolean) => void;
}

export type AppStore = AppState & AppActions;

// ===== Initial State =====

export const initialState: AppState = {
  vault: null,
  isLoggedIn: false,
  tasks: new Map(),
  preferences: {
    theme: 'dark',
    autoSave: true,
    tabConfigurations: {},
  },
  showSettings: false,
  showLogViewer: false,
  showImagePreview: false,
  previewImagePath: null,
  databaseConnected: false,
};

// ===== Context =====

export const AppStoreContext = createContext<AppStore | null>(null);

export const useAppStore = () => {
  const context = useContext(AppStoreContext);
  if (!context) {
    throw new Error('useAppStore must be used within AppStoreProvider');
  }
  return context;
};
