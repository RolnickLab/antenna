export interface EntityFieldValues {
  description: string
  name: string
  projectId: string
  customFields?: { [key: string]: string | number | object | undefined }
}
