import { ComponentMeta } from '@storybook/react'
import { Checkbox, CheckboxTheme } from './checkbox'

type Meta = ComponentMeta<typeof Checkbox>

export default {
  title: 'Components/Checkbox',
  component: Checkbox,
} as Meta

export const Default: Meta = {
  args: {
    label: 'Lorem ipsum',
    id: 'checkbox',
    theme: CheckboxTheme.Default,
    defaultChecked: true,
  },
}
