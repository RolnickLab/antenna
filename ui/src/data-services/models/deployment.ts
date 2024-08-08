import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'

export type ServerDeployment = any // TODO: Update this type

export class Deployment {
  protected readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    this._deployment = deployment
  }

  get createdAt(): Date | undefined {
    return this._deployment.created_at
      ? new Date(this._deployment.created_at)
      : undefined
  }

  get canDelete(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Delete)
  }

  get canUpdate(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Update)
  }

  get id(): string {
    return `${this._deployment.id}`
  }

  get image(): string | undefined {
    return this._deployment.image ? `${this._deployment.image}` : undefined
  }

  get latitude(): number {
    return this._deployment.latitude
  }

  get longitude(): number {
    return this._deployment.longitude
  }

  get name(): string {
    return this._deployment.name
  }

  get numEvents(): number {
    return this._deployment.events_count
  }

  get numImages(): number {
    return this._deployment.captures_count
  }

  get numOccurrences(): number {
    return this._deployment.occurrences_count
  }

  get numSpecies(): number {
    return this._deployment.taxa_count
  }

  get firstDateLabel(): string | undefined {
    return this.numImages
      ? getFormatedDateString({
          date: new Date(this._deployment.first_date),
        })
      : undefined
  }

  get lastDateLabel(): string | undefined {
    return this.numImages
      ? getFormatedDateString({ date: new Date(this._deployment.last_date) })
      : undefined
  }

  get dataSourceDetails(): {
    lastChecked?: string
    totalFiles?: number
    totalSize?: number
    totalSizeDisplay?: string
    uri?: string
  } {
    return {
      lastChecked: this._deployment.data_source_last_checked
        ? getFormatedDateTimeString({
            date: new Date(this._deployment.data_source_last_checked),
          })
        : undefined,
      totalFiles: this._deployment.data_source_total_files,
      totalSize: this._deployment.data_source_total_size,
      totalSizeDisplay: this._deployment.data_source_total_size_display,
      uri: this._deployment.data_source_uri,
    }
  }
}
