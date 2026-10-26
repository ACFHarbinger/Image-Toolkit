export interface ThumbnailItem {
  id: string;
  name: string;
  path: string;
}

interface ThumbnailGalleryProps {
  items: ThumbnailItem[];
  selectedIds: string[];
  onToggle: (id: string) => void;
}

export function ThumbnailGallery({ items, selectedIds, onToggle }: ThumbnailGalleryProps) {
  return (
    <div role="list" className="flex flex-wrap gap-2">
      {items.map((item) => {
        const pressed = selectedIds.includes(item.id);
        return (
          <div role="listitem" key={item.id}>
            <button type="button" aria-pressed={pressed} title={item.path} onClick={() => onToggle(item.id)}>
              {item.name}
            </button>
          </div>
        );
      })}
    </div>
  );
}
