import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useState } from 'react'
import { NavigationBar } from './navigation-bar'

type Meta = ComponentMeta<typeof NavigationBar>
type Story = ComponentStory<typeof NavigationBar>

export default {
  title: 'Components/NavigationBar',
  component: NavigationBar,
} as Meta

const NavigationBarTemplate: Story = (args) => {
  const [activeNavItemId, setActiveNavItemId] = useState(args.items?.[0]?.id)

  return (
    <NavigationBar
      items={args.items}
      activeItemId={activeNavItemId}
      onItemClick={(id) => setActiveNavItemId(id)}
    />
  )
}

export const Default = NavigationBarTemplate.bind({})
Default.args = {
  items: [
    { id: 'page-one', title: 'Page one', count: 1 },
    { id: 'page-two', title: 'Page two', count: 2 },
    { id: 'page-three', title: 'Page three', count: 3 },
  ],
}
