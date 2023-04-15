export type ServerDeployment = any // TODO: Update this type

export class Deployment {
  private readonly _deployment: ServerDeployment

  public constructor(deployment: ServerDeployment) {
    this._deployment = deployment
  }

  get id(): string {
    return `${this._deployment.id}`
  }

  get name(): string {
    return this._deployment.name
  }

  get numDetections(): number {
    return this._deployment.num_detections
  }

  get numEvents(): number {
    return this._deployment.num_detections
  }

  get numImages(): number {
    return this._deployment.num_source_images
  }
}
