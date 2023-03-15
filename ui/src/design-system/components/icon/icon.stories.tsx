import { ComponentMeta } from '@storybook/react'
import { Icon, IconTheme, IconType } from './icon'

type Meta = ComponentMeta<typeof Icon>

export default {
  title: 'Components/Icon',
  component: Icon,
} as Meta

export const Default: Meta = {
  args: {
    type: IconType.BatchId,
    theme: IconTheme.Dark,
  },
}
