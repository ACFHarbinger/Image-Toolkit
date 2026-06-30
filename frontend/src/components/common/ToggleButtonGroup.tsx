import React from "react";

interface ToggleButtonGroupProps {
  items: string[];
  selectedItems: Set<string>;
  onToggle: (item: string) => void;
}

const ToggleButtonGroup: React.FC<ToggleButtonGroupProps> = ({
  items,
  selectedItems,
  onToggle,
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const isSelected = selectedItems.has(item);
        return (
          <button
            key={item}
            onClick={() => onToggle(item)}
            className={`px-4 py-2 text-sm font-medium rounded-full shadow-sm transition-all duration-200 transform ${
              isSelected
                ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg scale-105"
                : "bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600"
            }`}
          >
            {item}
          </button>
        );
      })}
    </div>
  );
};

export default ToggleButtonGroup;
