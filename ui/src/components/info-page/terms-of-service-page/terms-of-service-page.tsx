import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import styles from '../info-page.module.scss'
import markdown from './terms-of-service.md'

export const TermsOfServicePage = () => {
  const [markdownContent, setMarkdownContent] = useState<string>()

  useEffect(() => {
    const loadContent = async () => {
      const response = await fetch(markdown)
      const markdownContent = await response.text()
      setMarkdownContent(markdownContent)
    }

    loadContent()
  })

  if (!markdownContent) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      </div>
    )
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.container}>
        <ReactMarkdown className={styles.content}>
          {markdownContent}
        </ReactMarkdown>
      </div>
    </div>
  )
}
