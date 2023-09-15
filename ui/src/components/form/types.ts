export interface FieldConfig {
  label: string
  description?: string
  rules?: {
    required?: boolean
    minLength?: number
    maxLength?: number
    min?: number
    max?: number
    validate?: (value: any) => string | undefined
  }
}

export type FormConfig = {
  [name: string]: FieldConfig
}
