import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Entity } from './entity'
import { Pipeline, ServerPipeline } from './pipeline'

export type ServerProcessingService = any // TODO: Update this type

export const SERVER_PROCESSING_SERVICE_STATUS_CODES = [
  'OFFLINE',
  'ONLINE',
] as const

export type ServerProcessingServiceStatusCode =
  (typeof SERVER_PROCESSING_SERVICE_STATUS_CODES)[number]

export enum ProcessingServiceStatusType {
  Success,
  Error,
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

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._processingService.created_at),
    })
  }

  get id(): string {
    return `${this._processingService.id}`
  }

  get name(): string {
    return `${this._processingService.name}`
  }

  get endpointUrl(): string {
    return `${this._processingService.endpoint_url}`
  }

  get description(): string {
    return `${this._processingService.description}`
  }

  get updatedAt(): string | undefined {
    if (!this._processingService.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._processingService.updated_at),
    })
  }

  get lastChecked(): string | undefined {
    if (!this._processingService.last_checked) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._processingService.last_checked),
    })
  }

  get lastCheckedLive(): boolean {
    return this._processingService.last_checked_live
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
    const status_code = this.lastCheckedLive ? 'ONLINE' : 'OFFLINE'
    return ProcessingService.getStatusInfo(status_code)
  }

  static getStatusInfo(code: ServerProcessingServiceStatusCode) {
    const label =
      String(code).charAt(0).toUpperCase() + String(code).toLowerCase().slice(1)

    const type = {
      OFFLINE: ProcessingServiceStatusType.Error,
      ONLINE: ProcessingServiceStatusType.Success,
    }[code]

    const color = {
      [ProcessingServiceStatusType.Error]: '#ef4444', // color-destructive-500,
      [ProcessingServiceStatusType.Success]: '#09af8a', // color-success-500
    }[type]

    return {
      code,
      label,
      type,
      color,
    }
  }
}
