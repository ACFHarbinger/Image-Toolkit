/**
 * TaskProgress - Background Task Progress Indicator
 *
 * Displays active and completed background tasks in a collapsible panel.
 */

import React, { useState } from 'react';
import { X, ChevronDown, ChevronUp, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const TaskProgress: React.FC = () => {
  const { tasks, removeTask, clearCompletedTasks, preferences } = useAppStore();
  const [isExpanded, setIsExpanded] = useState(true);

  const isDark = preferences.theme === 'dark';
  const taskArray = Array.from(tasks.values());
  const activeTasks = taskArray.filter((t) => t.status === 'running');
  const completedTasks = taskArray.filter((t) => t.status === 'completed' || t.status === 'failed');

  // Don't show panel if no tasks
  if (taskArray.length === 0) {
    return null;
  }

  return (
    <div
      className={`fixed bottom-4 right-4 w-96 max-h-[500px] flex flex-col rounded-xl shadow-2xl border z-40 ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
        }`}
    >
      {/* Header */}
      <div
        className={`flex items-center justify-between px-4 py-3 border-b cursor-pointer ${isDark ? 'border-gray-700 bg-gray-900/50' : 'border-gray-200 bg-gray-50'
          }`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Loader2
            size={16}
            className={`${activeTasks.length > 0 ? 'animate-spin text-blue-500' : 'text-gray-400'}`}
          />
          <h3 className={`font-semibold text-sm ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
            Background Tasks ({activeTasks.length} active)
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {completedTasks.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                clearCompletedTasks();
              }}
              className="text-xs text-red-500 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              Clear Done
            </button>
          )}
          <button onClick={(e) => e.stopPropagation()}>
            {isExpanded ? (
              <ChevronDown size={16} className="text-gray-400" />
            ) : (
              <ChevronUp size={16} className="text-gray-400" />
            )}
          </button>
        </div>
      </div>

      {/* Task List */}
      {isExpanded && (
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {/* Active Tasks */}
          {activeTasks.map((task) => (
            <div
              key={task.id}
              className={`p-3 rounded-lg border ${isDark ? 'bg-gray-700/50 border-gray-600' : 'bg-blue-50 border-blue-200'
                }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 flex-1">
                  <Loader2 size={14} className="animate-spin text-blue-500 flex-shrink-0" />
                  <span className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    {task.id}
                  </span>
                </div>
                <button
                  onClick={() => removeTask(task.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                  title="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>

              {task.message && (
                <p className={`text-xs mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  {task.message}
                </p>
              )}

              {/* Progress Bar */}
              <div className={`w-full h-2 rounded-full overflow-hidden ${isDark ? 'bg-gray-600' : 'bg-gray-200'}`}>
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
              <div className="flex justify-between items-center mt-1">
                <span className="text-xs text-gray-400">{task.progress}%</span>
                {task.startTime && (
                  <span className="text-xs text-gray-400">
                    {Math.floor((Date.now() - task.startTime) / 1000)}s
                  </span>
                )}
              </div>
            </div>
          ))}

          {/* Completed Tasks */}
          {completedTasks.map((task) => (
            <div
              key={task.id}
              className={`p-3 rounded-lg border ${task.status === 'completed'
                  ? isDark
                    ? 'bg-green-900/20 border-green-800'
                    : 'bg-green-50 border-green-200'
                  : isDark
                    ? 'bg-red-900/20 border-red-800'
                    : 'bg-red-50 border-red-200'
                }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 flex-1">
                  {task.status === 'completed' ? (
                    <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                  ) : (
                    <XCircle size={14} className="text-red-500 flex-shrink-0" />
                  )}
                  <span className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    {task.id}
                  </span>
                </div>
                <button
                  onClick={() => removeTask(task.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors"
                  title="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>

              {task.message && (
                <p
                  className={`text-xs mt-1 ${task.status === 'completed'
                      ? isDark
                        ? 'text-green-400'
                        : 'text-green-700'
                      : isDark
                        ? 'text-red-400'
                        : 'text-red-700'
                    }`}
                >
                  {task.message}
                </p>
              )}

              {task.endTime && task.startTime && (
                <p className="text-xs text-gray-400 mt-1">
                  Completed in {Math.floor((task.endTime - task.startTime) / 1000)}s
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
