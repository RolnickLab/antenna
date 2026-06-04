import { BookOpenIcon, ChevronRight } from 'lucide-react'
import { BasicTooltip, buttonVariants } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

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
      {isCompact ? (
        <BookOpenIcon className="w-4 h-4" />
      ) : (
        <>
          <span>{translate(STRING.VIEW_DOCS)}</span>
          <ChevronRight className="w-4 h-4" />
        </>
      )}
    </a>
  </BasicTooltip>
)
