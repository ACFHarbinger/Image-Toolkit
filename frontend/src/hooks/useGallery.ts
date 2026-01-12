import { useState, useMemo } from "react";
import { GalleryItem } from "./galleryItem.ts";

export function useGallery(pageSize = 100) {
  // --- Data State ---
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());

  // --- Pagination State ---
  const [currentPage, setCurrentPage] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(pageSize);

  // --- Computed ---
  const totalPages = useMemo(
    () => Math.ceil(items.length / itemsPerPage),
    [items.length, itemsPerPage],
  );

  const paginatedItems = useMemo(() => {
    // Ensure current page is valid
    if (currentPage >= totalPages && totalPages > 0) {
      setCurrentPage(Math.max(0, totalPages - 1));
    }

    const start = currentPage * itemsPerPage;
    return items.slice(start, start + itemsPerPage);
  }, [items, currentPage, itemsPerPage, totalPages]);

  // --- Actions ---
  const setGalleryItems = (newItems: GalleryItem[], append = false) => {
    if (append) {
      setItems((prev) => [...prev, ...newItems]);
    } else {
      setItems(newItems);
      setCurrentPage(0);
      setSelectedPaths(new Set());
    }
  };

  const selectItem = (path: string, multiSelect = false) => {
    setSelectedPaths((prev) => {
      const next = new Set(multiSelect ? prev : []);
      if (next.has(path) && multiSelect) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const selectBatch = (paths: Set<string>, append = false) => {
    setSelectedPaths((prev) => {
      if (append) {
        const next = new Set(prev);
        paths.forEach((p) => next.add(p));
        return next;
      }
      return paths;
    });
  };

  const deleteSelected = () => {
    setItems((prev) => prev.filter((i) => !selectedPaths.has(i.path)));
    setSelectedPaths(new Set());
  };

  const nextPage = () => setCurrentPage((p) => Math.min(p + 1, totalPages - 1));
  const prevPage = () => setCurrentPage((p) => Math.max(0, p - 1));

  return {
    items,
    paginatedItems,
    selectedPaths,
    pagination: {
      currentPage,
      totalPages,
      itemsPerPage,
      setItemsPerPage,
      nextPage,
      prevPage,
      setCurrentPage,
    },
    actions: {
      setGalleryItems,
      selectItem,
      selectBatch,
      deleteSelected,
    },
  };
}
