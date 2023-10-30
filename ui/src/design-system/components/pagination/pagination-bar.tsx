import { Button, ButtonTheme } from '../button/button'
import { IconButton, IconButtonShape } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { getPageWindow } from './getPageWindow'
import styles from './pagination-bar.module.scss'

interface PaginationBarProps {
  page: number
  perPage: number
  total: number
  setPage: (page: number) => void
}

export const PaginationBar = ({
  page: currentPage,
  perPage,
  total,
  setPage,
}: PaginationBarProps) => {
  const numPages = Math.ceil(total / perPage)
  const pageWindow = getPageWindow(currentPage, numPages)
  const firstPage = 0
  const lastPage = numPages - 1
  const showStartDivider = pageWindow[0] - firstPage > 1
  const showEndDivider = lastPage - pageWindow[pageWindow.length - 1] > 1

  return (
    <div className={styles.paginationBar}>
      <IconButton
        disabled={currentPage <= firstPage}
        icon={IconType.ToggleLeft}
        shape={IconButtonShape.RoundLarge}
        onClick={() => setPage(currentPage - 1)}
      />
      <div className={styles.pageWindow}>
        {!pageWindow.includes(firstPage) && (
          <>
            <PageButton page={firstPage} onClick={() => setPage(firstPage)} />
            {showStartDivider ? (
              <span className={styles.divider}>...</span>
            ) : null}
          </>
        )}
        {pageWindow.map((page) => (
          <PageButton
            key={page}
            active={page === currentPage}
            page={page}
            onClick={() => setPage(page)}
          />
        ))}
        {!pageWindow.includes(lastPage) && (
          <>
            {showEndDivider ? (
              <span className={styles.divider}>...</span>
            ) : null}
            <PageButton page={lastPage} onClick={() => setPage(lastPage)} />
          </>
        )}
      </div>
      <IconButton
        disabled={currentPage >= lastPage}
        icon={IconType.ToggleRight}
        shape={IconButtonShape.RoundLarge}
        onClick={() => setPage(currentPage + 1)}
      />
    </div>
  )
}

const PageButton = ({
  page,
  active,
  onClick,
}: {
  page: number
  active?: boolean
  onClick: () => void
}) => (
  <Button
    customClass={styles.pageButton}
    disabled={active}
    label={`${page}`}
    theme={ButtonTheme.Plain}
    onClick={onClick}
  />
)
