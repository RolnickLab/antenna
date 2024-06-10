import { ComponentMeta } from '@storybook/react'
import { Select } from './select'

type Meta = ComponentMeta<typeof Select>

export default {
  title: 'Components/Form/Select',
  component: Select,
  decorators: [(Story) => <div style={{ maxWidth: '320px' }}>{Story()}</div>],
} as Meta

export const Default: Meta = {
  args: {
    label: 'Label',
    placeholder: 'Placeholder',
    options: [
      { value: 'option-1', label: 'Option 1' },
      { value: 'option-2', label: 'Option 2' },
      { value: 'option-3', label: 'Option 3' },
    ],
  },
}
