import { FormConfig } from 'components/form/types'
import { STRING, translate } from 'utils/language'

export const config: FormConfig = {
  name: {
    label: translate(STRING.DETAILS_LABEL_NAME),
    rules: { required: true },
  },
  description: {
    label: 'Description',
  },
  latitude: {
    label: translate(STRING.DETAILS_LABEL_LATITUDE),
    rules: { min: -90, max: 90 },
  },
  longitude: {
    label: translate(STRING.DETAILS_LABEL_LONGITUDE),
    rules: {
      min: -180,
      max: 180,
    },
  },
  path: {
    label: translate(STRING.DETAILS_LABEL_PATH),
    rules: { required: true },
  },
}
