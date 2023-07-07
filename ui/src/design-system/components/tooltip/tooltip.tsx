import * as _Tooltip from '@radix-ui/react-tooltip'
import { ReactNode, useRef } from 'react'
import { Link } from 'react-router-dom'
import styles from './tooltip.module.scss'

interface TooltipProps {
  children: ReactNode
  content: string
  delayDuration?: number
  frame?: HTMLElement | null
  open?: boolean
  to?: string
}

export const Tooltip = ({
  children,
  content,
  delayDuration = 0,
  frame,
  open,
  to,
}: TooltipProps) => {
  const triggerRef = useRef(null)

  return (
    <_Tooltip.Provider>
      <_Tooltip.Root delayDuration={delayDuration} open={open}>
        <_Tooltip.Trigger
          asChild
          ref={triggerRef}
          onClick={(event) => event.preventDefault()}
        >
          {children}
        </_Tooltip.Trigger>
        <_Tooltip.Portal>
          <_Tooltip.Content
            className={styles.tooltipContent}
            collisionBoundary={frame}
            collisionPadding={6}
            side="bottom"
            sideOffset={6}
            onPointerDownOutside={(event) => {
              if (event.target === triggerRef.current) {
                event.preventDefault()
              }
            }}
          >
            {to ? <Link to={to}>{content}</Link> : <span>{content}</span>}
            <_Tooltip.Arrow className={styles.tooltipArrow} />
          </_Tooltip.Content>
        </_Tooltip.Portal>
      </_Tooltip.Root>
    </_Tooltip.Provider>
  )
}
