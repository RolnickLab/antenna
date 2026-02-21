import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Algorithm, ServerAlgorithm } from './algorithm'
import { ProcessingService } from './processing-service'

export type ServerPipeline = any // TODO: Update this type

export const PIPELINE_ENABLED_CODES = ['ENABLED', 'DISABLED'] as const

export type PipelineEnabledCode = (typeof PIPELINE_ENABLED_CODES)[number]

export enum PipelineEnabledType {
  Enabled,
  Disabled,
}
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

  get versionLabel(): string | undefined {
    if (this._pipeline.version == undefined) {
      return undefined
    }

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

  get currentProcessingService(): {
    online: boolean
    service?: ProcessingService
  } {
    const processingServices = this._pipeline.processing_services.map(
      (service: any) => new ProcessingService(service)
    )
    for (const processingService of processingServices) {
      if (processingService.lastSeenLive) {
        return { online: true, service: processingService }
      }
    }

    return { online: false, service: processingServices[0] }
  }

  get processingServicesOnline(): string {
    const processingServices = this._pipeline.processing_services
    let total_online = 0
    for (const processingService of processingServices) {
      if (processingService.last_seen_live) {
        total_online += 1
      }
    }

    return total_online + '/' + processingServices.length
  }

  get processingServicesOnlineLastSeen(): string | undefined {
    const processingServices = this._pipeline.processing_services

    if (!processingServices.length) {
      return undefined
    }

    const last_seen_times = []
    for (const processingService of processingServices) {
      last_seen_times.push(
        new Date(processingService.last_seen).getTime()
      )
    }

    return getFormatedDateTimeString({
      date: new Date(Math.max(...last_seen_times)),
    })
  }

  get enabled(): {
    code: PipelineEnabledCode
    label: string
    type: PipelineEnabledType
    color: string
  } {
    const status_code = this._pipeline.project_pipeline_configs[0].enabled
      ? 'ENABLED'
      : 'DISABLED'
    return Pipeline.getEnabledInfo(status_code)
  }

  static getEnabledInfo(code: PipelineEnabledCode) {
    const label =
      String(code).charAt(0).toUpperCase() + String(code).toLowerCase().slice(1)

    const type = {
      DISABLED: PipelineEnabledType.Disabled,
      ENABLED: PipelineEnabledType.Enabled,
    }[code]

    const color = {
      [PipelineEnabledType.Disabled]: '#ef4444', // color-destructive-500,
      [PipelineEnabledType.Enabled]: '#09af8a', // color-success-500
    }[type]

    return {
      code,
      label,
      type,
      color,
    }
  }
}
