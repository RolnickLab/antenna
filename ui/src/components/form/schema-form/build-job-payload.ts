import {
  ServerJobType,
  ServerJobTypeVariant,
} from 'data-services/models/job-type'
import { parseIntegerList } from 'utils/fieldProcessors'
import { FieldDescriptor, schemaToFields } from './schema-to-fields'

export interface CreateJobState {
  projectId: string
  jobType: ServerJobType
  variant?: ServerJobTypeVariant
  // Names of the rows chosen in pickers, used for the default job name.
  pickedLabels?: { [field: string]: string }
  configValues: { [field: string]: unknown }
  name?: string
  delay?: string | number
  startNow?: boolean
  today?: string
}

export const coerceValue = (field: FieldDescriptor, raw: unknown): unknown => {
  if (raw === undefined || raw === null || raw === '') {
    return undefined
  }
  switch (field.kind) {
    case 'integer':
    case 'number':
    case 'entity':
      return Number.isNaN(Number(raw)) ? raw : Number(raw)
    case 'integer-list':
      return parseIntegerList(`${raw}`) ?? undefined
    case 'json':
      try {
        return JSON.parse(`${raw}`)
      } catch {
        return raw
      }
    default:
      return raw
  }
}

const collect = (
  fields: FieldDescriptor[],
  values: { [field: string]: unknown }
) => {
  const result: { [field: string]: unknown } = {}
  fields.forEach((field) => {
    const value = coerceValue(field, values[field.name])
    if (value !== undefined) {
      result[field.name] = value
    }
  })
  return result
}

export const buildJobPayload = (state: CreateJobState) => {
  const { jobType, variant, projectId } = state
  const schema = variant?.config_schema ?? jobType.config_schema
  const config = collect(schemaToFields(schema), state.configValues)

  const params =
    jobType.variant_key && variant
      ? { [jobType.variant_key]: variant.key, config }
      : { config }

  const label = variant?.name ?? jobType.name
  // The capture set names a job best; otherwise use whatever was picked first.
  const pickedLabel =
    state.pickedLabels?.source_image_collection_id ||
    Object.values(state.pickedLabels ?? {}).find(Boolean)
  const name =
    state.name?.trim() ||
    `${label} – ${
      pickedLabel ?? state.today ?? new Date().toISOString().slice(0, 10)
    }`

  return {
    body: {
      name,
      delay: Number(state.delay) || 0,
      project_id: projectId,
      job_type_key: jobType.key,
      params,
    },
    startNow: !!state.startNow,
  }
}
