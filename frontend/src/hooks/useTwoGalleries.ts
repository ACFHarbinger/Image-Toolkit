import { useCallback } from 'react';
import { useGallery } from './useGallery.ts';
import { GalleryItem } from './galleryItem.ts';

export function useTwoGalleries(foundPageSize = 100, selectedPageSize = 100) {
  // 1. The "Found" Gallery (Source)
  // Holds all items discovered/scanned. Selection here implies adding to the "Selected" gallery.
  const found = useGallery(foundPageSize);

  // 2. The "Selected" Gallery (Target)
  // Holds items the user has chosen. Selection here implies marking for deletion/processing.
  const selected = useGallery(selectedPageSize);

  // --- Synchronization Actions ---

  /**
   * Toggles an item's presence in the Selected gallery.
   * Updates visual state in Found gallery to match.
   */
  const toggleSelection = useCallback((item: GalleryItem) => {
    const isAlreadySelected = found.selectedPaths.has(item.path);

    if (isAlreadySelected) {
      // Remove from 'Selected' gallery
      const newSelectedItems = selected.items.filter(i => i.path !== item.path);
      selected.actions.setGalleryItems(newSelectedItems);
      
      // Uncheck in 'Found' gallery
      found.actions.selectItem(item.path, true); 
    } else {
      // Add to 'Selected' gallery (append)
      selected.actions.setGalleryItems([item], true);
      
      // Check in 'Found' gallery
      found.actions.selectItem(item.path, true);
    }
  }, [found.selectedPaths, found.actions, selected.items, selected.actions]);

  /**
   * Selects all items visible on the current page of the Found gallery.
   * Adds them to the Selected gallery if not already present.
   */
  const selectAllFoundPage = useCallback(() => {
    const pageItems = found.paginatedItems;
    const newItemsToAdd: GalleryItem[] = [];
    const pathsToAdd = new Set<string>();

    pageItems.forEach(item => {
      if (!found.selectedPaths.has(item.path)) {
        newItemsToAdd.push(item);
        pathsToAdd.add(item.path);
      }
    });

    if (newItemsToAdd.length > 0) {
        // Add items to target
        selected.actions.setGalleryItems(newItemsToAdd, true);
        // Mark paths as selected in source (append to existing selection)
        found.actions.selectBatch(pathsToAdd, true);
    }
  }, [found.paginatedItems, found.selectedPaths, found.actions, selected.actions]);

  /**
   * Clears the Selected gallery completely and unchecks everything in Found.
   */
  const deselectAll = useCallback(() => {
    selected.actions.setGalleryItems([]);
    found.actions.selectBatch(new Set()); // Overwrite with empty set
  }, [selected.actions, found.actions]);

  /**
   * Removes items that are currently 'selected' (highlighted) inside the Selected Gallery panel.
   * This is equivalent to "Delete Selected" in the abstract class, but for the target list.
   */
  const removeSelectedTargets = useCallback(() => {
     const pathsToRemove = selected.selectedPaths;
     if (pathsToRemove.size === 0) return;

     // 1. Filter them out of the selected items list
     const remainingItems = selected.items.filter(i => !pathsToRemove.has(i.path));
     selected.actions.setGalleryItems(remainingItems);
     
     // 2. Sync the 'Found' gallery selection state to match the remaining items
     // (We essentially rebuild the Found selection set based on what's left)
     const newFoundSet = new Set(remainingItems.map(i => i.path));
     found.actions.selectBatch(newFoundSet);
     
  }, [selected.selectedPaths, selected.items, selected.actions, found.actions]);

  return {
    found,
    selected,
    actions: {
        toggleSelection,
        selectAllFoundPage,
        deselectAll,
        removeSelectedTargets
    }
  };
}