import { Deployment, ServerDeployment } from './deployment'
import { Entity } from './entity'
import { StorageSource } from './storage'

export type ServerDeploymentDetails = ServerDeployment & any // TODO: Update this type

export type ServerNestedCapture = {
  id: number
  url: string
}

export interface DeploymentFieldValues {
  dataSourceId?: string
  dataSourceSubdir?: string | null
  dataSourceRegex?: string | null
  description: string
  deviceId?: string
  name: string
  image?: File | null
  latitude: number
  longitude: number
  projectId?: string
  siteId?: string
}

export class DeploymentDetails extends Deployment {
  private readonly _exampleCaptures: { id: string; src: string }[] = []
  private readonly _manuallyUploadedCaptures: { id: string; src: string }[] = []

  public constructor(deployment: ServerDeploymentDetails) {
    super(deployment)

    if (deployment.example_captures?.length) {
      this._exampleCaptures = deployment.example_captures?.map(
        (capture: ServerNestedCapture) => ({
          id: `${capture.id}`,
          src: capture.url,
        })
      )
    }

    if (deployment.manually_uploaded_captures?.length) {
      this._manuallyUploadedCaptures =
        deployment.manually_uploaded_captures?.map(
          (capture: ServerNestedCapture) => ({
            id: `${capture.id}`,
            src: capture.url,
          })
        )
    }
  }

  get description(): string {
    return this._deployment.description
  }

  get exampleCaptures(): { id: string; src: string }[] {
    return this._exampleCaptures
  }

  get manuallyUploadedCaptures(): { id: string; src: string }[] {
    return this._manuallyUploadedCaptures
  }

  get dataSource(): StorageSource | undefined {
    if (this._deployment.data_source?.id) {
      return new StorageSource(this._deployment.data_source)
    }
  }

  get dataSourceSubdir(): string | null {
    return this._deployment.data_source_subdir
  }

  get dataSourceRegex(): string | null {
    return this._deployment.data_source_regex
  }

  get site(): Entity | undefined {
    if (this._deployment.research_site) {
      return new Entity(this._deployment.research_site)
    }
  }
}
