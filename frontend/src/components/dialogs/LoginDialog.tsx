/**
 * LoginDialog - locked session status (#918).
 *
 * Unlock stays on the C++ session. The password is not sent and no account
 * is created. auth.status only reports that the vault was not opened.
 */

import React, { useMemo, useState } from 'react';
import { HostClient, RustTransport } from '../../hostclient';
import { useAppStore } from '../../store/appStore';
import { LogIn, UserPlus, Eye, EyeOff, Sun, Moon } from 'lucide-react';

export interface AuthStatusClient {
  authStatus(params: { account: string }): Promise<{ unlocked: boolean; account: string; reason: string }>;
}

interface LoginDialogProps {
  onClose?: () => void;
  authClient?: AuthStatusClient;
}

export const LoginDialog: React.FC<LoginDialogProps> = ({ authClient }) => {
  const { preferences, setTheme } = useAppStore();
  const ownedClient = useMemo(
    () =>
      new HostClient(new RustTransport(), {
        clientName: "login-dialog",
        clientVersion: "1.0.0",
      }),
    [],
  );
  const client = authClient ?? ownedClient;
  const [accountName, setAccountName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const reportLocked = async () => {
    const account = accountName.trim();
    if (!account) {
      setError('Please enter an account name');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const result = await client.authStatus({ account });
      setError(result.reason);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to read the session status.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      void reportLocked();
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
              onClick={() => void reportLocked()}
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
              onClick={() => void reportLocked()}
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
