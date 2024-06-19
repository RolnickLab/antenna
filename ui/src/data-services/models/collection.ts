export type ServerCollection = any // TODO: Update this type
import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { Entity } from './entity'

export class Collection extends Entity {
  public constructor(entity: ServerCollection) {
    super(entity)
  }

  get method(): string {
    return this._data.method
  }

  get kwargs(): object {
    return this._data.kwargs || {}
  }

  get methodNameDisplay(): string {
    return snakeCaseToSentenceCase(this._data.method)
  }

  get methodDetailsDisplay(): string[] {
    return Object.entries(this._data.kwargs).map(
      ([key, value]) => `${snakeCaseToSentenceCase(key)} ${value}`
    )
  }

  get name(): string {
    return this._data.name
  }

  get numImages(): number | undefined {
    return this._data.source_image_count
  }
}
