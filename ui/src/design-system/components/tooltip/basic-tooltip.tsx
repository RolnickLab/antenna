import { Tooltip } from 'nova-ui-kit'
import { ReactNode } from 'react'

interface TooltipProps {
  asChild?: boolean
  children: ReactNode
  content?: string
  onTriggerClick?: () => void
}

export const BasicTooltip = ({
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
        <Tooltip.Content className="max-w-sm text-center" side="bottom">
          <span className="block whitespace-break-spaces">{content}</span>
        </Tooltip.Content>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
