import { Deployment, ServerDeployment } from './deployment'
import { Entity } from './entity'
import { Storage } from './storage'

export type ServerDeploymentDetails = ServerDeployment & any // TODO: Update this type

export interface DeploymentFieldValues {
  dataSourceId?: string
  description: string
  name: string
  siteId?: string
  deviceId?: string
  latitude: number
  longitude: number
  projectId?: string
}

export class DeploymentDetails extends Deployment {
  private readonly _exampleCaptures: { id: string; src: string }[] = []

  public constructor(deployment: ServerDeploymentDetails) {
    super(deployment)

    if (deployment.example_captures?.length) {
      this._exampleCaptures = deployment.example_captures?.map(
        (capture: any) => ({
          id: `${capture.id}`,
          src: capture.url,
        })
      )
    }
  }

  get device(): Entity | undefined {
    if (this._deployment.device) {
      return new Entity(this._deployment.device)
    }
  }

  get description(): string {
    return this._deployment.description
  }

  get exampleCaptures(): { id: string; src: string }[] {
    return this._exampleCaptures
  }

  get dataSource(): Storage | undefined {
    if (this._deployment.data_source) {
      return new Storage(this._deployment.data_source)
    }
  }

  get site(): Entity | undefined {
    if (this._deployment.research_site) {
      return new Entity(this._deployment.research_site)
    }
  }
}
