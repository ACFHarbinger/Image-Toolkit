import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../../components/FormRow.tsx';
import ToggleButtonGroup from '../../components/ToggleButtonGroup.tsx';
import { ALL_COMMON_TAGS } from '../../constants.ts';

interface SearchTabProps {
  showModal: (message: string, type: 'info' | 'success' | 'error' | 'custom') => void;
}

export interface SearchTabHandle {
  getData: () => {
    action: string;
    query: string;
    tags: string[];
  };
}

const SearchTab = forwardRef<SearchTabHandle, SearchTabProps>(({ showModal }, ref) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'search',
      query: searchQuery,
      tags: Array.from(selectedTags),
    }),
  }));

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  return (
    <div className="p-6">
      <FormRow label="Search Query:">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-4 py-2 text-gray-900 bg-white/80 border border-gray-300 rounded-md dark:bg-gray-800/80 dark:text-gray-100 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
        />
      </FormRow>
      <FormRow label="Common Tags:">
        <ToggleButtonGroup
          items={ALL_COMMON_TAGS}
          selectedItems={selectedTags}
          onToggle={toggleTag}
        />
      </FormRow>
      <button onClick={() => showModal("Simulating Search Operation...", "info")} className="w-full px-4 py-2 font-semibold text-white transition-colors bg-blue-600 rounded-md shadow-sm hover:bg-blue-700">
        Run Search
      </button>
    </div>
  );
});

export default SearchTab;