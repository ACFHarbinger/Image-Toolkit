/**
 * LoginDialog opens the sidecar C++ vault session.
 * The password is an auth.unlock parameter only. auth.status is the session.
 * localStorage remembers the account name, not a login flag.
 */

import React, { useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { HostClient, RustTransport } from '../../hostclient';
import { useAppStore } from '../../store/appStore';
import { LogIn, UserPlus, Eye, EyeOff, Sun, Moon } from 'lucide-react';

export interface AuthResult {
  success: boolean;
  message?: string;
}

export interface SessionClient {
  create(account: string, password: string): Promise<AuthResult>;
}

export interface AuthBridge {
  authUnlock(params: { account: string; password: string }): Promise<{ success: boolean; account: string; message: string }>;
  authStatus(params: { account: string }): Promise<{ unlocked: boolean; account: string; reason: string }>;
}

async function createAccount(account: string, password: string): Promise<AuthResult> {
  return invoke<AuthResult>("create_user_account", { accountName: account, password });
}

const defaultSession: SessionClient = {
  create: createAccount,
};

interface LoginDialogProps {
  onClose?: () => void;
  session?: SessionClient;
  authClient?: AuthBridge;
}

export const LoginDialog: React.FC<LoginDialogProps> = ({ session = defaultSession, authClient }) => {
  const { preferences, setTheme, login } = useAppStore();
  const ownedClient = useMemo(
    () =>
      new HostClient(new RustTransport(), {
        clientName: "login-dialog",
        clientVersion: "1.0.0",
      }),
    [],
  );
  const bridge = authClient ?? ownedClient;
  const [accountName, setAccountName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const confirmSession = async (account: string) => {
    const opened = await bridge.authUnlock({ account, password });
    if (!opened.success) {
      setError(opened.message || 'Login failed.');
      return;
    }
    const status = await bridge.authStatus({ account });
    if (!status.unlocked) {
      setError(status.reason || 'C++ vault session locked');
      return;
    }
    login(status.account || account);
  };

  const submit = async (action: "login" | "create") => {
    const account = accountName.trim();
    if (!account) {
      setError('Please enter an account name');
      return;
    }
    if (!password) {
      setError('Please enter a password');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      if (action === "create") {
        const created = await session.create(account, password);
        if (!created.success) {
          setError(created.message || 'Account creation failed.');
          return;
        }
      }
      await confirmSession(account);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      void submit("login");
    }
  };

  const toggleTheme = () => {
    const newTheme = preferences.theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  };

  const isDark = preferences.theme === 'dark';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className={`w-full max-w-md rounded-2xl shadow-2xl border ${isDark
          ? 'bg-gray-800 border-gray-700 text-white'
          : 'bg-white border-gray-200 text-gray-900'
          }`}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'
            }`}
        >
          <h2 className="text-xl font-bold">
            <span className={isDark ? 'text-cyan-400' : 'text-blue-600'}>
              Welcome - Secure Toolkit Access
            </span>
          </h2>
          <button
            onClick={toggleTheme}
            className={`p-2 rounded-lg transition-colors ${isDark ? 'hover:bg-gray-700 text-cyan-400' : 'hover:bg-gray-100 text-blue-600'
              }`}
            aria-label="Toggle theme"
          >
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-6 space-y-4">
          {/* Error Message */}
          {error && (
            <div role="alert" className="p-3 rounded-lg bg-red-500/10 border border-red-500/50 text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Account Name Input */}
          <div>
            <label
              htmlFor="accountName"
              className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'
                }`}
            >
              Account Name
            </label>
            <input
              id="accountName"
              type="text"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="e.g., user_id_123"
              disabled={isLoading}
              className={`w-full px-4 py-2 rounded-lg border focus:outline-none focus:ring-2 transition-colors ${isDark
                ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400 focus:ring-cyan-500'
                : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-blue-500'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
            />
          </div>

          {/* Password Input */}
          <div>
            <label
              htmlFor="password"
              className={`block text-sm font-medium mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'
                }`}
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter your password"
                disabled={isLoading}
                className={`w-full px-4 py-2 pr-12 rounded-lg border focus:outline-none focus:ring-2 transition-colors ${isDark
                  ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400 focus:ring-cyan-500'
                  : 'bg-white border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-blue-500'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className={`absolute right-3 top-1/2 -translate-y-1/2 ${isDark ? 'text-gray-400 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'
                  }`}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => void submit("create")}
              disabled={isLoading}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-semibold transition-colors ${isDark
                ? 'bg-gray-700 text-white hover:bg-gray-600'
                : 'bg-gray-200 text-gray-900 hover:bg-gray-300'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <UserPlus size={18} />
              Create Account
            </button>
            <button
              onClick={() => void submit("login")}
              disabled={isLoading}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-white transition-colors ${isDark
                ? 'bg-cyan-600 hover:bg-cyan-500'
                : 'bg-blue-600 hover:bg-blue-700'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <LogIn size={18} />
              {isLoading ? 'Authenticating...' : 'Login'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
