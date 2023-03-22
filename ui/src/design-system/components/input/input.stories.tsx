import { ComponentMeta } from '@storybook/react'
import { Input } from './input'

type Meta = ComponentMeta<typeof Input>

export default {
  title: 'Components/Input',
  component: Input,
  decorators: [(Story) => <div style={{ maxWidth: '320px' }}>{Story()}</div>],
} as Meta

const Default: Meta = {
  args: {
    label: 'Label',
    placeholder: 'Placeholder',
    description: 'Description',
  },
}

export const TextInput: Meta = {
  args: {
    ...Default.args,
    type: 'text',
    name: 'text-input',
  },
}

export const NumberInput: Meta = {
  args: {
    ...Default.args,
    type: 'number',
    name: 'number-input',
  },
}
