export type ServerDeployment = any // TODO: Update this type

export interface DeploymentFieldValues {
  device: string
  name: string
  latitude: number
  longitude: number
  path: string
  site: string
}

export class Deployment {
  private readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    this._deployment = deployment
  }

  get id(): string {
    return this._deployment.id ?? this._deployment.name // TODO: Update when BE is returning an ID
  }

  get latitude(): number {
    return 0 // TODO: Update when BE is returning latitude
  }

  get longitude(): number {
    return 0 // TODO: Update when BE is returning longitude
  }

  get name(): string {
    return this._deployment.name
  }

  get numDetections(): number {
    return this._deployment.num_detections
  }

  get numEvents(): number {
    return this._deployment.num_events
  }

  get numImages(): number {
    return this._deployment.num_source_images
  }

  get path(): string {
    return this._deployment.image_base_path
  }
}
