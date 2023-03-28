import { ComponentMeta } from '@storybook/react'
import { LoadingSpinner } from './loading-spinner'

type Meta = ComponentMeta<typeof LoadingSpinner>

export default {
  title: 'Components/LoadingSpinner',
  component: LoadingSpinner,
} as Meta

export const Default: Meta = {
  args: {},
}
