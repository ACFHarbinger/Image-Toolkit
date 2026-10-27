import { FormEvent, ReactNode } from "react";

/** Shared field chrome for catalog pages that were raw browser controls. */
export const deskControlClass =
  "w-full rounded-lg border border-it-border bg-it-window-bg px-3 py-2 text-sm text-it-text outline-none focus:border-it-accent";

export const deskButtonClass =
  "inline-flex w-fit items-center rounded-lg bg-it-accent px-4 py-2 text-sm font-semibold text-white hover:bg-it-accent-hover";

const frameClass =
  "mx-auto flex w-full max-w-3xl flex-col gap-4 rounded-2xl border border-it-border bg-it-surface p-6 shadow-sm";

export function DeskField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid items-start gap-1.5 sm:grid-cols-[10rem_minmax(0,1fr)] sm:items-center sm:gap-4">
      <span className="text-sm font-medium text-it-text">{label}</span>
      {children}
    </label>
  );
}

export function DeskForm({
  testId,
  title,
  description,
  onSubmit,
  children,
}: {
  testId: string;
  title: string;
  description?: string;
  onSubmit: (event: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-full bg-it-window-bg p-6 text-it-text">
      <form data-testid={testId} onSubmit={onSubmit} className={frameClass}>
        <header>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          {description ? <p className="mt-1 text-sm text-it-muted-text">{description}</p> : null}
        </header>
        {children}
      </form>
    </div>
  );
}
