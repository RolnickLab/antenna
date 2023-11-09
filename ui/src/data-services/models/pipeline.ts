import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'

export type ServerPipeline = any // TODO: Update this type

export class Pipeline {
  protected readonly _pipeline: ServerPipeline

  public constructor(pipeline: ServerPipeline) {
    this._pipeline = pipeline
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._pipeline.created_at),
    })
  }

  get id(): string {
    return `${this._pipeline.id}`
  }

  get name(): string {
    return this._pipeline.name
  }

  get updatedAt(): string | undefined {
    if (!this._pipeline.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._pipeline.updated_at),
    })
  }
}
