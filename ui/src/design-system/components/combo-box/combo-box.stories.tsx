import { ComponentMeta, ComponentStory } from '@storybook/react'
import { useState } from 'react'
import { ComboBox } from './combo-box'

type Meta = ComponentMeta<typeof ComboBox>
type Story = ComponentStory<typeof ComboBox>

export default {
  title: 'Components/Form/ComboBox',
  component: ComboBox,
} as Meta

const items = [
  { id: 'apple', label: 'Apple' },
  { id: 'banana', label: 'Banana' },
  { id: 'melon', label: 'Melon' },
  { id: 'orange', label: 'Orange' },
  { id: 'pear', label: 'Pear' },
]

const ComboBoxTemplate: Story = () => {
  const [searchString, setSearchString] = useState('')

  return (
    <ComboBox
      emptyLabel="No results to show"
      items={items}
      label="Search for a fruit"
      searchString={searchString}
      onItemSelect={(id) => {
        const item = items.find((i) => i.id === id)
        if (item) {
          setSearchString(item.label)
        }
      }}
      setSearchString={setSearchString}
    />
  )
}

export const Default = ComboBoxTemplate.bind({})
