import { useForm } from "@tanstack/vue-form";

/** Shared TanStack Form helper for docs-site demos (search-filter forms, hub controls). */
export function useCustomForm<TValues extends Record<string, unknown>>(options: {
  defaultValues: TValues;
  onSubmit?: (props: { value: TValues }) => void | Promise<void>;
}) {
  return useForm({
    defaultValues: options.defaultValues,
    onSubmit: options.onSubmit
      ? async ({ value }) => {
          await options.onSubmit?.({ value: value as TValues });
        }
      : undefined,
  });
}

export { useForm } from "@tanstack/vue-form";
