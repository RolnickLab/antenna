import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useState } from 'react'
import { FormStepper } from './form-stepper'

type Meta = ComponentMeta<typeof FormStepper>
type Story = ComponentStory<typeof FormStepper>

export default {
  title: 'Components/Form/FormStepper',
  component: FormStepper,
} as Meta

const items = [
  { id: 'general', label: 'General' },
  { id: 'location', label: 'Location' },
  { id: 'source-images', label: 'Source images' },
]

const FormStepperTemplate: Story = () => {
  const [currentItem, setCurrentItem] = useState('general')
  return (
    <FormStepper
      items={items}
      currentItem={currentItem}
      setCurrentItem={setCurrentItem}
    />
  )
}

export const Default = FormStepperTemplate.bind({})
