import { Entity } from './entity'
import { Pipeline, ServerPipeline } from './pipeline'

export type ServerProcessingService = any // TODO: Update this type

export const SERVER_PROCESSING_SERVICE_STATUS_CODES = [
  'OFFLINE',
  'ONLINE',
  'UNKNOWN',
] as const

export type ServerProcessingServiceStatusCode =
  (typeof SERVER_PROCESSING_SERVICE_STATUS_CODES)[number]

export enum ProcessingServiceStatusType {
  Success,
  Error,
  Unknown,
}

export class ProcessingService extends Entity {
  protected readonly _processingService: ServerProcessingService
  protected readonly _pipelines: Pipeline[] = []

  public constructor(processingService: ServerProcessingService) {
    super(processingService)
    this._processingService = processingService

    if (processingService.pipelines) {
      this._pipelines = processingService.pipelines.map(
        (pipeline: ServerPipeline) => new Pipeline(pipeline)
      )
    }
  }

  get pipelines(): Pipeline[] {
    return this._pipelines
  }

  get id(): string {
    return `${this._processingService.id}`
  }

  get name(): string {
    return `${this._processingService.name}`
  }

  get endpointUrl(): string | undefined {
    const url = this._processingService.endpoint_url
    return url && url.trim().length > 0 ? url : undefined
  }

  get isAsync(): boolean {
    return this._processingService.is_async ?? false
  }

  get description(): string {
    return `${this._processingService.description}`
  }

  get lastSeen(): Date | undefined {
    if (!this._processingService.last_seen) {
      return undefined
    }
    return new Date(this._processingService.last_seen)
  }

  get lastSeenLive(): boolean {
    return this._processingService.last_seen_live ?? false
  }

  get numPiplinesAdded(): number {
    return this._pipelines.length
  }

  get status(): {
    code: ServerProcessingServiceStatusCode
    label: string
    type: ProcessingServiceStatusType
    color: string
  } {
    if (this.isAsync) {
      // Async services derive status from heartbeat
      const status_code = this.lastSeenLive ? 'ONLINE' : 'UNKNOWN'
      return ProcessingService.getStatusInfo(status_code)
    }
    const status_code = this.lastSeenLive ? 'ONLINE' : 'OFFLINE'
    return ProcessingService.getStatusInfo(status_code)
  }

  static getStatusInfo(code: ServerProcessingServiceStatusCode) {
    const label =
      String(code).charAt(0).toUpperCase() + String(code).toLowerCase().slice(1)

    const type = {
      OFFLINE: ProcessingServiceStatusType.Error,
      ONLINE: ProcessingServiceStatusType.Success,
      UNKNOWN: ProcessingServiceStatusType.Unknown,
    }[code]

    const color = {
      [ProcessingServiceStatusType.Error]: '#ef4444', // color-destructive-500,
      [ProcessingServiceStatusType.Success]: '#09af8a', // color-success-500
      [ProcessingServiceStatusType.Unknown]: '#9ca3af', // gray-400
    }[type]

    return {
      code,
      label,
      type,
      color,
    }
  }
}
