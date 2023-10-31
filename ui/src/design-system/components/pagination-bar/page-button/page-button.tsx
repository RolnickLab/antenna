import { Button, ButtonTheme } from '../../button/button'
import styles from './page-button.module.scss'

interface PageButtonProps {
  page: number
  active?: boolean
  onClick: () => void
}

export const PageButton = ({ page, active, onClick }: PageButtonProps) => (
  <Button
    customClass={styles.pageButton}
    disabled={active}
    label={`${page}`}
    theme={ButtonTheme.Plain}
    onClick={onClick}
  />
)
