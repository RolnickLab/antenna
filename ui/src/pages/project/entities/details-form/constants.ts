import { CollectionDetailsForm } from './collection-details-form'
import { ExportDetailsForm } from './export-details-form'
import { ProcessingServiceDetailsForm } from './processing-service-details-form'
import { StorageDetailsForm } from './storage-details-form'
import { TaxonDetailsForm } from './taxon-details-form'
import { DetailsFormProps } from './types'

export const customFormMap: {
  [key: string]: (props: DetailsFormProps) => JSX.Element
} = {
  collection: CollectionDetailsForm,
  export: ExportDetailsForm,
  service: ProcessingServiceDetailsForm,
  storage: StorageDetailsForm,
  taxon: TaxonDetailsForm,
}
