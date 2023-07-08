import { FormConfig } from 'components/form/types'
import { STRING, translate } from 'utils/language'

export const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: { required: true },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
  latitude: {
    label: translate(STRING.FIELD_LABEL_LATITUDE),
    rules: { min: -90, max: 90 },
  },
  longitude: {
    label: translate(STRING.FIELD_LABEL_LONGITUDE),
    rules: {
      min: -180,
      max: 180,
    },
  },
  path: {
    label: translate(STRING.FIELD_LABEL_PATH),
    rules: { required: true },
  },
}
