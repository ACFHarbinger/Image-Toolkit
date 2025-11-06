// src/tabs/ConvertTab.jsx
import React, { forwardRef, useState, useImperativeHandle } from 'react';
import FormRow from '../components/FormRow';
import PathInput from '../components/PathInput';
import CollapsibleSection from '../components/CollapsibleSection';
import ToggleButtonGroup from '../components/ToggleButtonGroup';
import { SUPPORTED_IMG_FORMATS } from '../constants';

const ConvertTab = forwardRef((props, ref) => {
  const [outputFormat, setOutputFormat] = useState('png');
  const [inputPath, setInputPath] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [inputFormats, setInputFormats] = useState(new Set());

  useImperativeHandle(ref, () => ({
    getData: () => ({
      action: 'convert',
      output_format: outputFormat,
      input_path: inputPath,
      output_path: outputPath,
      input_formats: Array.from(inputFormats),
    }),
  }));

  const toggleFormat = (format) => {
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