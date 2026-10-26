import { ComponentType, ReactNode } from "react";
import { ConvertPilot } from "../views/ConvertPilot";
import { Listings } from "../views/library/Listings";
import { ImageSearch } from "../views/library/ImageSearch";
import { LibraryManagement } from "../views/library/LibraryManagement";
import { DataBrowser } from "../views/library/DataBrowser";
import { ScanMetadataView } from "../views/library/ScanMetadataView";
import { MergeView } from "../views/system/MergeView";
import { SimilarityView } from "../views/system/SimilarityView";
import { ExtractorView } from "../views/system/ExtractorView";
import WallpaperView from "../views/system/WallpaperView";
import { StitchWorkspace } from "../views/stitch/StitchWorkspace";
import { DlWorkspace, type DlRoute } from "../views/dl/DlWorkspace";
import { ImageSearch } from "../views/library/ImageSearch";
import { ScanMetadataView } from "../views/library/ScanMetadataView";
import { ReverseSearchView } from "../views/web/ReverseSearch";
import { EntityReconView } from "../views/web/EntityRecon";
import { WebRequestsView } from "../views/web/WebRequestsView";
import { DriveSyncView } from "../views/web/DriveSyncView";
import { MediaLoaderView } from "../views/web/MediaLoaderView";
import { MangaColorizationView } from "../views/manga/MangaColorizationView";
import { MangaAnimationView } from "../views/manga/MangaAnimationView";
import { MangaPuppeteeringView } from "../views/manga/MangaPuppeteeringView";
import ImageCrawlerTab from "../tabs/web/ImageCrawlerTab";
import { EntityReconView } from "../views/web/EntityRecon";
import { ReverseSearchView } from "../views/web/ReverseSearch";
import { WebRequestsView } from "../views/web/WebRequestsView";
import { BenchmarkDashboard } from "../tabs/apollo/BenchmarkDashboard";
import { HieEditorTab } from "../tabs/editor/HieEditorTab";
import { LogDeskView } from "../views/windows/LogDeskView";
import { MetadataDeskView } from "../views/windows/MetadataDeskView";
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

const STITCH_ROUTE_IDS = [
  "stitch.stitch",
  "stitch.graph",
  "stitch.adjust",
  "stitch.canvas",
  "stitch.statistics",
  "stitch.sequence-builder",
  "stitch.hybrid",
  "stitch.animation-clusters",
] as const;

const STITCH_VIEWS: Record<string, ComponentType<any>> = Object.fromEntries(
  STITCH_ROUTE_IDS.map((id) => [id, StitchWorkspace]),
);

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

/** Catalog pages whose view takes a HostClient (passed as both prop spellings). */
const HOST_CLIENT_VIEWS = new Set([
  "system.convert",
  "system.merge",
  "system.similarity",
  "system.extractor",
  "system.wallpaper",
  "library.scan",
  "library.search",
  "library.listings",
  "library.management",
  "library.data-browser",
  "web.crawler",
  "web.requests",
  "web.drive-sync",
  "web.media-loader",
  "web.reverse-search",
  "web.entity-recon",
  "editor.hybrid",
  "developer.logs",
  "developer.metadata",
  ...STITCH_ROUTE_IDS,
  ...Object.keys(DL_ROUTE),
  "web.reverse-search",
  "web.entity-recon",
  "web.requests",
  "web.drive-sync",
  "web.media-loader",
  "manga.colorization",
  "manga.animation",
  "manga.puppeteering",
  "editor.hybrid",
  "developer.logs",
  "developer.metadata",
  ...Object.keys(DL_ROUTE),
  ...STITCH_ROUTE_IDS,
]);

export const CATALOG_VIEWS: Record<string, ComponentType<any>> = {
  "system.convert": ConvertPilot,
  "system.merge": MergeView,
  "system.similarity": SimilarityView,
  "system.extractor": ExtractorView,
  "system.wallpaper": WallpaperView,
  "library.listings": Listings,
  "library.search": ImageSearch,
  "library.management": LibraryManagement,
  "library.data-browser": DataBrowser,
  "library.scan": ScanMetadataView,
  "web.crawler": ImageCrawlerTab,
  "web.requests": WebRequestsView,
  "web.drive-sync": DriveSyncView,
  "web.media-loader": MediaLoaderView,
  "web.reverse-search": ReverseSearchView,
  "web.entity-recon": EntityReconView,
  "manga.colorization": MangaColorizationView,
  "manga.animation": MangaAnimationView,
  "manga.puppeteering": MangaPuppeteeringView,
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
  "developer.logs": LogDeskView,
  "developer.metadata": MetadataDeskView,
  ...STITCH_VIEWS,
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
  const hostClientProps = HOST_CLIENT_VIEWS.has(entry.id)
    ? { hostClient, client: hostClient }
    : {};
  const stitchRoute = (STITCH_ROUTE_IDS as readonly string[]).includes(entry.id);
  const routeProps = stitchRoute ? { route: entry.id } : {};
  const route = DL_ROUTE[entry.id];
  return (
    <View
      showModal={showModal}
      {...extra}
      {...hostClientProps}
      {...routeProps}
      {...(route ? { route } : {})}
    />
  );
  const route = (STITCH_ROUTE_IDS as readonly string[]).includes(entry.id)
    ? entry.id
    : DL_ROUTE[entry.id];
  return <View showModal={showModal} {...extra} {...hostClientProps} {...(route ? { route } : {})} />;
}
