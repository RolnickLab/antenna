import settingsFields from './example-data/settings-fields.json'
import { SettingsField, SettingsFieldType } from './types'

const mockOptions = [
  { value: 'mock-option-1', label: 'Mock option 1' },
  { value: 'mock-option-2', label: 'Mock option 2' },
  { value: 'mock-option-3', label: 'Mock option 3' },
]

export const useSettingsFields = (): SettingsField[] => {
  // TODO: Use real data

  return Object.entries(settingsFields).map(([id, field]) => {
    const type = field.type as SettingsFieldType

    return {
      id,
      title: field.title,
      description: field.description,
      type,
      section: field.section,
      selectOptions: type === 'options' ? mockOptions : undefined,
    }
  })
}
