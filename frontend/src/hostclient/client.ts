import type {
  GetMonitorsResult,
  SetWallpaperParams,
  SetWallpaperResult,
  SlideshowConfigParams,
  SlideshowConfigResult,
  SlideshowToggleParams,
  SlideshowToggleResult,
} from "../../../contracts/generated/ts";
import type { ScanDirectoryParams, ScanDirectoryResult, SaveMetadataParams, SaveMetadataResult, SuggestTagsParams, SuggestTagsResult } from "../../../contracts/generated/ts";
import type { ExecuteParams, ExecuteResult, SequenceParams, SequenceResult } from "../../../contracts/generated/ts";
import type {
  ArapDeformParams as CsgArapDeformParams,
  ArapDeformPayload as CsgArapDeformPayload,
  ColorizeReferenceParams as CsgColorizeReferenceParams,
  ColorizeScribbleParams as CsgColorizeScribbleParams,
  ColorizeScribblePayload as CsgColorizePayload,
  PropagateSequenceParams as CsgPropagateSequenceParams,
  PropagateSequencePayload as CsgPropagateSequencePayload,
} from "../../../contracts/generated/ts";
import type { BrowseParams, BrowseResult, CatalogResult, MutateParams, MutateResult } from "../../../contracts/generated/ts";
import type {
  CrawlParams,
  CrawlResult,
  CrawlerSupportedParams,
  CrawlerSupportedResult,
  EditParams,
  EditResult,
  ExportDocumentParams,
  ExportDocumentResult,
  ListCapabilitiesParams,
  ListCapabilitiesResult,
  OpenDocumentParams,
  OpenDocumentResult,
} from "../../../contracts/generated/ts";
import type {
  BridgeResponse,
  CancelResult,
  ConvertBatchParams,
  ConvertBatchResult,
  CloudSubmitParams,
  CloudSubmitResult,
  EntityReconDescribeResult,
  EntityReconResolveParams,
  EntityReconResolveResult,
  ProvidersResult as CloudSetupProvidersResult,
  ConvertParams,
  ConvertResult,
  DescribeParams,
  DescribeResult,
  DifferenceParams,
  DifferenceResult,
  ConcatenateParams,
  ConcatenateResult,
  CompareParams,
  CompareResult,
  AuthStatusParams,
  AuthStatusResult,
  ProbeParams,
  ProbeResult,
  StitchStatusResult,
  PrefsDescribeResult,
  PrefsGetResult,
  PrefsSetParams,
  PrefsSetResult,
  LogsReadParams,
  LogsReadResult,
  MetadataDescribeParams,
  MetadataDescribeResult,
  DlInspectParams,
  DlInspectResult,
  DriveSyncPlanParams,
  DriveSyncPlanResult,
  MediaPlanParams,
  MediaPlanResult,
  FrameParams,
  FrameResult,
  GetManyParams,
  GetManyResult,
  ListImagesParams,
  ListImagesResult,
  ListGroupsResult,
  ListTagsResult,
  EnginesResult as ReverseEnginesResult,
  SearchParams as ReverseSearchParams,
  SearchResult as ReverseSearchResult,
  GetParams,
  GetResult,
  PrefillParams,
  PrefillResult,
  PreviewParams,
  PreviewResult,
  JobDetailParams,
  JobDetailResult,
  ListJobsParams,
  ListJobsResult,
  ResourcesResult,
  SpendResult,
  SummaryResult,
  TerminateResult,
  HandshakeResult,
  JobStatus,
  ListParams,
  ListResult,
  PingResult,
  SetManyParams,
  SetManyResult,
  SetParams,
  SetResult,
  SubmitParams,
  SubmitResult,
} from "../../../contracts/generated/ts";
import { BridgeAppError, BridgeTransportError, decodeBridgeResult } from "./errors";
import { buildBridgeRequest, type BridgeTransport } from "./transport";

const PROTOCOL_NAME = "image-toolkit-bridge";

export interface HostClientOptions {
  readonly clientName: string;
  readonly clientVersion: string;
  /** Total attempts for retryable transport failures, including the first. */
  readonly reconnectAttempts?: number;
  readonly reconnectDelayMs?: number;
}

export class HostClient {
  private readonly transport: BridgeTransport;
  private readonly options: Required<HostClientOptions>;
  private ready: Promise<HandshakeResult> | undefined;
  private nextId = 1;

  constructor(transport: BridgeTransport, options: HostClientOptions) {
    this.transport = transport;
    this.options = {
      reconnectAttempts: 2,
      reconnectDelayMs: 25,
      ...options,
    };
  }

  connect(): Promise<HandshakeResult> {
    this.ready ??= this.send<HandshakeResult>("system.handshake", {
      protocol: PROTOCOL_NAME,
      client: { name: this.options.clientName, version: this.options.clientVersion },
    }).then((result) => {
      this.assertCompatible(result);
      return result;
    });
    this.ready.catch(() => {
      this.ready = undefined;
    });
    return this.ready;
  }

  async ping(): Promise<PingResult> {
    await this.connect();
    return this.send<PingResult>("system.ping", {});
  }

  async submitJob(params: SubmitParams): Promise<SubmitResult> {
    await this.connect();
    return this.send<SubmitResult>("jobs.submit", params as unknown as Record<string, unknown>);
  }

  async cancelJob(jobId: string): Promise<CancelResult> {
    await this.connect();
    return this.send<CancelResult>("jobs.cancel", { job_id: jobId });
  }

  async jobStatus(jobId: string): Promise<JobStatus> {
    await this.connect();
    return this.send<JobStatus>("jobs.status", { job_id: jobId });
  }

  async listJobs(params: ListParams = {}): Promise<ListResult> {
    await this.connect();
    return this.send<ListResult>("jobs.list", params as unknown as Record<string, unknown>);
  }

  async entityReconDescribe(): Promise<EntityReconDescribeResult> {
    await this.connect();
    return this.send<EntityReconDescribeResult>("entity_recon.describe", {});
  }

  async entityReconResolve(params: EntityReconResolveParams): Promise<EntityReconResolveResult> {
    await this.connect();
    return this.send<EntityReconResolveResult>("entity_recon.resolve", params as unknown as Record<string, unknown>);
  }

  async csgColorizeScribble(params: CsgColorizeScribbleParams): Promise<CsgColorizePayload> {
    await this.connect();
    return this.send<CsgColorizePayload>("csg.colorize_scribble", params as unknown as Record<string, unknown>);
  }

  async csgColorizeReference(params: CsgColorizeReferenceParams): Promise<CsgColorizePayload> {
    await this.connect();
    return this.send<CsgColorizePayload>("csg.colorize_reference", params as unknown as Record<string, unknown>);
  }

  async csgArapDeform(params: CsgArapDeformParams): Promise<CsgArapDeformPayload> {
    await this.connect();
    return this.send<CsgArapDeformPayload>("csg.arap_deform", params as unknown as Record<string, unknown>);
  }

  async csgPropagateSequence(params: CsgPropagateSequenceParams): Promise<CsgPropagateSequencePayload> {
    await this.connect();
    return this.send<CsgPropagateSequencePayload>("csg.propagate_sequence", params as unknown as Record<string, unknown>);
  }

  async cloudSetupProviders(): Promise<CloudSetupProvidersResult> {
    await this.connect();
    return this.send<CloudSetupProvidersResult>("cloud_setup.providers", {});
  }

  async cloudJobsSummary(): Promise<SummaryResult> {
    await this.connect();
    return this.send<SummaryResult>("cloud_jobs.summary", {});
  }

  async cloudJobsPreview(params: PreviewParams): Promise<PreviewResult> {
    await this.connect();
    return this.send<PreviewResult>("cloud_jobs.preview", params as unknown as Record<string, unknown>);
  }

  async cloudJobsSubmit(params: CloudSubmitParams): Promise<CloudSubmitResult> {
    await this.connect();
    return this.send<CloudSubmitResult>("cloud_jobs.submit", params as unknown as Record<string, unknown>);
  }

  async cloudJobsList(params: ListJobsParams = {}): Promise<ListJobsResult> {
    await this.connect();
    return this.send<ListJobsResult>("cloud_jobs.list", params as unknown as Record<string, unknown>);
  }

  async cloudJobsDetail(params: JobDetailParams): Promise<JobDetailResult> {
    await this.connect();
    return this.send<JobDetailResult>("cloud_jobs.detail", params as unknown as Record<string, unknown>);
  }

  async cloudJobsResources(): Promise<ResourcesResult> {
    await this.connect();
    return this.send<ResourcesResult>("cloud_jobs.resources", {});
  }

  async cloudJobsSpend(): Promise<SpendResult> {
    await this.connect();
    return this.send<SpendResult>("cloud_jobs.spend", {});
  }

  async cloudJobsTerminate(resourceId: string): Promise<TerminateResult> {
    await this.connect();
    return this.send<TerminateResult>("cloud_jobs.terminate", { resource_id: resourceId });
  }

  async libraryPreviewDescribe(params: DescribeParams): Promise<DescribeResult> {
    await this.connect();
    return this.send<DescribeResult>("library_preview.describe", params as unknown as Record<string, unknown>);
  }

  async libraryPreviewFrame(params: FrameParams): Promise<FrameResult> {
    await this.connect();
    return this.send<FrameResult>("library_preview.frame", params as unknown as Record<string, unknown>);
  }

  async libraryPreviewDifference(params: DifferenceParams): Promise<DifferenceResult> {
    await this.connect();
    return this.send<DifferenceResult>("library_preview.difference", params as unknown as Record<string, unknown>);
  }

  async mergeConcatenate(params: ConcatenateParams): Promise<ConcatenateResult> {
    await this.connect();
    return this.send<ConcatenateResult>("merge.concatenate", params as unknown as Record<string, unknown>);
  }

  async similarityCompare(params: CompareParams): Promise<CompareResult> {
    await this.connect();
    return this.send<CompareResult>("similarity.compare", params as unknown as Record<string, unknown>);
  }

  async extractorProbe(params: ProbeParams): Promise<ProbeResult> {
    await this.connect();
    return this.send<ProbeResult>("extractor.probe", params as unknown as Record<string, unknown>);
  }

  async stitchStatus(route: string): Promise<StitchStatusResult> {
    await this.connect();
    return this.send<StitchStatusResult>("stitch.status", { route });
  }

  async logsRead(params: LogsReadParams): Promise<LogsReadResult> {
    await this.connect();
    return this.send<LogsReadResult>("logs.read", params as unknown as Record<string, unknown>);
  }

  async metadataDescribe(params: MetadataDescribeParams): Promise<MetadataDescribeResult> {
    await this.connect();
    return this.send<MetadataDescribeResult>("metadata.describe", params as unknown as Record<string, unknown>);
  }

  async dlInspect(params: DlInspectParams): Promise<DlInspectResult> {
    await this.connect();
    return this.send<DlInspectResult>("dl.inspect", params as unknown as Record<string, unknown>);
  }

  async driveSyncPlan(params: DriveSyncPlanParams): Promise<DriveSyncPlanResult> {
    await this.connect();
    return this.send<DriveSyncPlanResult>("drive_sync.plan", params as unknown as Record<string, unknown>);
  }

  async mediaLoaderPlan(params: MediaPlanParams): Promise<MediaPlanResult> {
    await this.connect();
    return this.send<MediaPlanResult>("media_loader.plan", params as unknown as Record<string, unknown>);
  }

  async authStatus(params: AuthStatusParams): Promise<AuthStatusResult> {
    await this.connect();
    return this.send<AuthStatusResult>("auth.status", params as unknown as Record<string, unknown>);
  }

  async cloudOfferPrefill(params: PrefillParams): Promise<PrefillResult> {
    await this.connect();
    return this.send<PrefillResult>("cloud_offer.prefill", params as unknown as Record<string, unknown>);
  }

  async convert(params: ConvertParams): Promise<ConvertResult> {
    await this.connect();
    return this.send<ConvertResult>("convert.convert", params as unknown as Record<string, unknown>);
  }

  async convertBatch(params: ConvertBatchParams): Promise<ConvertBatchResult> {
    await this.connect();
    return this.send<ConvertBatchResult>(
      "convert.convert_batch",
      params as unknown as Record<string, unknown>,
    );
  }

  /** Bridge settings value: any JSON the settings service accepts. */
  async getSetting(params: GetParams): Promise<GetResult> {
    await this.connect();
    return this.send<GetResult>("settings.get", params as unknown as Record<string, unknown>);
  }

  async setSetting(params: SetParams): Promise<SetResult> {
    await this.connect();
    return this.send<SetResult>("settings.set", params as unknown as Record<string, unknown>);
  }

  async getSettings(params: GetManyParams): Promise<GetManyResult> {
    await this.connect();
    return this.send<GetManyResult>("settings.get_many", params as unknown as Record<string, unknown>);
  }

  async setSettings(params: SetManyParams): Promise<SetManyResult> {
    await this.connect();
    return this.send<SetManyResult>("settings.set_many", params as unknown as Record<string, unknown>);
  }

  /** Settings window sections. Does not open the vault or change a password. */
  async prefsDescribe(account: string): Promise<PrefsDescribeResult> {
    await this.connect();
    return this.send<PrefsDescribeResult>("prefs.describe", { account });
  }

  /** Read the settings window. Does not open the vault or the log directory. */
  async prefsGet(account: string): Promise<PrefsGetResult> {
    await this.connect();
    return this.send<PrefsGetResult>("prefs.get", { account });
  }

  /** Write profiles, gallery, logging, and one shortcut override. */
  async prefsSet(params: PrefsSetParams): Promise<PrefsSetResult> {
    await this.connect();
    return this.send<PrefsSetResult>("prefs.set", params as unknown as Record<string, unknown>);
  }

  async listLibraryImages(params: ListImagesParams = {}): Promise<ListImagesResult> {
    await this.connect();
    return this.send<ListImagesResult>("library.list_images", params as unknown as Record<string, unknown>);
  }

  async listLibraryTags(): Promise<ListTagsResult> {
    await this.connect();
    return this.send<ListTagsResult>("library.list_tags", {});
  }

  async listLibraryGroups(): Promise<ListGroupsResult> {
    await this.connect();
    return this.send<ListGroupsResult>("library.list_groups", {});
  }

  async reverseSearchEngines(): Promise<ReverseEnginesResult> {
    await this.connect();
    return this.send<ReverseEnginesResult>("reverse_search.engines", {});
  }

  async reverseSearch(params: ReverseSearchParams): Promise<ReverseSearchResult> {
    await this.connect();
    return this.send<ReverseSearchResult>("reverse_search.search", params as unknown as Record<string, unknown>);
  }

  async libraryAdminCatalog(): Promise<CatalogResult> {
    await this.connect();
    return this.send<CatalogResult>("library_admin.catalog", {});
  }

  async libraryAdminMutate(params: MutateParams): Promise<MutateResult> {
    await this.connect();
    return this.send<MutateResult>(
      "library_admin.mutate",
      params as unknown as Record<string, unknown>,
    );
  }

  async libraryAdminBrowse(params: BrowseParams): Promise<BrowseResult> {
    await this.connect();
    return this.send<BrowseResult>(
      "library_admin.browse",
      params as unknown as Record<string, unknown>,
    );
  }

  async scanDirectory(params: ScanDirectoryParams): Promise<ScanDirectoryResult> {
    await this.connect();
    return this.send<ScanDirectoryResult>("scan.directory", params as unknown as Record<string, unknown>);
  }

  async scanSaveMetadata(params: SaveMetadataParams): Promise<SaveMetadataResult> {
    await this.connect();
    return this.send<SaveMetadataResult>("scan.save_metadata", params as unknown as Record<string, unknown>);
  }

  async scanSuggestTags(params: SuggestTagsParams): Promise<SuggestTagsResult> {
    await this.connect();
    return this.send<SuggestTagsResult>("scan.suggest_tags", params as unknown as Record<string, unknown>);
  }

  async wallpaperGetMonitors(): Promise<GetMonitorsResult> {
    await this.connect();
    return this.send<GetMonitorsResult>("wallpaper.get_monitors", {});
  }

  async wallpaperSet(params: SetWallpaperParams): Promise<SetWallpaperResult> {
    await this.connect();
    return this.send<SetWallpaperResult>("wallpaper.set", params as unknown as Record<string, unknown>);
  }

  async wallpaperSlideshowConfig(params: SlideshowConfigParams): Promise<SlideshowConfigResult> {
    await this.connect();
    return this.send<SlideshowConfigResult>("wallpaper.slideshow_config", params as unknown as Record<string, unknown>);
  }

  async wallpaperSlideshowToggle(params: SlideshowToggleParams): Promise<SlideshowToggleResult> {
    await this.connect();
    return this.send<SlideshowToggleResult>("wallpaper.slideshow_toggle", params as unknown as Record<string, unknown>);
  }

  async crawlerCrawl(params: CrawlParams): Promise<CrawlResult> {
    await this.connect();
    return this.send<CrawlResult>("crawler.crawl", params as unknown as Record<string, unknown>);
  }

  async crawlerListSupported(params?: CrawlerSupportedParams): Promise<CrawlerSupportedResult> {
    await this.connect();
    return this.send<CrawlerSupportedResult>("crawler.list_supported", (params ?? {}) as Record<string, unknown>);
  }

  async webreqExecute(params: ExecuteParams): Promise<ExecuteResult> {
    await this.connect();
    return this.send<ExecuteResult>("webreq.execute", params as unknown as Record<string, unknown>);
  }

  async webreqSequence(params: SequenceParams): Promise<SequenceResult> {
    await this.connect();
    return this.send<SequenceResult>("webreq.sequence", params as unknown as Record<string, unknown>);
  }

  async hieOpenDocument(params: OpenDocumentParams): Promise<OpenDocumentResult> {
    await this.connect();
    return this.send<OpenDocumentResult>("hie.open_document", params as unknown as Record<string, unknown>);
  }

  async hieExecuteEdit(params: EditParams): Promise<EditResult> {
    await this.connect();
    return this.send<EditResult>("hie.execute_edit", params as unknown as Record<string, unknown>);
  }

  async hieExportDocument(params: ExportDocumentParams): Promise<ExportDocumentResult> {
    await this.connect();
    return this.send<ExportDocumentResult>("hie.export_document", params as unknown as Record<string, unknown>);
  }

  async hieListCapabilities(params?: ListCapabilitiesParams): Promise<ListCapabilitiesResult> {
    await this.connect();
    return this.send<ListCapabilitiesResult>("hie.list_capabilities", (params ?? {}) as Record<string, unknown>);
  }

  onEvent(listener: Parameters<NonNullable<BridgeTransport["onEvent"]>>[0]): () => void {
    if (!this.transport.onEvent) {
      throw new BridgeTransportError("this transport has no event stream");
    }
    return this.transport.onEvent(listener);
  }

  async close(): Promise<void> {
    await this.transport.close?.();
    this.ready = undefined;
  }

  private async send<T>(method: string, params: Record<string, unknown>): Promise<T> {
    const attempts = Math.max(1, this.options.reconnectAttempts);
    let lastError: unknown;
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      const request = buildBridgeRequest(method, this.allocateId(), params);
      try {
        const response: BridgeResponse = await this.transport.request(request);
        return decodeBridgeResult<T>(response, request.id);
      } catch (error) {
        lastError = error;
        const retryable =
          error instanceof BridgeTransportError ||
          (error instanceof BridgeAppError && error.retryable && method !== "jobs.submit");
        if (!retryable || attempt === attempts) {
          throw error;
        }
        await this.transport.reset?.();
        await delay(this.options.reconnectDelayMs * attempt);
      }
    }
    throw lastError;
  }

  private allocateId(): string {
    const id = `host-${this.nextId}`;
    this.nextId += 1;
    return id;
  }

  private assertCompatible(result: HandshakeResult): void {
    if (result.protocol !== PROTOCOL_NAME) {
      throw new BridgeAppError({
        code: "bridge.protocol_mismatch",
        retryable: false,
        message_key: "bridge.errors.protocol_mismatch",
        details: { expected: PROTOCOL_NAME, got: result.protocol },
      });
    }
    const { min, max } = result.compatibility;
    if (!versionInRange(this.options.clientVersion, min, max)) {
      throw new BridgeAppError({
        code: "bridge.version_mismatch",
        retryable: false,
        message_key: "bridge.errors.version_mismatch",
        details: { client: this.options.clientVersion, min, max },
      });
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseVersion(version: string): [number, number, number] {
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(version);
  if (!match) {
    throw new BridgeAppError({
      code: "bridge.version_mismatch",
      retryable: false,
      message_key: "bridge.errors.version_mismatch",
      details: { client: version },
    });
  }
  return [Number(match[1]), Number(match[2] ?? 0), Number(match[3] ?? 0)];
}

function compareVersion(left: string, right: string): number {
  const a = parseVersion(left);
  const b = parseVersion(right);
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) {
      return a[index] - b[index];
    }
  }
  return 0;
}

function versionInRange(version: string, minimum: string, maximum: string): boolean {
  return compareVersion(version, minimum) >= 0 && compareVersion(version, maximum) <= 0;
}
