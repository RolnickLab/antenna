import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import styles from './terms-of-service-info.module.scss'

export const TermsOfServiceInfo = () => {
  const { userPreferences, setUserPreferences } = useUserPreferences()

  useEffect(() => {
    return () => {
      // Mark message as seen when component unmounts
      setUserPreferences({ ...userPreferences, termsMessageSeen: true })
    }
  }, [])

  if (userPreferences.termsMessageSeen) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <p>
        By using this website you agree to the{' '}
        <Link to={APP_ROUTES.TERMS_OF_SERVICE}>Terms of Service.</Link>
      </p>
      <div className={styles.iconContainer}>
        <IconButton
          icon={IconType.Cross}
          theme={IconButtonTheme.Plain}
          onClick={() =>
            setUserPreferences({ ...userPreferences, termsMessageSeen: true })
          }
        />
      </div>
    </div>
  )
}
