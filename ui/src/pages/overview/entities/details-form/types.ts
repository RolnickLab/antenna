import { Entity } from 'data-services/models/entity'

export type DetailsFormProps = {
  entity?: Entity
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (
    data: FormValues & {
      customFields?: { [key: string]: string | number | object | undefined }
    }
  ) => void
}

export type FormValues = {
  name: string
  description: string
}
