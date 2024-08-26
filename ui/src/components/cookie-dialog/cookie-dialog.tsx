import * as Dialog from '@radix-ui/react-dialog'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './cookie-dialog.module.scss'
import { CookieCategory, CookieDialogSection } from './types'

export const CookieDialog = () => {
  const [section, setSection] = useState<CookieDialogSection>(
    CookieDialogSection.Intro
  )

  return (
    <Dialog.Root open={true} modal={false}>
      <Dialog.Portal>
        <Dialog.Content className={styles.dialog}>
          {section === CookieDialogSection.Intro && (
            <IntroContent
              onSectionChange={() => setSection(CookieDialogSection.SetCookies)}
            />
          )}
          {section === CookieDialogSection.SetCookies && (
            <SetCookiesContent
              onSectionChange={() => setSection(CookieDialogSection.Intro)}
            />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

const IntroContent = ({
  onSectionChange,
}: {
  onSectionChange: (section: CookieDialogSection) => void
}) => (
  <div>
    <div className={styles.content}>
      <p>
        We use cookies to analyze the browsing and usage of our website and to
        personalize your experience. You can disable these technologies at any
        time, but this may limit certain functionalities of the site.
      </p>
    </div>
    <div className={styles.actions}>
      <Button
        label="Set cookies"
        onClick={() => onSectionChange(CookieDialogSection.SetCookies)}
      />
      <Button
        label="Refuse cookies"
        onClick={() => {
          /* TODO: Save and close */
        }}
      />
      <Button
        label="Accept cookies"
        theme={ButtonTheme.Success}
        onClick={() => {
          /* TODO: Save and close */
        }}
      />
    </div>
  </div>
)

const SetCookiesContent = ({
  onSectionChange,
}: {
  onSectionChange: (section: CookieDialogSection) => void
}) => {
  const [settings, setSettings] = useState<{
    [key in CookieCategory]: boolean
  }>({
    [CookieCategory.Necessary]: true,
    [CookieCategory.Functionality]: false,
    [CookieCategory.Performance]: false,
  })

  return (
    <div>
      <div className={styles.content}>
        <h1>Set cookies</h1>
        <p>
          You can enable and disable the types of cookies you wish to accept.
          However certain choices you make could affect the services offered on
          our sites.
        </p>
        <div className={styles.options}>
          <Checkbox
            label="Necessary cookies (cookies needed for core features, such as login)"
            checked={settings[CookieCategory.Necessary]}
          />
          <Checkbox
            label="Functionality cookies (cookies to remember user preferences)"
            checked={settings[CookieCategory.Functionality]}
            onCheckedChange={(checked) =>
              setSettings((prev) => ({
                ...prev,
                [CookieCategory.Functionality]: checked,
              }))
            }
          />
          <Checkbox
            label="Performance cookies (cookies for analytics)"
            checked={settings[CookieCategory.Performance]}
            onCheckedChange={(checked) =>
              setSettings((prev) => ({
                ...prev,
                [CookieCategory.Performance]: checked,
              }))
            }
          />
        </div>
      </div>
      <div className={styles.actions}>
        <Button
          label={translate(STRING.CANCEL)}
          onClick={() => onSectionChange(CookieDialogSection.Intro)}
        />
        <Button
          label={translate(STRING.SAVE)}
          theme={ButtonTheme.Success}
          onClick={() => {
            /* TODO: Save and close */
          }}
        />
      </div>
    </div>
  )
}
