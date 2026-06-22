/**
 * SettingsDialog - Application Settings & Configuration
 * 
 * Provides comprehensive settings management including:
 * - Theme preferences
 * - Default tab configurations
 * - System preference profiles
 * - Master password reset
 */

import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useAppStore } from '../store/appStore';
import { X, Save, RotateCcw, Trash2, Plus } from 'lucide-react';

interface SettingsDialogProps {
  onClose: () => void;
}

interface TabConfiguration {
  [tabName: string]: {
    [configName: string]: any;
  };
}

interface SystemProfile {
  theme: 'light' | 'dark' | 'system';
  active_tab_configs: Record<string, string>;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ onClose }) => {
  const { preferences, setTheme, updatePreferences, vault } = useAppStore();
  
  const [activeSection, setActiveSection] = useState<'general' | 'tabs' | 'profiles'>('general');
  const [selectedTheme, setSelectedTheme] = useState(preferences.theme);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Tab Configurations
  const [tabConfigurations, setTabConfigurations] = useState<TabConfiguration>({});
  const [selectedTab, setSelectedTab] = useState('');
  const [selectedConfig, setSelectedConfig] = useState('');
  const [configEditor, setConfigEditor] = useState('');
  const [configName, setConfigName] = useState('');
  
  // System Profiles
  const [profiles, setProfiles] = useState<Record<string, SystemProfile>>({});
  const [selectedProfile, setSelectedProfile] = useState('');
  const [newProfileName, setNewProfileName] = useState('');

  const isDark = preferences.theme === 'dark';

  // Load settings from backend
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const settings = await invoke<any>('load_user_settings', {
        accountName: vault?.accountName,
      });
      
      if (settings) {
        setTabConfigurations(settings.tab_configurations || {});
        setProfiles(settings.system_preference_profiles || {});
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const handleSaveSettings = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      // Validate password if changing
      if (newPassword) {
        if (newPassword !== confirmPassword) {
          setMessage({ type: 'error', text: 'Passwords do not match' });
          setIsSaving(false);
          return;
        }

        // Update password
        await invoke('update_master_password', {
          accountName: vault?.accountName,
          newPassword,
        });
      }

      // Save theme preference
      setTheme(selectedTheme);

      // Save all settings to backend
      await invoke('save_user_settings', {
        accountName: vault?.accountName,
        settings: {
          theme: selectedTheme,
          tab_configurations: tabConfigurations,
          system_preference_profiles: profiles,
          active_tab_configs: preferences.tabConfigurations,
        },
      });

      setMessage({ type: 'success', text: 'Settings saved successfully!' });
      
      // Clear password fields
      setNewPassword('');
      setConfirmPassword('');
      
      // Close after brief delay
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      console.error('Save error:', err);
      setMessage({ type: 'error', text: err.message || 'Failed to save settings' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetSettings = () => {
    setSelectedTheme('dark');
    setNewPassword('');
    setConfirmPassword('');
    setMessage({ type: 'success', text: 'Settings reset to defaults' });
  };

  const handleSaveProfile = () => {
    if (!newProfileName.trim()) {
      setMessage({ type: 'error', text: 'Please enter a profile name' });
      return;
    }

    const newProfile: SystemProfile = {
      theme: selectedTheme,
      active_tab_configs: preferences.tabConfigurations || {},
    };

    setProfiles((prev) => ({
      ...prev,
      [newProfileName]: newProfile,
    }));

    setMessage({ type: 'success', text: `Profile "${newProfileName}" saved` });
    setNewProfileName('');
  };

  const handleLoadProfile = () => {
    if (!selectedProfile) return;

    const profile = profiles[selectedProfile];
    if (profile) {
      setSelectedTheme(profile.theme);
      updatePreferences({ tabConfigurations: profile.active_tab_configs });
      setMessage({ type: 'success', text: `Profile "${selectedProfile}" loaded` });
    }
  };

  const handleDeleteProfile = () => {
    if (!selectedProfile) return;

    setProfiles((prev) => {
      const updated = { ...prev };
      delete updated[selectedProfile];
      return updated;
    });

    setMessage({ type: 'success', text: `Profile "${selectedProfile}" deleted` });
    setSelectedProfile('');
  };

  const renderGeneralSettings = () => (
    <div className="space-y-6">
      {/* Theme Selection */}
      <div>
        <label className={`block text-sm font-semibold mb-3 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          Application Theme
        </label>
        <div className="grid grid-cols-3 gap-3">
          {(['dark', 'light', 'system'] as const).map((theme) => (
            <button
              key={theme}
              onClick={() => setSelectedTheme(theme)}
              className={`px-4 py-3 rounded-lg border-2 font-medium capitalize transition-all ${
                selectedTheme === theme
                  ? isDark
                    ? 'border-cyan-500 bg-cyan-500/20 text-cyan-300'
                    : 'border-blue-600 bg-blue-50 text-blue-700'
                  : isDark
                  ? 'border-gray-600 bg-gray-700/50 text-gray-300 hover:border-gray-500'
                  : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
              }`}
            >
              {theme}
            </button>
          ))}
        </div>
      </div>

      {/* Password Reset */}
      <div className="pt-4 border-t border-gray-700">
        <h3 className={`text-sm font-semibold mb-3 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          Change Master Password
        </h3>
        <div className="space-y-3">
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New Password"
            className={`w-full px-4 py-2 rounded-lg border ${
              isDark
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
            } focus:outline-none focus:ring-2 focus:ring-cyan-500`}
          />
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm Password"
            className={`w-full px-4 py-2 rounded-lg border ${
              isDark
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
            } focus:outline-none focus:ring-2 focus:ring-cyan-500`}
          />
        </div>
      </div>
    </div>
  );

  const renderTabSettings = () => (
    <div className="space-y-4">
      <p className={isDark ? 'text-gray-400' : 'text-gray-600'}>
        Tab configuration management will be available here.
      </p>
    </div>
  );

  const renderProfileSettings = () => (
    <div className="space-y-6">
      {/* Load/Delete Profile */}
      <div>
        <label className={`block text-sm font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          Load Existing Profile
        </label>
        <div className="flex gap-2">
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            className={`flex-1 px-4 py-2 rounded-lg border ${
              isDark
                ? 'bg-gray-700 border-gray-600 text-white'
                : 'bg-white border-gray-300 text-gray-900'
            } focus:outline-none focus:ring-2 focus:ring-cyan-500`}
          >
            <option value="">Select profile...</option>
            {Object.keys(profiles).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            onClick={handleLoadProfile}
            disabled={!selectedProfile}
            className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Load
          </button>
          <button
            onClick={handleDeleteProfile}
            disabled={!selectedProfile}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Trash2 size={18} />
          </button>
        </div>
      </div>

      {/* Create New Profile */}
      <div>
        <label className={`block text-sm font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          Create New Profile
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            placeholder="Profile name (e.g., Work Laptop)"
            className={`flex-1 px-4 py-2 rounded-lg border ${
              isDark
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500'
            } focus:outline-none focus:ring-2 focus:ring-cyan-500`}
          />
          <button
            onClick={handleSaveProfile}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 flex items-center gap-2"
          >
            <Plus size={18} />
            Save
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className={`w-full max-w-3xl max-h-[90vh] flex flex-col rounded-2xl shadow-2xl border ${
          isDark ? 'bg-gray-800 border-gray-700 text-white' : 'bg-white border-gray-200 text-gray-900'
        }`}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${
            isDark ? 'border-gray-700' : 'border-gray-200'
          }`}
        >
          <h2 className="text-xl font-bold">Application Settings</h2>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg transition-colors ${
              isDark ? 'hover:bg-gray-700 text-gray-400' : 'hover:bg-gray-100 text-gray-600'
            }`}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className={`flex border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
          {[
            { id: 'general', label: 'General' },
            { id: 'tabs', label: 'Tab Configs' },
            { id: 'profiles', label: 'Profiles' },
          ].map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id as any)}
              className={`px-6 py-3 font-medium border-b-2 transition-colors ${
                activeSection === section.id
                  ? isDark
                    ? 'border-cyan-500 text-cyan-400'
                    : 'border-blue-600 text-blue-600'
                  : isDark
                  ? 'border-transparent text-gray-400 hover:text-gray-300'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              {section.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {message && (
            <div
              className={`mb-4 p-3 rounded-lg ${
                message.type === 'success'
                  ? 'bg-green-500/10 border border-green-500/50 text-green-500'
                  : 'bg-red-500/10 border border-red-500/50 text-red-500'
              }`}
            >
              {message.text}
            </div>
          )}

          {activeSection === 'general' && renderGeneralSettings()}
          {activeSection === 'tabs' && renderTabSettings()}
          {activeSection === 'profiles' && renderProfileSettings()}
        </div>

        {/* Footer */}
        <div
          className={`flex items-center justify-end gap-3 px-6 py-4 border-t ${
            isDark ? 'border-gray-700' : 'border-gray-200'
          }`}
        >
          <button
            onClick={handleResetSettings}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              isDark
                ? 'bg-gray-700 text-white hover:bg-gray-600'
                : 'bg-gray-200 text-gray-900 hover:bg-gray-300'
            }`}
          >
            <RotateCcw size={18} className="inline mr-2" />
            Reset
          </button>
          <button
            onClick={handleSaveSettings}
            disabled={isSaving}
            className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            <Save size={18} className="inline mr-2" />
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
