import { ComponentMeta } from '@storybook/react'
import { Slider } from './slider'

type Meta = ComponentMeta<typeof Slider>

export default {
  title: 'Components/Form/Slider',
  component: Slider,
  decorators: [(Story) => <div style={{ maxWidth: '320px' }}>{Story()}</div>],
} as Meta

export const Default: Meta = {
  args: {
    label: 'Label',
    description: 'Description',
    settings: {
      min: 0,
      max: 1,
      step: 0.01,
      defaultValue: 0.5,
    },
  },
}
