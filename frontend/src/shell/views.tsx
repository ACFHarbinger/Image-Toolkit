import { ComponentType, ReactNode } from "react";
import ConvertTab from "../tabs/core/ConvertTab";
import MergeTab from "../tabs/core/MergeTab";
import DeleteTab from "../tabs/core/DeleteTab";
import WallpaperTab from "../tabs/core/WallpaperTab";
import { ImageExtractorTab } from "../tabs/core/ImageExtractorTab";
import SearchTab from "../tabs/database/SearchTab";
import DatabaseTab from "../tabs/database/DatabaseTab";
import ScanMetadataTab from "../tabs/database/ScanMetadataTab";
import DriveSyncTab from "../tabs/web/DriveSyncTab";
import ImageCrawlerTab from "../tabs/web/ImageCrawlerTab";
import ReverseSearchTab from "../tabs/web/ReverseSearchTab";
import WebRequestsTab from "../tabs/web/WebRequestsTab";
import { UnifiedTrainTab } from "../tabs/models/UnifiedTrainTab";
import { UnifiedGenerateTab } from "../tabs/models/UnifiedGenerateTab";
import { MetaCLIPInferenceTab } from "../tabs/models/MetaCLIPInferenceTab";
import { R3GANEvaluateTab } from "../tabs/models/R3GANEvaluateTab";
import { BenchmarkDashboard } from "../tabs/apollo/BenchmarkDashboard";
import { HieEditorTab } from "../tabs/editor/HieEditorTab";
import { CatalogEntry } from "./catalog";

export interface ViewProps {
  showModal: (
    message: string | ReactNode,
    type?: "info" | "error" | "success",
    duration?: number,
  ) => void;
  onAddImagesToDb?: (files: File[]) => void;
}

/** Views keyed by catalog id. A new page does not extend a tab-id union. */
export const CATALOG_VIEWS: Record<string, ComponentType<any>> = {
  "system.convert": ConvertTab,
  "system.merge": MergeTab,
  "system.similarity": DeleteTab,
  "system.extractor": ImageExtractorTab,
  "system.wallpaper": WallpaperTab,
  "library.search": SearchTab,
  "library.management": DatabaseTab,
  "library.scan": ScanMetadataTab,
  "web.crawler": ImageCrawlerTab,
  "web.requests": WebRequestsTab,
  "web.drive-sync": DriveSyncTab,
  "web.reverse-search": ReverseSearchTab,
  "ml.training": UnifiedTrainTab,
  "ml.generation": UnifiedGenerateTab,
  "ml.evaluation": R3GANEvaluateTab,
  "ml.inference": MetaCLIPInferenceTab,
  "editor.hybrid": HieEditorTab,
  "developer.benchmarks": BenchmarkDashboard,
};

export function UnportedCatalogView({ entry }: { entry: CatalogEntry }) {
  return (
    <div data-testid="unported-view" className="p-8 text-sm text-gray-600 dark:text-gray-300">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{entry.title}</h2>
      <p className="mt-2">
        Catalog id <code>{entry.id}</code> has no webview yet.
      </p>
    </div>
  );
}

export function CatalogView({
  entry,
  showModal,
  onAddImagesToDb,
}: ViewProps & { entry: CatalogEntry }) {
  const View = CATALOG_VIEWS[entry.id];
  if (!View) {
    return <UnportedCatalogView entry={entry} />;
  }
  const extra = entry.id === "library.scan" ? { onAddImagesToDb } : {};
  return <View showModal={showModal} {...extra} />;
}
