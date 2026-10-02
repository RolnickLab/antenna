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

export interface ServerJobTypeVariant {
  key: string
  name: string
  description?: string
  config_schema: ServerConfigSchema | null
}

export interface ServerJobType {
  key: string
  name: string
  description?: string
  allowed: boolean
  config_schema: ServerConfigSchema | null
  variant_key: string | null
  variants: ServerJobTypeVariant[]
}
