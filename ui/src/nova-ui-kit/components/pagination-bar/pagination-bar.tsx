import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { getPageWindow } from './getPageWindow'
import { InfoLabel } from './info-label/info-label'
import { PageButton } from './page-button/page-button'
import styles from './pagination-bar.module.scss'

interface PaginationBarProps {
  compact?: boolean
  pagination: {
    page: number
    perPage: number
  }
  setPage: (page: number) => void
  total: number
}

export const PaginationBar = ({
  compact,
  pagination,
  setPage,
  total,
}: PaginationBarProps) => {
  const { page: currentPage, perPage } = pagination
  const numPages = Math.ceil(total / perPage)

  if (compact && numPages === 1) {
    return null
  }

  const firstPage = 0
  const lastPage = numPages - 1
  const pageWindow = getPageWindow(currentPage, numPages)
  const showStartDivider = pageWindow[0] - firstPage > 1
  const showEndDivider = lastPage - pageWindow[pageWindow.length - 1] > 1

  return (
    <div className={styles.wrapper}>
      <InfoLabel pagination={pagination} total={total} />
      <div className={styles.pageSettings}>
        <Button
          aria-label={translate(STRING.PREVIOUS)}
          disabled={currentPage <= firstPage}
          onClick={() => setPage(currentPage - 1)}
          size="icon"
          variant="outline"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
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
        <Button
          aria-label={translate(STRING.NEXT)}
          disabled={currentPage >= lastPage}
          onClick={() => setPage(currentPage + 1)}
          size="icon"
          variant="outline"
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
