import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../components/FormRow.tsx';
import PathInput from '../components/PathInput.tsx';
import CollapsibleSection from '../components/CollapsibleSection.tsx';
import ToggleButtonGroup from '../components/ToggleButtonGroup.tsx';
import { SUPPORTED_IMG_FORMATS } from '../constants.ts';

// Props interface (empty if no props are passed, but kept for consistency)
interface ConvertTabProps {}

export interface ConvertTabHandle {
  getData: () => {
    action: string;
    output_format: string;
    input_path: string;
    output_path: string;
    input_formats: string[];
  };
}

const ConvertTab = forwardRef<ConvertTabHandle, ConvertTabProps>((props, ref) => {
  const [outputFormat, setOutputFormat] = useState<string>('png');
  const [inputPath, setInputPath] = useState<string>('');
  const [outputPath, setOutputPath] = useState<string>('');
  const [inputFormats, setInputFormats] = useState<Set<string>>(new Set());

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'convert',
      output_format: outputFormat,
      input_path: inputPath,
      output_path: outputPath,
      input_formats: Array.from(inputFormats),
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

  return (
    <div className="p-6">
      <FormRow label="Output Format:">
        <input
          type="text"
          value={outputFormat}
          onChange={(e) => setOutputFormat(e.target.value)}
          className="w-full px-4 py-2 text-gray-900 bg-white/80 border border-gray-300 rounded-md sm:w-1/2 dark:bg-gray-800/80 dark:text-gray-100 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
        />
      </FormRow>
      <FormRow label="Input Path (File or Dir):">
        <PathInput
          value={inputPath}
          onChange={(e) => setInputPath(e.target.value)}
          onBrowseFile={() => setInputPath('/simulated/path/to/image.jpg')}
          onBrowseDir={() => setInputPath('/simulated/path/to/directory/')}
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

export default ConvertTab;