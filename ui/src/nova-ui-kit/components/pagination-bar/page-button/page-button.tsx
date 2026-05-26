import { Button } from 'nova-ui-kit'

interface PageButtonProps {
  page: number
  active?: boolean
  onClick: () => void
}

export const PageButton = ({ page, active, onClick }: PageButtonProps) => (
  <Button
    className="px-3"
    disabled={active}
    onClick={onClick}
    size="small"
    variant="ghost"
  >
    <span>{(page + 1).toLocaleString()}</span>
  </Button>
)
