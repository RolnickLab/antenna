import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Algorithm, ServerAlgorithm } from './algorithm'

export type ServerPipeline = any // TODO: Update this type

export class Pipeline {
  protected readonly _pipeline: ServerPipeline
  protected readonly _algorithms: Algorithm[] = []

  public constructor(pipeline: ServerPipeline) {
    this._pipeline = pipeline

    if (pipeline.algorithms) {
      this._algorithms = pipeline.algorithms.map(
        (algorithm: ServerAlgorithm) => new Algorithm(algorithm)
      )
    }
  }

  get algorithms(): Algorithm[] {
    return this._algorithms
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._pipeline.created_at),
    })
  }

  get description(): string {
    return this._pipeline.description
  }

  get id(): string {
    return `${this._pipeline.id}`
  }

  get slug(): string {
    return `${this._pipeline.slug}`
  }

  get name(): string {
    return this._pipeline.name
  }

  get stages(): {
    fields: { key: string; label: string; value?: string | number }[]
    name: string
    key: string
  }[] {
    const stages = this._pipeline.stages ?? []

    return stages.map((stage: any) => {
      const fields: { key: string; label: string; value?: string | number }[] =
        stage.params.map((param: any) => ({
          key: param.key,
          label: param.name,
          value: param.value,
        }))

      return {
        fields,
        key: stage.key,
        name: stage.name,
      }
    })
  }

  get versionLabel(): string {
    return this._pipeline.version_name?.length
      ? `${this._pipeline.version} "${this._pipeline.version_name?.length}"`
      : `${this._pipeline.version}`
  }

  get updatedAt(): string | undefined {
    if (!this._pipeline.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._pipeline.updated_at),
    })
  }

  get processingServicesOnline(): string {
    const processingServices = this._pipeline.processing_services
    let total_online = 0
    for (const processingService of processingServices) {
      if (processingService.last_checked_live) {
        total_online += 1
      }
    }

    return total_online + '/' + processingServices.length
  }

  get processingServicesOnlineLastChecked(): string | undefined {
    const processingServices = this._pipeline.processing_services

    if (!processingServices.length) {
      return undefined
    }

    const last_checked_times = []
    for (const processingService of processingServices) {
      last_checked_times.push(
        new Date(processingService.last_checked).getTime()
      )
    }

    return getFormatedDateTimeString({
      date: new Date(Math.max(...last_checked_times)),
    })
  }
}
