import * as Dialog from '@radix-ui/react-dialog'
import { Checkbox } from 'design-system/components/checkbox/checkbox'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useCookieConsent } from 'utils/cookieConsent/cookieConsentContext'
import { CookieCategory } from 'utils/cookieConsent/types'
import { STRING, translate } from 'utils/language'
import styles from './cookie-dialog.module.scss'

export enum CookieDialogSection {
  Intro,
  SetCookies,
}

export const CookieDialog = () => {
  const { accepted } = useCookieConsent()
  const [section, setSection] = useState<CookieDialogSection>(
    CookieDialogSection.Intro
  )

  return (
    <Dialog.Root open={!accepted} modal={false}>
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
}) => {
  const { setSettings } = useCookieConsent()

  return (
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
          onClick={() => onSectionChange(CookieDialogSection.SetCookies)}
          size="small"
          variant="outline"
        >
          <span>Set cookies</span>
        </Button>
        <Button
          onClick={() =>
            setSettings({
              [CookieCategory.Necessary]: true,
              [CookieCategory.Functionality]: false,
              [CookieCategory.Performance]: false,
            })
          }
          size="small"
          variant="outline"
        >
          <span>Refuse</span>
        </Button>
        <Button
          onClick={() =>
            setSettings({
              [CookieCategory.Necessary]: true,
              [CookieCategory.Functionality]: true,
              [CookieCategory.Performance]: true,
            })
          }
          size="small"
          variant="success"
        >
          <span>Accept</span>
        </Button>
      </div>
    </div>
  )
}

const SetCookiesContent = ({
  onSectionChange,
}: {
  onSectionChange: (section: CookieDialogSection) => void
}) => {
  const { settings, setSettings } = useCookieConsent()
  const [formValues, setFormValues] = useState(settings)

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
            id={CookieCategory.Necessary}
            label="Necessary cookies (cookies needed for core features, such as login)"
            checked={formValues[CookieCategory.Necessary]}
            disabled
          />
          <Checkbox
            id={CookieCategory.Functionality}
            label="Functionality cookies (cookies to remember user preferences)"
            checked={formValues[CookieCategory.Functionality]}
            onCheckedChange={(checked) =>
              setFormValues((prev) => ({
                ...prev,
                [CookieCategory.Functionality]: checked,
              }))
            }
          />
          <Checkbox
            id={CookieCategory.Performance}
            label="Performance cookies (cookies for analytics)"
            checked={formValues[CookieCategory.Performance]}
            onCheckedChange={(checked) =>
              setFormValues((prev) => ({
                ...prev,
                [CookieCategory.Performance]: checked,
              }))
            }
          />
        </div>
      </div>
      <div className={styles.actions}>
        <Button
          onClick={() => onSectionChange(CookieDialogSection.Intro)}
          size="small"
          variant="outline"
        >
          <span>{translate(STRING.CANCEL)}</span>
        </Button>
        <Button
          onClick={() => setSettings(formValues)}
          size="small"
          variant="success"
        >
          <span>{translate(STRING.SAVE)}</span>
        </Button>
      </div>
    </div>
  )
}
