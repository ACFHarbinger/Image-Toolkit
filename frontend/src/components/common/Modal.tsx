import React, { ReactNode } from "react";
import { Check, AlertCircle, X, LucideIcon } from "lucide-react";

type ModalType = "success" | "error" | "info" | "custom";

interface ModalProps {
  isVisible: boolean;
  content: string | ReactNode;
  type: ModalType;
  onClose: () => void;
}

interface ModalStyle {
  icon: LucideIcon | null;
  color: string;
  title: string;
}

const Modal: React.FC<ModalProps> = ({ isVisible, content, type, onClose }) => {
  if (!isVisible) return null;

  const getStyle = (): ModalStyle => {
    switch (type) {
      case "success":
        return { icon: Check, color: "bg-green-500", title: "Success" };
      case "error":
        return { icon: AlertCircle, color: "bg-red-500", title: "Error" };
      case "info":
        return {
          icon: AlertCircle,
          color: "bg-blue-500",
          title: "Information",
        };
      case "custom":
        return { icon: null, color: "bg-gray-700", title: "Preview" };
      default:
        return { icon: AlertCircle, color: "bg-gray-500", title: "Alert" };
    }
  };

  const { icon: Icon, color, title } = getStyle();
  const isStringContent = typeof content === "string";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm transition-opacity duration-300">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full m-4 transform transition-all duration-300 scale-100 dark:text-white">
        <header
          className={`flex items-center justify-between p-4 ${color} rounded-t-xl text-white`}
        >
          <div className="flex items-center">
            {Icon && <Icon size={20} className="mr-2" />}
            <h3 className="font-bold">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-white/20 transition-colors"
          >
            <X size={20} />
          </button>
        </header>

        <div className="p-6">
          {isStringContent ? (
            <p className="text-gray-700 dark:text-gray-300">{content}</p>
          ) : (
            content
          )}
        </div>

        <footer className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-semibold text-white bg-violet-600 rounded-md shadow-md hover:bg-violet-700 transition-colors"
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  );
};

export default Modal;
