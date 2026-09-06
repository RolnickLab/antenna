import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'
import { Entity } from './entity'
import { Job } from './job'

export type ServerDeployment = any // TODO: Update this type

/**
 * What a connected device last reported about itself.
 *
 * The two identity fields are the only ones every device answers. Everything past them
 * depends on what that particular device can measure, so the type stays open and the UI
 * lists whatever arrived rather than a fixed set of rows.
 */
export interface StationStatus {
  device_id: string
  software_version: string
  [key: string]: unknown
}

export const STATION_STATUS_IDENTITY_KEYS = ['device_id', 'software_version']

export class Deployment extends Entity {
  private readonly _jobs: Job[] = []

  protected readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    super(deployment)

    this._deployment = deployment

    if (this._deployment.jobs) {
      this._jobs = this._deployment.jobs.map((job: any) => new Job(job))
    }
  }

  get canDelete(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Delete)
  }

  get canSync(): boolean {
    // Granted to ML data managers, project managers, and superusers. Superusers
    // receive `sync` here too (guardian returns every project permission for
    // them), so this getter alone is the sync gate.
    return this._deployment.user_permissions.includes(UserPermission.Sync)
  }

  get canUpdate(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Update)
  }

  get dataSourceConnected(): boolean {
    return this._deployment.data_source_connected ?? false
  }

  get currentJob(): Job | undefined {
    if (!this._jobs.length) {
      return
    }

    return this._jobs.sort((j1: Job, j2: Job) => {
      const time1 = j1.updatedAt?.getTime() ?? 0
      const time2 = j2.updatedAt?.getTime() ?? 0

      return time2 - time1
    })[0]
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

  get numEvents(): number {
    return this._deployment.events_count
  }

  get numImages(): number {
    return this._deployment.captures_count
  }

  get numJobs(): number | undefined {
    return this._deployment.jobs?.length
  }

  get numOccurrences(): number {
    return this._deployment.occurrences_count
  }

  get numTaxa(): number {
    return this._deployment.taxa_count
  }

  get device(): Entity | undefined {
    if (this._deployment.device) {
      return new Entity(this._deployment.device)
    }
  }

  get researchSite(): Entity | undefined {
    if (this._deployment.research_site) {
      return new Entity(this._deployment.research_site)
    }
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

  /** The station's own most recent report, if it has ever checked in. */
  get lastStatus(): StationStatus | undefined {
    return this._deployment.last_status ?? undefined
  }

  get lastStatusAt(): Date | undefined {
    return this._deployment.last_status_at
      ? new Date(this._deployment.last_status_at)
      : undefined
  }

  get lastSeenLabel(): string | undefined {
    const lastStatusAt = this.lastStatusAt

    return lastStatusAt
      ? getFormatedDateTimeString({ date: lastStatusAt })
      : undefined
  }

  /**
   * Everything the device published beyond its identity, in the order it sent it.
   *
   * Devices differ in what they can measure, so this is a list to render rather than a
   * set of known fields to read: a phone reports its battery, a mains-powered box
   * reports that it is on mains, and neither is shown rows it never answered.
   */
  get reportedStatusEntries(): [string, unknown][] {
    const status = this.lastStatus

    if (!status) {
      return []
    }

    return Object.entries(status).filter(
      ([key]) => !STATION_STATUS_IDENTITY_KEYS.includes(key)
    )
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
