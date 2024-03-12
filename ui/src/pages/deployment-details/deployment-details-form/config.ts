import { FormConfig } from 'components/form/types'
import { bytesToMB } from 'utils/bytesToMB'
import { API_MAX_UPLOAD_SIZE } from 'utils/constants'
import { STRING, translate } from 'utils/language'


export const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    rules: { required: true },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
  siteId: {
    label: translate(STRING.FIELD_LABEL_SITE),
  },
  deviceId: {
    label: translate(STRING.FIELD_LABEL_DEVICE),
  },
  image: {
    label: translate(STRING.FIELD_LABEL_IMAGE),
    description: [
      translate(STRING.MESSAGE_IMAGE_SIZE, {
        value: bytesToMB(API_MAX_UPLOAD_SIZE),
        unit: 'MB',
      }),
      translate(STRING.MESSAGE_IMAGE_FORMAT),
    ].join('\n'),
    rules: {
      validate: (file: File) => {
        if (file) {
          if (file?.size > API_MAX_UPLOAD_SIZE) {
            return translate(STRING.MESSAGE_IMAGE_TOO_BIG)
          }
        }
      },
    },
  },
  dataSourceId: {
    label: translate(STRING.FIELD_LABEL_DATA_SOURCE),
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
  },
}
