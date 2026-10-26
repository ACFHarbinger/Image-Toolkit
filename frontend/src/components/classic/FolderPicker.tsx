import { open } from "@tauri-apps/plugin-dialog";

interface FolderPickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

export function FolderPicker({ label, value, onChange }: FolderPickerProps) {
  const browse = async () => {
    try {
      const picked = await open({ directory: true, multiple: false, defaultPath: value || undefined });
      if (typeof picked === "string" && picked) {
        onChange(picked);
      }
    } catch {
      // The text field still edits the path when the dialog plugin is absent.
    }
  };

  const fieldId = `folder-${label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={fieldId}>{label}</label>
      <input
        id={fieldId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 flex-1 rounded border border-gray-300 px-2 py-1 dark:border-gray-600 dark:bg-gray-800"
      />
      <button type="button" onClick={() => void browse()}>
        Browse…
      </button>
    </div>
  );
}
