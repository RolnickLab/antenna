import { ServerConfigSchema } from 'data-services/models/job-type'
import { STRING, translate } from 'utils/language'

export type FieldKind =
  | 'integer'
  | 'number'
  | 'boolean'
  | 'select'
  | 'text'
  | 'entity'
  | 'integer-list'
  | 'json'

export interface FieldDescriptor {
  name: string
  label: string
  description?: string
  kind: FieldKind
  required: boolean
  defaultValue?: unknown
  min?: number
  max?: number
  exclusiveMin?: number
  exclusiveMax?: number
  options?: (string | number)[]
  entity?: string
  entityFilters?: { [key: string]: string | number | boolean }
  advanced?: boolean
}

// Fields the schema marks ami_widget: "hidden" are left out of the form.
export const schemaToFields = (
  schema?: ServerConfigSchema | null
): FieldDescriptor[] =>
  Object.entries(schema?.properties ?? {})
    .filter(([, prop]) => prop.ami_widget !== 'hidden')
    .map(([name, prop]) => {
      const base = {
        name,
        label: prop.title ?? name,
        description: prop.description,
        required: !!schema?.required?.includes(name),
        defaultValue: prop.default,
        advanced: !!prop.ami_advanced,
      }

      if (prop.type === 'array' && prop.items?.type === 'integer') {
        return { ...base, kind: 'integer-list' }
      }
      if (prop.ami_widget === 'entity' && prop.ami_entity) {
        return {
          ...base,
          kind: 'entity',
          entity: prop.ami_entity,
          entityFilters: prop.ami_entity_filters,
        }
      }
      if (prop.type === 'boolean') {
        return { ...base, kind: 'boolean' }
      }
      if (prop.type === 'integer' || prop.type === 'number') {
        return {
          ...base,
          kind: prop.type,
          min: prop.minimum,
          max: prop.maximum,
          exclusiveMin: prop.exclusiveMinimum,
          exclusiveMax: prop.exclusiveMaximum,
        }
      }
      if (prop.type === 'string' && prop.enum?.length) {
        return { ...base, kind: 'select', options: prop.enum }
      }
      if (prop.type === 'string') {
        return { ...base, kind: 'text' }
      }
      return { ...base, kind: 'json' }
    })

const isEmptyDefault = (value: unknown) =>
  value === undefined ||
  value === null ||
  (Array.isArray(value) && value.length === 0) ||
  (typeof value === 'object' && Object.keys(value as object).length === 0)

// Empty defaults (null, [], {}) start blank and show "Not set", rather than as
// raw JSON; leaving them blank sends nothing, so the server default applies.
export const getInitialValue = (field: FieldDescriptor): unknown =>
  isEmptyDefault(field.defaultValue)
    ? undefined
    : field.kind === 'boolean' || field.kind === 'select'
    ? field.defaultValue
    : field.kind === 'json'
    ? JSON.stringify(field.defaultValue)
    : `${field.defaultValue}`

export const validateNumber = (
  field: FieldDescriptor,
  raw: unknown
): string | undefined => {
  if (raw === undefined || raw === null || raw === '') {
    return undefined
  }
  const value = Number(raw)
  if (Number.isNaN(value)) {
    return translate(STRING.MESSAGE_ENTER_NUMBER)
  }
  if (field.kind === 'integer' && !Number.isInteger(value)) {
    return translate(STRING.MESSAGE_ENTER_WHOLE_NUMBER)
  }
  if (field.min !== undefined && value < field.min) {
    return translate(STRING.MESSAGE_VALUE_AT_LEAST, { value: field.min })
  }
  if (field.max !== undefined && value > field.max) {
    return translate(STRING.MESSAGE_VALUE_AT_MOST, { value: field.max })
  }
  if (field.exclusiveMin !== undefined && value <= field.exclusiveMin) {
    return translate(STRING.MESSAGE_VALUE_GREATER_THAN, {
      value: field.exclusiveMin,
    })
  }
  if (field.exclusiveMax !== undefined && value >= field.exclusiveMax) {
    return translate(STRING.MESSAGE_VALUE_LESS_THAN, {
      value: field.exclusiveMax,
    })
  }
  return undefined
}
