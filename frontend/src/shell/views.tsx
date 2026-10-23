import { ComponentType, ReactNode } from "react";
import { ConvertPilot } from "../views/ConvertPilot";
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
import type { HostClient } from "../hostclient";

export interface ViewProps {
  showModal: (
    message: string | ReactNode,
    type?: "info" | "error" | "success",
    duration?: number,
  ) => void;
  onAddImagesToDb?: (files: File[]) => void;
  hostClient: HostClient;
}

export const CATALOG_VIEWS: Record<string, ComponentType<any>> = {
  "system.convert": ConvertPilot,
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

export function CatalogView({
  entry,
  showModal,
  onAddImagesToDb,
  hostClient,
}: ViewProps & { entry: CatalogEntry }) {
  const View = CATALOG_VIEWS[entry.id];
  if (!View) {
    return (
      <div data-testid="unported-view">
        <h2>{entry.title}</h2>
        <p>Catalog id {entry.id} has no webview yet.</p>
      </div>
    );
  }
  const extra = entry.id === "library.scan" ? { onAddImagesToDb } : {};
  const convertProps = entry.id === "system.convert" ? { hostClient } : {};
  return <View showModal={showModal} {...extra} {...convertProps} />;
}
