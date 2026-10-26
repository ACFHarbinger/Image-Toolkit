/**
 * AppStoreProvider - Global State Management Provider
 * 
 * Provides global state management using React Context API.
 * This replaces the need for Zustand to keep dependencies minimal.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';
import {
  AppStoreContext,
  initialState,
  AppState,
  AppStore,
  BackgroundTask,
  UserPreferences,
} from './appStore';

interface AppStoreProviderProps {
  children: React.ReactNode;
}

export const AppStoreProvider: React.FC<AppStoreProviderProps> = ({ children }) => {
  const [state, setState] = useState<AppState>(initialState);

  // ===== Authentication Actions =====

  const login = useCallback((accountName: string) => {
    setState((prev) => ({
      ...prev,
      vault: { accountName, isAuthenticated: true },
      isLoggedIn: true,
    }));
    
    // The account name is a hint for the next status check. It is not the vault session.
    localStorage.removeItem('app_authenticated');
    localStorage.setItem('app_account_name', accountName);
  }, []);

  const logout = useCallback(() => {
    setState((prev) => ({
      ...prev,
      vault: null,
      isLoggedIn: false,
    }));

    localStorage.removeItem('app_authenticated');
    localStorage.removeItem('app_account_name');
  }, []);

  // ===== Background Task Actions =====

  const addTask = useCallback((task: BackgroundTask) => {
    setState((prev) => {
      const newTasks = new Map(prev.tasks);
      newTasks.set(task.id, task);
      return { ...prev, tasks: newTasks };
    });
  }, []);

  const updateTask = useCallback((id: string, updates: Partial<BackgroundTask>) => {
    setState((prev) => {
      const newTasks = new Map(prev.tasks);
      const existingTask = newTasks.get(id);
      if (existingTask) {
        newTasks.set(id, { ...existingTask, ...updates });
      }
      return { ...prev, tasks: newTasks };
    });
  }, []);

  const removeTask = useCallback((id: string) => {
    setState((prev) => {
      const newTasks = new Map(prev.tasks);
      newTasks.delete(id);
      return { ...prev, tasks: newTasks };
    });
  }, []);

  const clearCompletedTasks = useCallback(() => {
    setState((prev) => {
      const newTasks = new Map(prev.tasks);
      newTasks.forEach((task, id) => {
        if (task.status === 'completed') {
          newTasks.delete(id);
        }
      });
      return { ...prev, tasks: newTasks };
    });
  }, []);

  // ===== User Preferences Actions =====

  const updatePreferences = useCallback((preferences: Partial<UserPreferences>) => {
    setState((prev) => ({
      ...prev,
      preferences: { ...prev.preferences, ...preferences },
    }));
    
    // Persist preferences to localStorage
    const newPrefs = { ...state.preferences, ...preferences };
    localStorage.setItem('app_preferences', JSON.stringify(newPrefs));
  }, [state.preferences]);

  const setTheme = useCallback((theme: 'light' | 'dark' | 'system') => {
    updatePreferences({ theme });

    // Tailwind's dark: variant and the shell tokens both read data-theme, not the class.
    const root = document.documentElement;
    const prefersDark = theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const resolved = theme === 'system' ? (prefersDark ? 'dark' : 'light') : theme;
    root.dataset.theme = resolved;
    root.classList.toggle('dark', resolved === 'dark');
  }, [updatePreferences]);

  // ===== UI Actions =====

  const openSettings = useCallback(() => {
    setState((prev) => ({ ...prev, showSettings: true }));
  }, []);

  const closeSettings = useCallback(() => {
    setState((prev) => ({ ...prev, showSettings: false }));
  }, []);

  const openLogViewer = useCallback(() => {
    setState((prev) => ({ ...prev, showLogViewer: true }));
  }, []);

  const closeLogViewer = useCallback(() => {
    setState((prev) => ({ ...prev, showLogViewer: false }));
  }, []);

  const openImagePreview = useCallback((path: string) => {
    setState((prev) => ({
      ...prev,
      showImagePreview: true,
      previewImagePath: path,
    }));
  }, []);

  const closeImagePreview = useCallback(() => {
    setState((prev) => ({
      ...prev,
      showImagePreview: false,
      previewImagePath: null,
    }));
  }, []);

  // ===== Database Actions =====

  const setDatabaseConnected = useCallback((connected: boolean) => {
    setState((prev) => ({ ...prev, databaseConnected: connected }));
  }, []);

  // ===== Tauri Event Listeners =====

  useEffect(() => {
    // Listen for task progress events from Tauri backend
    const unlistenProgress = listen<any>('task-progress', (event) => {
      const { taskId, progress, message, status } = event.payload;
      updateTask(taskId, { progress, message, status });
    });

    // Listen for task completion events
    const unlistenComplete = listen<any>('task-complete', (event) => {
      const { taskId, success, message } = event.payload;
      updateTask(taskId, {
        status: success ? 'completed' : 'failed',
        progress: 100,
        message,
        endTime: Date.now(),
      });
    });

    // Cleanup listeners on unmount
    return () => {
      if (unlistenProgress && typeof unlistenProgress.then === "function") {
        unlistenProgress.then((fn) => fn && typeof fn === "function" && fn());
      }
      if (unlistenComplete && typeof unlistenComplete.then === "function") {
        unlistenComplete.then((fn) => fn && typeof fn === "function" && fn());
      }
    };
  }, [updateTask]);

  // ===== Initialize from localStorage =====

  useEffect(() => {
    // Remember the account name only. The shell confirms auth.status before trusting it.
    const accountName = localStorage.getItem('app_account_name');
    if (accountName) {
      login(accountName);
    }

    // Load preferences
    const savedPrefs = localStorage.getItem('app_preferences');
    if (savedPrefs) {
      try {
        const prefs = JSON.parse(savedPrefs);
        setState((prev) => ({ ...prev, preferences: prefs }));
        
        // Apply saved theme
        if (prefs.theme) {
          setTheme(prefs.theme);
        }
      } catch (e) {
        console.error('Failed to load preferences:', e);
      }
    } else {
      // Apply default theme
      setTheme('dark');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ===== Construct Store Value =====

  const store: AppStore = {
    ...state,
    login,
    logout,
    addTask,
    updateTask,
    removeTask,
    clearCompletedTasks,
    updatePreferences,
    setTheme,
    openSettings,
    closeSettings,
    openLogViewer,
    closeLogViewer,
    openImagePreview,
    closeImagePreview,
    setDatabaseConnected,
  };

  return <AppStoreContext.Provider value={store}>{children}</AppStoreContext.Provider>;
};
