export interface ServerScopeField {
  field: string
  label: string
  entity: string
  required: boolean
  many: boolean
  target: 'job' | 'config'
  entity_filters: { [key: string]: string | number | boolean }
}

export interface ServerConfigSchemaProperty {
  title?: string
  description?: string
  type?: string
  default?: unknown
  enum?: (string | number)[]
  minimum?: number
  maximum?: number
  exclusiveMinimum?: number
  exclusiveMaximum?: number
  items?: { type?: string }
  ami_widget?: string
  ami_entity?: string
  ami_entity_filters?: { [key: string]: string | number | boolean }
}

export interface ServerConfigSchema {
  type?: string
  title?: string
  required?: string[]
  properties?: { [name: string]: ServerConfigSchemaProperty }
}

export interface ServerJobTypeVariant {
  key: string
  name: string
  description?: string
  allowed: boolean
  scope: ServerScopeField[]
  scope_rule?: 'all_required' | 'exactly_one'
  config_schema: ServerConfigSchema | null
}

export interface ServerJobType {
  key: string
  name: string
  description?: string
  allowed: boolean
  scope: ServerScopeField[]
  required_fields: string[]
  required_params: string[]
  config_schema: ServerConfigSchema | null
  variant_key: string | null
  variants: ServerJobTypeVariant[]
}
