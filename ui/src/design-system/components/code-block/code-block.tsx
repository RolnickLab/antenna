import classNames from 'classnames'
import { useRef, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { Button } from '../button/button'
import styles from './code-block.module.scss'
import { useExpander } from './useExpander'

export enum CodeBlockTheme {
  Default = 'default',
  Error = 'error',
}

export const CodeBlock = ({
  lines,
  theme = CodeBlockTheme.Default,
}: {
  lines: string[]
  theme?: CodeBlockTheme
}) => {
  const codeBlockContentRef = useRef<HTMLDivElement>(null)
  const [expanded, setExpanded] = useState(false)
  const showExpander = useExpander(codeBlockContentRef, [lines, expanded])

  return (
    <div
      className={classNames(styles.codeBlock, {
        [styles.error]: theme === CodeBlockTheme.Error,
      })}
    >
      <div
        ref={codeBlockContentRef}
        className={classNames(styles.codeBlockContentWrapper, {
          [styles.expanded]: expanded,
        })}
      >
        <div
          className={classNames(styles.codeBlockContent, {
            [styles.expanded]: expanded,
          })}
        >
          {lines.map((line, index) => (
            <code key={index} className={styles.line}>
              {line}
            </code>
          ))}
        </div>
      </div>
      <div
        className={classNames(styles.overflowFader, {
          [styles.visible]: showExpander && !expanded,
        })}
      />
      {(showExpander || expanded) && (
        <div className={styles.buttonContainer}>
          <Button
            label={
              expanded ? translate(STRING.COLLAPSE) : translate(STRING.EXPAND)
            }
            onClick={() => setExpanded(!expanded)}
          />
        </div>
      )}
    </div>
  )
}
