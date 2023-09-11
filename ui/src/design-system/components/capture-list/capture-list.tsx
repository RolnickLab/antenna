import classNames from 'classnames'
import { ReactNode, RefObject } from 'react'
import styles from './capture-list.module.scss'

export const CaptureList = ({
  children,
  hasNext,
  hasPrev,
  isLoadingNext,
  isLoadingPrev,
  innerRef,
  onNext = () => {},
  onPrev = () => {},
}: {
  children: ReactNode
  hasNext?: boolean
  hasPrev?: boolean
  innerRef?: RefObject<HTMLDivElement>
  isLoadingNext?: boolean
  isLoadingPrev?: boolean
  onNext?: () => void
  onPrev?: () => void
}) => (
  <div ref={innerRef} className={styles.captures}>
    <ActionRow
      label={hasPrev ? 'Load previous' : 'Session start'}
      loading={isLoadingPrev}
      disabled={!hasPrev || isLoadingPrev}
      onClick={onPrev}
    />
    {children}
    <ActionRow
      label={hasNext ? 'Load more' : 'Session end'}
      loading={isLoadingNext}
      disabled={!hasNext || isLoadingNext}
      onClick={onNext}
    />
  </div>
)

const ActionRow = ({
  disabled,
  label,
  loading,
  onClick,
}: {
  disabled?: boolean
  label: string
  loading?: boolean
  onClick: () => void
}) => {
  return (
    <p className={styles.action}>
      <span
        className={classNames(styles.actionText, {
          [styles.disabled]: disabled,
        })}
        onClick={!disabled ? onClick : undefined}
      >
        {loading ? `${label}...` : label}
      </span>
    </p>
  )
}
