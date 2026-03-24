import { XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
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
        <Button
          onClick={() =>
            setUserPreferences({ ...userPreferences, termsMessageSeen: true })
          }
          size="icon"
          variant="ghost"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
