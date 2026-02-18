import { Tooltip } from 'nova-ui-kit'
import { ReactNode } from 'react'

interface TooltipProps {
  align?: 'center' | 'end' | 'start'
  asChild?: boolean
  children: ReactNode
  content?: string
  onTriggerClick?: () => void
}

export const BasicTooltip = ({
  align,
  asChild,
  children,
  content,
  onTriggerClick,
}: TooltipProps) => {
  if (!content?.length) {
    return <>{children}</>
  }

  return (
    <Tooltip.Provider delayDuration={0}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild={asChild} onClick={onTriggerClick}>
          {children}
        </Tooltip.Trigger>
        <Tooltip.Content className="max-w-xs" side="bottom" align={align}>
          <span className="block text-center whitespace-break-spaces">
            {content}
          </span>
        </Tooltip.Content>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
