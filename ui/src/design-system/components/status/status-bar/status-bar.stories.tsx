import { ComponentMeta } from '@storybook/react'
import { Status } from '../types'
import { StatusBar } from './status-bar'

type Meta = ComponentMeta<typeof StatusBar>

export default {
  title: 'Components/Status/StatusBar',
  component: StatusBar,
} as Meta

export const Default: Meta = {
  args: {
    status: Status.Success,
    progress: 0.33,
    description: '33% completed, 3h 10min left.',
  },
}
