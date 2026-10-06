// A row from any list endpoint an entity picker pages through.
export interface ServerEntityOption {
  id: number | string
  name?: string
  source_images_count?: number
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
  ami_advanced?: boolean
  ami_entity?: string
  ami_entity_filters?: { [key: string]: string | number | boolean }
}

export interface ServerConfigSchema {
  type?: string
  title?: string
  required?: string[]
  properties?: { [name: string]: ServerConfigSchemaProperty }
}

// A heading in the Create Job picker, grouping choices by what the user wants to do.
export interface ServerJobGroup {
  key: string
  label: string
}

export interface ServerJobTypeVariant {
  key: string
  name: string
  description?: string
  group: string
  config_schema: ServerConfigSchema | null
}

export interface ServerJobType {
  key: string
  name: string
  description?: string
  // Empty when each variant is listed under its own group instead.
  group: string | null
  allowed: boolean
  config_schema: ServerConfigSchema | null
  variant_key: string | null
  variants: ServerJobTypeVariant[]
}
