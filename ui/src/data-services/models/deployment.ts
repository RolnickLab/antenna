export type ServerDeployment = any // TODO: Update this type

const DUMMY_DATA = {
  location: { lat: 52.30767, lng: 5.04011 },
}

export class Deployment {
  private readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    this._deployment = deployment
  }

  get id(): string {
    return this._deployment.name // TODO: Update when BE is returning an ID
  }

  get location(): { lat: number; lng: number } {
    return DUMMY_DATA.location // TODO: Update when BE is returning a location
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
