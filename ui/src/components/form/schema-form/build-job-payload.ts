import {
  ServerJobType,
  ServerJobTypeVariant,
} from 'data-services/models/job-type'
import { parseIntegerList } from 'utils/fieldProcessors'
import {
  FieldDescriptor,
  schemaToFields,
  scopeToFields,
} from './schema-to-fields'

export interface CreateJobState {
  projectId: string
  jobType: ServerJobType
  variant?: ServerJobTypeVariant
  scopeValues: { [field: string]: unknown }
  scopeLabels?: { [field: string]: string }
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

const getScopeFields = (state: CreateJobState) => {
  const { jobType, variant } = state
  return [
    ...scopeToFields(jobType.scope),
    ...scopeToFields(variant?.scope ?? [], {
      optional: variant?.scope_rule === 'exactly_one',
    }),
  ]
}

export const buildJobPayload = (state: CreateJobState) => {
  const { jobType, variant, projectId } = state
  const scopeItems = [
    ...jobType.scope.map((item) => ({ ...item })),
    ...(variant?.scope ?? []),
  ]
  const scopeFields = getScopeFields(state)
  const scopeValues = collect(scopeFields, state.scopeValues)

  const jobScope: { [field: string]: unknown } = {}
  const configScope: { [field: string]: unknown } = {}
  scopeItems.forEach((item) => {
    if (item.field in scopeValues) {
      const target = item.target === 'config' ? configScope : jobScope
      target[item.field] = scopeValues[item.field]
    }
  })

  const schema = variant?.config_schema ?? jobType.config_schema
  const config = {
    ...collect(schemaToFields(schema), state.configValues),
    ...configScope,
  }

  let params: { [key: string]: unknown } | undefined
  if (jobType.variant_key && variant) {
    params = { [jobType.variant_key]: variant.key, config }
  } else if (jobType.config_schema) {
    params = { config }
  }

  const label = variant?.name ?? jobType.name
  const scopeLabel = Object.values(state.scopeLabels ?? {}).find(Boolean)
  const name =
    state.name?.trim() ||
    `${label} – ${
      scopeLabel ?? state.today ?? new Date().toISOString().slice(0, 10)
    }`

  return {
    body: {
      name,
      delay: Number(state.delay) || 0,
      project_id: projectId,
      job_type_key: jobType.key,
      ...jobScope,
      ...(params ? { params } : {}),
    },
    startNow: !!state.startNow,
  }
}
