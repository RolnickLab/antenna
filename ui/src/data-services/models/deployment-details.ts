export type ServerDeploymentDetails = any // TODO: Update this type

export interface DeploymentFieldValues {
  device: string
  name: string
  latitude: number
  longitude: number
  path: string
  site: string
}

export class DeploymentDetails {
  private readonly _deployment: ServerDeploymentDetails
  private readonly _exampleCaptures: { src: string }[] = []

  public constructor(deployment: ServerDeploymentDetails) {
    this._deployment = deployment

    if (deployment.example_captures?.length) {
      this._exampleCaptures = deployment.example_captures?.map(
        (capture: any) => ({
          src: capture.path,
        })
      )
    }
  }

  get exampleCaptures(): { src: string }[] {
    return this._exampleCaptures
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

  get numDetections(): number {
    return this._deployment.detections_count
  }

  get numEvents(): number {
    return this._deployment.events_count
  }

  get numImages(): number {
    return this._deployment.captures_count
  }

  get path(): string {
    return this._deployment.data_source
  }
}
