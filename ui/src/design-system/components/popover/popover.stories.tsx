import { ComponentMeta, ComponentStory } from '@storybook/react'
import { Button } from '../button/button'
import * as Popover from './popover'

type Meta = ComponentMeta<typeof Popover.Root>
type Story = ComponentStory<typeof Popover.Root>

export default {
  title: 'Components/Popover',
  component: Popover.Root,
  subcomponents: {
    Trigger: Popover.Trigger,
    Content: Popover.Content,
  },
} as Meta

const PopoverTemplate: Story = () => (
  <Popover.Root>
    <Popover.Trigger>
      <Button label="Click me!" />
    </Popover.Trigger>
    <Popover.Content ariaCloselabel="Close" align="start" side="right">
      <div style={{ padding: '30px' }}>Popover content</div>
    </Popover.Content>
  </Popover.Root>
)

export const Default = PopoverTemplate.bind({})
