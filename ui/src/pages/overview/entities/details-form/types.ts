import { Entity } from 'data-services/models/entity'

export type DetailsFormProps = {
  entity?: Entity
  error?: unknown
  isLoading?: boolean
  isSuccess?: boolean
  onSubmit: (
    data: FormValues & { customFields?: { [key: string]: string } }
  ) => void
}

export type FormValues = {
  name: string
  description: string
}
