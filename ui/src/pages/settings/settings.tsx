import { useSettings } from 'data-services/hooks/useSettings'
import { SettingsField } from 'data-services/models/settings'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { Input } from 'design-system/components/input/input'
import { Select } from 'design-system/components/select/select'
import { Slider } from 'design-system/components/slider/slider'
import { STRING, translate } from 'utils/language'
import styles from './settings.module.scss'

export const Settings = () => {
  const settings = useSettings()

  return (
    <Dialog.Root>
      <Dialog.Trigger>
        <Button
          label={translate(STRING.NAV_ITEM_SETTINGS)}
          icon={IconType.Settings}
          theme={ButtonTheme.Plain}
        />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={translate(STRING.SETTINGS)}>
          <div className={styles.buttonWrapper}>
            <Button label={translate(STRING.RESET)} />
            <Button
              label={translate(STRING.SAVE)}
              theme={ButtonTheme.Success}
            />
          </div>
        </Dialog.Header>
        <div className={styles.content}>
          {Object.entries(settings.sections).map(([section, fieldIds]) => (
            <div key={section} className={styles.section}>
              {fieldIds.map((fieldId) => {
                const field = settings.fields[fieldId]
                return <SettingsFieldComponent key={field.id} field={field} />
              })}
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
        <Input
          name={field.id}
          label={field.title}
          description={field.description}
          type="text"
        />
      )
    case 'options':
      return (
        <Select
          label={field.title}
          placeholder={translate(STRING.SELECT_VALUE)}
          description={field.description}
          options={field.options}
        />
      )
    case 'slider':
      return (
        <Slider
          label={field.title}
          description={field.description}
          settings={field.settings}
        />
      )
  }
}
