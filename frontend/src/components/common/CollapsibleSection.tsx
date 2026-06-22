import React, { ReactNode } from "react";
import { ChevronsUpDown } from "lucide-react";

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  startOpen?: boolean;
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  children,
  startOpen = false,
}) => {
  return (
    <details
      open={startOpen}
      className="mb-4 border border-gray-200/50 dark:border-gray-700/50 rounded-lg shadow-sm"
    >
      <summary className="flex items-center justify-between p-4 font-semibold text-gray-800 bg-gray-50/50 rounded-t-lg cursor-pointer dark:bg-gray-800/50 dark:text-gray-200 hover:bg-gray-100/50 dark:hover:bg-gray-700/50 transition-colors">
        {title}
        <ChevronsUpDown size={18} className="text-gray-500" />
      </summary>
      <div className="p-4 bg-white/50 dark:bg-gray-900/20 rounded-b-lg">
        {children}
      </div>
    </details>
  );
};

export default CollapsibleSection;
