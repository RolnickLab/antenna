import { Deployment, ServerDeployment } from './deployment'

export type ServerDeploymentDetails = ServerDeployment & any // TODO: Update this type

export interface DeploymentFieldValues {
  description: string
  name: string
  latitude: number
  longitude: number
  path: string
}

export class DeploymentDetails extends Deployment {
  private readonly _exampleCaptures: { src: string }[] = []

  public constructor(deployment: ServerDeploymentDetails) {
    super(deployment)

    if (deployment.example_captures?.length) {
      this._exampleCaptures = deployment.example_captures?.map(
        (capture: any) => ({
          src: capture.url,
        })
      )
    }
  }

  get description(): string {
    return this._deployment.description
  }

  get exampleCaptures(): { src: string }[] {
    return this._exampleCaptures
  }

  get path(): string {
    return this._deployment.data_source
  }
}
