import { CaptureSetDetailsForm } from './capture-set-details-form'
import { ExportDetailsForm } from './export-details-form'
import { ProcessingServiceDetailsForm } from './processing-service-details-form'
import { StorageDetailsForm } from './storage-details-form'
import { DetailsFormProps } from './types'

export const customFormMap: {
  [key: string]: (props: DetailsFormProps) => JSX.Element
} = {
  'capture set': CaptureSetDetailsForm,
  export: ExportDetailsForm,
  service: ProcessingServiceDetailsForm,
  storage: StorageDetailsForm,
}
