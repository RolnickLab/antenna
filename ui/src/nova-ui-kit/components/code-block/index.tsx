import { ChevronsUpDown, ExternalLinkIcon } from 'lucide-react'
import { Button, buttonVariants } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { useEffect, useRef, useState } from 'react'
import { useShowFader } from './useShowFader'

interface CodeBlockProps {
  className?: string
  collapsible?: boolean
  externalLink?: string
  snippet: string
  theme?: 'default' | 'error'
}

export const CodeBlock = ({
  className,
  collapsible = false,
  externalLink,
  snippet,
  theme = 'default',
}: CodeBlockProps) => {
  const elementRef = useRef<HTMLDivElement>(null)
  const [expanded, setExpanded] = useState(!collapsible)
  const showFader = useShowFader(collapsible, elementRef, [
    collapsible,
    expanded,
    snippet,
  ])
  const showExpandButton = (() => {
    if (!collapsible) {
      return false
    }

    if (!expanded) {
      return showFader
    }

    return true
  })()

  useEffect(() => {
    setExpanded(!collapsible)
  }, [collapsible])

  return (
    <div className="relative">
      <div
        ref={elementRef}
        className={cn(
          'relative p-4 rounded-md border border-border bg-muted overflow-auto overflow-y-hidden',
          {
            'min-h-14': !!externalLink || showExpandButton,
            'max-h-32': !expanded,
          },
          className
        )}
      >
        <pre
          className={cn('text-xs text-muted-foreground', {
            'text-destructive': theme === 'error',
          })}
        >
          {snippet}
        </pre>
        {showFader && (
          <div className="absolute bottom-0 left-0 w-full h-12 bg-gradient-to-b from-[transparent] to-muted" />
        )}
      </div>
      <div className="absolute top-2 right-2 flex items-center gap-2">
        {externalLink ? (
          <a
            className={buttonVariants({ variant: 'outline', size: 'icon' })}
            href={externalLink}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLinkIcon className="h-4 w-4" />
          </a>
        ) : null}
        {showExpandButton ? (
          <Button
            onClick={() => setExpanded(!expanded)}
            size="icon"
            variant="outline"
          >
            <ChevronsUpDown className="h-4 w-4" />
          </Button>
        ) : null}
      </div>
    </div>
  )
}
