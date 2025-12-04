import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../../components/FormRow.tsx';
import PathInput from '../../components/PathInput.tsx';
import CollapsibleSection from '../../components/CollapsibleSection.tsx';
import ToggleButtonGroup from '../../components/ToggleButtonGroup.tsx';
import { SUPPORTED_IMG_FORMATS } from '../../constants.ts';

interface MergeTabProps {}

export interface MergeTabHandle {
  getData: () => {
    action: string;
    direction: string;
    input_paths: string[];
    output_path: string;
    input_formats: string[];
    spacing: number;
    grid_size: [number, number] | null;
  };
}

const MergeTab = forwardRef<MergeTabHandle, MergeTabProps>((props, ref) => {
  const [direction, setDirection] = useState<string>('horizontal');
  const [inputPath, setInputPath] = useState<string>('');
  const [outputPath, setOutputPath] = useState<string>('');
  const [inputFormats, setInputFormats] = useState<Set<string>>(new Set());
  const [spacing, setSpacing] = useState<number>(0);
  const [gridRows, setGridRows] = useState<number>(2);
  const [gridCols, setGridCols] = useState<number>(2);

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'merge',
      direction: direction,
      input_paths: inputPath.split(',').map(p => p.trim()).filter(Boolean),
      output_path: outputPath,
      input_formats: Array.from(inputFormats),
      spacing: spacing,
      grid_size: direction === 'grid' ? [gridRows, gridCols] : null,
    }),
  }));

  const toggleFormat = (format: string) => {
    setInputFormats((prev) => {
      const next = new Set(prev);
      if (next.has(format)) {
        next.delete(format);
      } else {
        next.add(format);
      }
      return next;
    });
  };
  
  const inputBaseClasses = "px-4 py-2 text-gray-900 bg-white/80 border border-gray-300 rounded-md dark:bg-gray-800/80 dark:text-gray-100 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-all";

  return (
    <div className="p-6">
      <FormRow label="Direction:">
        <select
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          className={`${inputBaseClasses} w-full sm:w-1/2`}
        >
          <option value="horizontal">Horizontal</option>
          <option value="vertical">Vertical</option>
          <option value="grid">Grid</option>
        </select>
      </FormRow>

      <FormRow label="Input Paths (Files or Dir):">
        <PathInput
          value={inputPath}
          onChange={(e) => setInputPath(e.target.value)}
          onBrowseFile={() => setInputPath(prev => prev + (prev ? ', ' : '') + '/simulated/file.jpg')}
          onBrowseDir={() => setInputPath('/simulated/directory/')}
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Separate multiple files with a comma.</p>
      </FormRow>

      {direction === 'grid' && (
        <FormRow label="Grid Size:">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 font-medium">
              Rows:
              <input
                type="number"
                value={gridRows}
                min="1"
                onChange={(e) => setGridRows(Number(e.target.value))}
                className={`${inputBaseClasses} w-24`}
              />
            </label>
            <label className="flex items-center gap-2 font-medium">
              Cols:
              <input
                type="number"
                value={gridCols}
                min="1"
                onChange={(e) => setGridCols(Number(e.target.value))}
                className={`${inputBaseClasses} w-24`}
              />
            </label>
          </div>
        </FormRow>
      )}

      <FormRow label="Spacing (px):">
        <input
          type="number"
          value={spacing}
          min="0"
          onChange={(e) => setSpacing(Number(e.target.value))}
          className={`${inputBaseClasses} w-24`}
        />
      </FormRow>

      <CollapsibleSection title="Output Path (Optional)">
        <FormRow label="Output Path:">
          <PathInput
            value={outputPath}
            onChange={(e) => setOutputPath(e.target.value)}
            onBrowseFile={() => setOutputPath('/simulated/output/image.png')}
            onBrowseDir={() => setOutputPath('/simulated/output/directory/')}
          />
        </FormRow>
      </CollapsibleSection>

      <CollapsibleSection title="Input Formats (Optional)">
        <ToggleButtonGroup
          items={SUPPORTED_IMG_FORMATS}
          selectedItems={inputFormats}
          onToggle={toggleFormat}
        />
      </CollapsibleSection>
    </div>
  );
});

export default MergeTab;