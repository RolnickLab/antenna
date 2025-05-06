import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { ReactElement, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import styles from './info-page.module.scss'

export const InfoPage = ({
  anchorPrefix,
  markdown,
}: {
  anchorPrefix?: string
  markdown: URL
}) => {
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
        <ReactMarkdown
          className={styles.content}
          components={{
            ol: (props) => {
              if (!anchorPrefix) {
                return <ol {...props} />
              }

              const start = props.start ?? 1
              const children = (props.children as ReactElement[]).filter(
                (element) => element.type === 'li'
              )

              if (children.length === 1) {
                const id = `${anchorPrefix}-${start}`

                return (
                  <a href={`#${id}`}>
                    <ol id={id} start={start}>
                      {props.children}
                    </ol>
                  </a>
                )
              }

              return <ol start={start}>{props.children}</ol>
            },
          }}
        >
          {markdownContent}
        </ReactMarkdown>
      </div>
    </div>
  )
}
