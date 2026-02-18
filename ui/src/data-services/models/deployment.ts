import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'
import { Entity } from './entity'
import { Job } from './job'

export type ServerDeployment = any // TODO: Update this type

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

  get canUpdate(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Update)
  }

  get currentJob(): Job | undefined {
    if (!this._jobs.length) {
      return
    }

    return this._jobs.sort((j1: Job, j2: Job) => {
      const date1 = new Date(j1.updatedAt as string)
      const date2 = new Date(j2.updatedAt as string)

      return date2.getTime() - date1.getTime()
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
