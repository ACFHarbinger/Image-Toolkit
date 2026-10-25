import { LibraryManagement } from "../views/library/LibraryManagement";
import { DataBrowser } from "../views/library/DataBrowser";
import { ComponentType, ReactNode } from "react";
import { ConvertPilot } from "../views/ConvertPilot";
import { Listings } from "../views/library/Listings";
import { MergeView } from "../views/system/MergeView";
import { SimilarityView } from "../views/system/SimilarityView";
import { ExtractorView } from "../views/system/ExtractorView";
import { DlWorkspace, type DlRoute } from "../views/dl/DlWorkspace";
import WallpaperTab from "../tabs/core/WallpaperTab";
import { ImageSearch } from "../views/library/ImageSearch";
import { ScanMetadataView } from "../views/library/ScanMetadataView";
import DriveSyncTab from "../tabs/web/DriveSyncTab";
import ImageCrawlerTab from "../tabs/web/ImageCrawlerTab";
import ReverseSearchTab from "../tabs/web/ReverseSearchTab";
import WebRequestsTab from "../tabs/web/WebRequestsTab";
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

const DL_ROUTE: Record<string, DlRoute> = {
  "dl.train": "train",
  "dl.generate": "generate",
  "dl.review": "review",
  "dl.runs": "runs",
  "ml.training": "train",
  "ml.generation": "generate",
  "ml.evaluation": "review",
  "ml.inference": "review",
};

const HOST_CLIENT_IDS = new Set([
  "system.convert",
  "system.merge",
  "system.similarity",
  "system.extractor",
  "library.scan",
  "library.search",
  "library.listings",
  "library.management",
  "library.data-browser",
  ...Object.keys(DL_ROUTE),
]);

export const CATALOG_VIEWS: Record<string, ComponentType<any>> = {
  "system.convert": ConvertPilot,
  "library.listings": Listings,
  "system.merge": MergeView,
  "system.similarity": SimilarityView,
  "system.extractor": ExtractorView,
  "system.wallpaper": WallpaperTab,
  "library.search": ImageSearch,
  "library.management": LibraryManagement,
  "library.data-browser": DataBrowser,
  "library.scan": ScanMetadataView,
  "web.crawler": ImageCrawlerTab,
  "web.requests": WebRequestsTab,
  "web.drive-sync": DriveSyncTab,
  "web.reverse-search": ReverseSearchTab,
  "dl.train": DlWorkspace,
  "dl.generate": DlWorkspace,
  "dl.review": DlWorkspace,
  "dl.runs": DlWorkspace,
  "ml.training": DlWorkspace,
  "ml.generation": DlWorkspace,
  "ml.evaluation": DlWorkspace,
  "ml.inference": DlWorkspace,
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
  const route = DL_ROUTE[entry.id];
  const hostClientProps = HOST_CLIENT_IDS.has(entry.id) ? { hostClient, client: hostClient } : {};
  return <View showModal={showModal} {...extra} {...hostClientProps} {...(route ? { route } : {})} />;
}
