interface JobProgressProps {
  label: string;
  done: number;
  total: number;
  onCancel?: () => void;
}

export function JobProgress({ label, done, total, onCancel }: JobProgressProps) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span>{label}</span>
      <progress aria-label={label} value={done} max={total > 0 ? total : undefined} />
      {onCancel ? (
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      ) : null}
    </div>
  );
}
