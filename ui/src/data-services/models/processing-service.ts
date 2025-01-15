import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Entity } from './entity'
import { Pipeline, ServerPipeline } from './pipeline'

export type ServerProcessingService = any // TODO: Update this type

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

  get slug(): string {
    return `${this._processingService.slug}`
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

  get num_piplines_added(): number {
    return this._pipelines.length
  }
}
