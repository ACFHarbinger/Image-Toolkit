import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

export type DbStatus = "checking" | "connected" | "disconnected";

interface StatusBarProps {
  dbStatus: DbStatus;
  activeId: string;
  windowRole: string;
}

export function StatusBar({ dbStatus, activeId, windowRole }: StatusBarProps) {
  return (
    <footer
      aria-label="Status bar"
      className="flex h-7 items-center gap-4 border-t border-gray-200 bg-gray-50 px-3 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
    >
      <span className="flex items-center gap-1">
        {dbStatus === "checking" && <Loader2 size={12} className="animate-spin" />}
        {dbStatus === "connected" && <CheckCircle2 size={12} className="text-green-600" />}
        {dbStatus === "disconnected" && <AlertCircle size={12} className="text-red-500" />}
        {dbStatus === "checking" ? "Checking database" : dbStatus === "connected" ? "Database connected" : "Database offline"}
      </span>
      <span data-testid="active-catalog-id">{activeId}</span>
      <span data-testid="active-window-role">{windowRole}</span>
    </footer>
  );
}
