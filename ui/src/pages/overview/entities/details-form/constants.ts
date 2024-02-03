import { StorageDetailsForm } from './storage-details-form'
import { DetailsFormProps } from './types'

export const customFormMap: {
  [key: string]: (props: DetailsFormProps) => JSX.Element
} = {
  storage: StorageDetailsForm,
}
