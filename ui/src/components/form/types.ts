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
  // Processor functions for field value transformation
  toApiValue?: (formValue: any) => any // Form → API
  toFormValue?: (apiValue: any) => any // API → Form
}

export type FormConfig = {
  [name: string]: FieldConfig
}
