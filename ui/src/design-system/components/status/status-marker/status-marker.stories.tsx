import { ComponentMeta } from '@storybook/react'
import { Status } from '../types'
import { StatusMarker } from './status-marker'

type Meta = ComponentMeta<typeof StatusMarker>

export default {
  title: 'Components/Status/StatusMarker',
  component: StatusMarker,
} as Meta

export const Default: Meta = {
  args: {
    status: Status.Success,
  },
}
