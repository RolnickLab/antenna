import { ComponentMeta } from '@storybook/react'
import { IconType } from '../icon/icon'
import { IconButton } from './icon-button'

type Meta = ComponentMeta<typeof IconButton>

export default {
  title: 'Components/Buttons/IconButton',
  component: IconButton,
} as Meta

export const Default: Meta = {
  args: {
    iconType: IconType.Checkmark,
  },
}
