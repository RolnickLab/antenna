import { CollectionDetailsForm } from './collection-details-form'
import { ExportDetailsForm } from './export-details-form'
import { ProcessingServiceDetailsForm } from './processing-service-details-form'
import { StorageDetailsForm } from './storage-details-form'
import { DetailsFormProps } from './types'

export const customFormMap: {
  [key: string]: (props: DetailsFormProps) => JSX.Element
} = {
  export: ExportDetailsForm,
  storage: StorageDetailsForm,
  collection: CollectionDetailsForm,
  service: ProcessingServiceDetailsForm,
}
