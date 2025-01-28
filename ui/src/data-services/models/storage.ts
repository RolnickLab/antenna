import { Entity } from './entity'

export type ServerStorage = any // TODO: Update this type

export class StorageSource extends Entity {
  public constructor(entity: StorageSource) {
    super(entity)
  }

  get accessKey(): string {
    return this._data.access_key
  }

  get bucket(): string {
    return this._data.bucket
  }

  get lastChecked(): string {
    return this._data.last_checked
  }

  get totalFiles(): number {
    return this._data.total_files_indexed
  }

  get totalSize(): number {
    return this._data.total_size_indexed
  }

  get totalSizeDisplay(): string {
    return this._data.total_size_indexed_display
  }

  get deploymentsCount(): number {
    return this._data.deployments_count
  }

  get endpointUrl(): string {
    return this._data.endpoint_url
  }

  get publicBaseUrl(): string {
    return this._data.public_base_url
  }
}
