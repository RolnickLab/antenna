import { Entity } from './entity'

export type ServerStorage = any // TODO: Update this type

export class Storage extends Entity {
  public constructor(entity: Storage) {
    super(entity)
  }

  get bucket(): string {
    return this._data.bucket
  }

  get endpointUrl(): string {
    return this._data.endpoint_url
  }

  get publicBaseUrl(): string {
    return this._data.public_base_url
  }
}
