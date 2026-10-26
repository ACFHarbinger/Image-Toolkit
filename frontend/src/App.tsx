import React, { ReactNode, useState } from "react";
import { useAppStore } from "./store/appStore";
import { LoginDialog } from "./components/dialogs/LoginDialog";
import { ImagePreview } from "./components/sublime/ImagePreview";
import { TaskProgress } from "./components/sublime/TaskProgress";
import { Shell } from "./shell/Shell";

interface ModalData {
  show: boolean;
  message: string;
  type: "info" | "error" | "success";
  content: React.ReactNode | null;
}

const App: React.FC = () => {
  const {
    isLoggedIn,
    showImagePreview,
    previewImagePath,
    closeImagePreview,
  } = useAppStore();

  const [modal, setModal] = useState<ModalData>({
    show: false,
    message: "",
    type: "info",
    content: null,
  });

  const showModal = (
    message: string | ReactNode,
    type: "info" | "error" | "success" = "info",
    duration: number = 0,
  ) => {
    setModal({
      show: true,
      message: typeof message === "string" ? message : "",
      type,
      content: typeof message !== "string" ? message : null,
    });

    if (duration > 0) {
      setTimeout(() => setModal((prev) => ({ ...prev, show: false })), duration);
    }
  };

  if (!isLoggedIn) {
    return <LoginDialog />;
  }

  return (
    <>
      <Shell showModal={showModal} />
      <div
        className={`fixed inset-0 z-50 ${modal.show ? "flex" : "hidden"} items-center justify-center`}
        onClick={() => setModal((prev) => ({ ...prev, show: false }))}
      >
        <div
          className="w-full max-w-sm rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800"
          onClick={(event) => event.stopPropagation()}
        >
          {modal.content || (
            <p
              className={`text-center ${
                modal.type === "error" ? "text-red-500" : "text-gray-900 dark:text-gray-100"
              }`}
            >
              {modal.message}
            </p>
          )}
          <button
            type="button"
            onClick={() => setModal((prev) => ({ ...prev, show: false }))}
            className="mt-4 w-full rounded-lg bg-violet-500 py-2 text-white hover:bg-violet-600"
          >
            Close
          </button>
        </div>
      </div>
      {showImagePreview && previewImagePath && (
        <ImagePreview path={previewImagePath} onClose={closeImagePreview} />
      )}
      <TaskProgress />
    </>
  );
};

export default App;
