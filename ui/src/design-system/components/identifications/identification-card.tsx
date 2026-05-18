import { Button } from 'design-system'
import { cn } from 'design-system/utils'
import { ChevronsUpDownIcon } from 'lucide-react'
import { ReactNode } from 'react'
import { BasicTooltip } from '../tooltip/basic-tooltip'

interface IdentificationCard {
  avatar: ReactNode
  children?: ReactNode
  collapsible?: boolean
  collapsibleTriggerTooltip?: string
  onOpenChange?: (open: boolean) => void
  open?: boolean
  subTitle?: string
  title: string
  onTitleClick?: () => void
}

export const IdentificationCard = ({
  avatar,
  children,
  collapsible,
  collapsibleTriggerTooltip,
  onOpenChange,
  open,
  subTitle,
  title,
  onTitleClick,
}: IdentificationCard) => (
  <div className="border border-border rounded-xl overflow-hidden">
    <div className="flex items-center justify-between gap-4 px-4 py-3 bg-primary-50">
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center shrink-0 w-10 h-10 rounded-full border border-border bg-fieldguide overflow-hidden">
          {avatar}
        </div>
        <div className="grid">
          <span
            tabIndex={onTitleClick ? 0 : -1}
            className={cn('pt-0.5 body-base text-foreground', {
              'font-medium text-primary-600 hover:opacity-70 hover:cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2':
                onTitleClick,
            })}
            onClick={onTitleClick}
          >
            {title}
          </span>
          {subTitle?.length ? (
            <span className="pt-0.5 body-small text-muted-foreground">
              {subTitle}
            </span>
          ) : null}
        </div>
      </div>
      {collapsible ? (
        <BasicTooltip asChild content={collapsibleTriggerTooltip}>
          <Button
            className="w-8 h-8 hover:bg-primary-50"
            size="icon"
            variant="ghost"
            onClick={() => onOpenChange?.(!open)}
          >
            <ChevronsUpDownIcon className="w-4 h-4" />
          </Button>
        </BasicTooltip>
      ) : null}
    </div>
    {children}
  </div>
)
