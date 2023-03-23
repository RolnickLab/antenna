import { SettingsField } from 'data-services/types'
import { useSettingsFields } from 'data-services/useSettingsFields'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Input, PathInput } from 'design-system/components/input/input'
import { Select } from 'design-system/components/select/select'
import { Slider } from 'design-system/components/slider/slider'
import React, { useMemo } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './settings.module.scss'

export const Settings = () => {
  const settingsFields = useSettingsFields()

  const sections = useMemo(
    () =>
      settingsFields.reduce<{
        [section: string]: SettingsField[]
      }>((sections, field) => {
        const section = sections[field.section] ?? []
        section.push(field)
        sections[field.section] = section
        return sections
      }, {}),
    [settingsFields]
  )

  return (
    <Dialog.Root>
      <Dialog.Trigger>
        <Button label={translate(STRING.SETTINGS)} theme={ButtonTheme.Plain} />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={translate(STRING.SETTINGS)}>
          <div className={styles.buttonWrapper}>
            <Button label={translate(STRING.RESET)} />
            <Button
              label={translate(STRING.SAVE_CHANGES)}
              theme={ButtonTheme.Success}
            />
          </div>
        </Dialog.Header>
        <div className={styles.content}>
          {Object.entries(sections).map(([section, fields]) => (
            <div key={section} className={styles.section}>
              {fields.map((field) => (
                <SettingsFieldComponent key={field.id} field={field} />
              ))}
            </div>
          ))}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const SettingsFieldComponent = ({ field }: { field: SettingsField }) => {
  switch (field.type) {
    case 'string':
    case 'numeric':
      return (
        <Input
          name={field.id}
          label={field.title}
          description={field.description}
          type={field.type === 'numeric' ? 'number' : 'text'}
        />
      )
    case 'path':
      return (
        <PathInput
          name={field.id}
          placeholder={translate(STRING.SELECT_PATH)}
          label={field.title}
          description={field.description}
        />
      )
    case 'options':
      return (
        <Select
          label={field.title}
          placeholder={translate(STRING.SELECT_VALUE)}
          options={field.selectOptions}
          description={field.description}
        />
      )
    case 'slider':
      return (
        <Slider
          label={field.title}
          description={field.description}
          settings={field.sliderSettings}
        />
      )
  }
}
