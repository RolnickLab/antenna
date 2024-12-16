import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Pipeline, ServerPipeline } from './pipeline'
import { Entity } from './entity'

export type ServerBackend = any // TODO: Update this type

export class Backend extends Entity {
  protected readonly _backend: ServerBackend
  protected readonly _pipelines: Pipeline[] = []

  public constructor(backend: ServerBackend) {
    super(backend)
    this._backend = backend

    if (backend.pipelines) {
      this._pipelines = backend.pipelines.map(
        (pipeline: ServerPipeline) => new Pipeline(pipeline)
      )
    }
  }

  get pipelines(): Pipeline[] {
    return this._pipelines
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._backend.created_at),
    })
  }

  get id(): string {
    return `${this._backend.id}`
  }

  get endpointUrl(): string {
    return `${this._backend.endpoint_url}`
  }

  get updatedAt(): string | undefined {
    if (!this._backend.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._backend.updated_at),
    })
  }

  get lastChecked(): string | undefined {
    if (!this._backend.last_checked) {
        return undefined
      }
  
      return getFormatedDateTimeString({
        date: new Date(this._backend.last_checked),
      })
  }
}
