import { useEffect } from 'react'
import { useCookieConsent } from 'utils/cookieConsent/cookieConsentContext'

const GTM_ID = 'G-EX26RXX0YT'

export const Analytics = () => {
  const { accepted, settings } = useCookieConsent()
  const shouldLoad = accepted && settings.performance

  useEffect(() => {
    if (!shouldLoad) {
      return
    }

    // Load script 1
    const script1 = document.createElement('script')
    script1.async = true
    script1.src = `https://www.googletagmanager.com/gtag/js?id=${GTM_ID}`
    document.head.appendChild(script1)

    // Load script 2
    const script2 = document.createElement('script')
    script2.innerHTML = `
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', '${GTM_ID}');
    `
    document.head.appendChild(script2)

    return () => {
      // Unload both scripts when component unmounts or load condition changes
      document.head.removeChild(script1)
      document.head.removeChild(script2)
    }
  }, [shouldLoad])

  return null
}
