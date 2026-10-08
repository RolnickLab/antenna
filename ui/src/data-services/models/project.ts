import { MarkerPosition } from 'components/map/types'
import { UserPermission } from 'utils/user/types'
import { Deployment, ServerDeployment } from './deployment'

export type ServerProject = any // TODO: Update this type

export class Project {
  protected readonly _project: ServerProject
  protected readonly _deployments: Deployment[] = []

  public constructor(project: ServerProject) {
    this._project = project
    this._deployments = (project.deployments ?? []).map(
      (deployment: ServerDeployment) => new Deployment(deployment)
    )
  }

  get canDelete(): boolean {
    return this._project.user_permissions.includes(UserPermission.Delete)
  }

  get location(): MarkerPosition | undefined {
    const { location } = this._project

    return location
      ? new MarkerPosition(location.latitude, location.longitude)
      : undefined
  }

  get createdAt(): Date | undefined {
    return this._project.created_at
      ? new Date(this._project.created_at)
      : undefined
  }

  get canUpdate(): boolean {
    return this._project.user_permissions.includes(UserPermission.Update)
  }

  get deployments(): Deployment[] {
    return this._deployments
  }

  get description(): string {
    return this._project.description
  }

  get featureFlags(): { [key: string]: boolean } {
    return this._project.feature_flags ?? {}
  }

  get id(): string {
    return `${this._project.id}`
  }

  get image(): string | undefined {
    return this._project.image ? `${this._project.image}` : undefined
  }

  get isDraft(): boolean {
    return this._project.draft
  }

  get lastCaptureDate(): Date | undefined {
    return this._project.last_capture_timestamp
      ? new Date(this._project.last_capture_timestamp)
      : undefined
  }

  get lastJobUpdateDate(): Date | undefined {
    return this._project.last_job_updated_at
      ? new Date(this._project.last_job_updated_at)
      : undefined
  }

  get lastOccurrenceUpdateDate(): Date | undefined {
    return this._project.last_occurrence_updated_at
      ? new Date(this._project.last_occurrence_updated_at)
      : undefined
  }

  get name(): string {
    return this._project.name
  }

  get numCaptures(): number | undefined {
    return this._project.captures_count
  }

  get numDeployments(): number | undefined {
    return this._project.deployments_count
  }

  get numMembers(): number | undefined {
    return this._project.members_count
  }

  get numOccurrences(): number | undefined {
    return this._project.occurrences_count
  }

  get numTaxa(): number | undefined {
    return this._project.taxa_observed_count
  }

  get updatedAt(): Date | undefined {
    return this._project.updated_at
      ? new Date(this._project.updated_at)
      : undefined
  }
}
