import { ComponentMeta, ComponentStory } from '@storybook/react'
import { IconType } from '../icon/icon'
import { StatusBullet, StatusBulletTheme } from './status-bullet/status-bullet'
import * as Wizard from './wizard'

type Meta = ComponentMeta<typeof Wizard.Root>
type Story = ComponentStory<typeof Wizard.Root>

export default {
  title: 'Components/Wizard',
  component: Wizard.Root,
  subcomponents: {
    Item: Wizard.Item,
    Trigger: Wizard.Trigger,
    Content: Wizard.Content,
  },
} as Meta

const WizardTemplate: Story = () => (
  <Wizard.Root>
    <Wizard.Item value="item-1">
      <Wizard.Trigger title="Object Detection">
        <StatusBullet
          icon={IconType.Checkmark}
          theme={StatusBulletTheme.Success}
        />
      </Wizard.Trigger>
      <Wizard.Content>Room for content.</Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="item-2">
      <Wizard.Trigger title="Objects of Interest Filter">
        <StatusBullet value={2} theme={StatusBulletTheme.Default} />
      </Wizard.Trigger>
      <Wizard.Content>Room for content.</Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="item-3">
      <Wizard.Trigger title="Taxon Classifier">
        <StatusBullet value={3} theme={StatusBulletTheme.Neutral} />
      </Wizard.Trigger>
      <Wizard.Content>Room for content.</Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="item-4">
      <Wizard.Trigger title="Occurrence Tracking">
        <StatusBullet value={4} theme={StatusBulletTheme.Neutral} />
      </Wizard.Trigger>
      <Wizard.Content>Room for content.</Wizard.Content>
    </Wizard.Item>
  </Wizard.Root>
)

export const Default = WizardTemplate.bind({})
