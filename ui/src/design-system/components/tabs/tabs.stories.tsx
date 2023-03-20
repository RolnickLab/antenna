import { ComponentMeta, ComponentStory } from '@storybook/react'
import * as Tabs from './tabs'

type Meta = ComponentMeta<typeof Tabs.Root>
type Story = ComponentStory<typeof Tabs.Root>

export default {
  title: 'Components/Tabs',
  component: Tabs.Root,
  subcomponents: {
    List: Tabs.List,
    Trigger: Tabs.Trigger,
    Content: Tabs.Content,
  },
  argTypes: {
    defaultValue: {
      control: { type: 'disable' },
    },
  },
} as Meta

const TabsTemplate: Story = () => (
  <Tabs.Root defaultValue="tab1">
    <Tabs.List>
      <Tabs.Trigger value="tab1" label="One" />
      <Tabs.Trigger value="tab2" label="Two" />
      <Tabs.Trigger value="tab3" label="Three" />
    </Tabs.List>
    <Tabs.Content value="tab1">Tab one content</Tabs.Content>
    <Tabs.Content value="tab2">Tab two content</Tabs.Content>
    <Tabs.Content value="tab3">Tab three content</Tabs.Content>
  </Tabs.Root>
)

export const Default = TabsTemplate.bind({})
