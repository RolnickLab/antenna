import { UserPermission } from 'utils/user/types'

export type ServerDeployment = any // TODO: Update this type

export class Deployment {
  protected readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    this._deployment = deployment
  }

  get canCreate(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Create)
  }

  get canUpdate(): boolean {
    return this._deployment.user_permissions.includes(UserPermission.Update)
  }

  get id(): string {
    return `${this._deployment.id}`
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

  get firstDate(): number {
    return this._deployment.first_date
  }

  get lastDate(): number {
    return this._deployment.last_date
  }
}
