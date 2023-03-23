import { ComponentMeta, ComponentStory } from '@storybook/react'
import { Button } from '../button/button'
import * as Dialog from './dialog'

type Meta = ComponentMeta<typeof Dialog.Root>
type Story = ComponentStory<typeof Dialog.Root>

export default {
  title: 'Components/Dialog',
  component: Dialog.Root,
  subcomponents: {
    Trigger: Dialog.Trigger,
    Content: Dialog.Content,
  },
} as Meta

const DialogTemplate: Story = () => (
  <Dialog.Root>
    <Dialog.Trigger>
      <Button label="Click me!" />
    </Dialog.Trigger>
    <Dialog.Content ariaCloselabel="Close">
      <Dialog.Header title="Title" />
      <div
        style={{
          width: '320px',
          padding: '32px',
          boxSizing: 'border-box',
        }}
      >
        Dialog content
      </div>
    </Dialog.Content>
  </Dialog.Root>
)

export const Default = DialogTemplate.bind({})
