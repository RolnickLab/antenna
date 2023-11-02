export type ServerCollection = any // TODO: Update this type
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'

export class Collection {
  protected readonly _collection: ServerCollection

  public constructor(collection: ServerCollection) {
    this._collection = collection
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._collection.created_at),
    })
  }

  get id(): string {
    return `${this._collection.id}`
  }

  get method(): string {
    return snakeCaseToSentenceCase(this._collection.method)
  }

  get methodDetails(): string[] {
    return Object.entries(this._collection.kwargs).map(
      ([key, value]) => `${snakeCaseToSentenceCase(key)} ${value}`
    )
  }

  get name(): string {
    return this._collection.name
  }

  get numImages(): number | undefined {
    return this._collection.source_image_count
  }

  get updatedAt(): string | undefined {
    if (!this._collection.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._collection.updated_at),
    })
  }
}
