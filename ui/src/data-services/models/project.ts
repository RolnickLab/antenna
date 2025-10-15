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

  get name(): string {
    return this._project.name
  }
}
