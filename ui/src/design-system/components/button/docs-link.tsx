import { BookOpenIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { BasicTooltip } from '../tooltip/basic-tooltip'

export const DocsLink = ({
  href,
  isCompact,
}: {
  href: string
  isCompact?: boolean
}) => (
  <BasicTooltip
    asChild
    content={isCompact ? translate(STRING.VIEW_DOCS) : undefined}
  >
    <a
      aria-label={isCompact ? translate(STRING.VIEW_DOCS) : undefined}
      className={buttonVariants({
        size: isCompact ? 'icon' : 'small',
        variant: 'ghost',
      })}
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <BookOpenIcon className="w-4 h-4" />
      {isCompact ? null : <span>{translate(STRING.VIEW_DOCS)}</span>}
    </a>
  </BasicTooltip>
)
