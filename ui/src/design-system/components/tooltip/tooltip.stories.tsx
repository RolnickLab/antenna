import { ComponentMeta, ComponentStory } from '@storybook/react'
import { Button } from '../button/button'
import { Tooltip } from './tooltip'

type Meta = ComponentMeta<typeof Tooltip>
type Story = ComponentStory<typeof Tooltip>

export default {
  title: 'Components/Tooltip',
  component: Tooltip,
  argTypes: {},
} as Meta

const TooltipTemplate: Story = () => (
  <Tooltip content="Lorem ipsum">
    <Button label="Hover or focus me!" />
  </Tooltip>
)

export const Default = TooltipTemplate.bind({})
