import { cn } from 'design-system/utils'
import { ChevronRightIcon, MinusIcon } from 'lucide-react'
import { Tooltip } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { Taxon } from './types'
import { getMainParent, isGenusOrBelow } from './utils'

interface TaxonDetailsProps {
  compact?: boolean
  onTaxonClick?: (id: string) => void
  size?: 'default' | 'lg'
  taxon: Taxon
}

export const TaxonDetails = ({
  compact,
  onTaxonClick,
  size = 'default',
  taxon,
}: TaxonDetailsProps) => {
  const mainParent = compact ? getMainParent(taxon) : undefined

  const parents = compact
    ? taxon.parents.filter((p) => p !== mainParent).slice(mainParent ? -2 : -3)
    : taxon.parents

  return (
    <div className="flex flex-col items-start gap-1">
      <TaxonLabel onTaxonClick={onTaxonClick} taxon={taxon}>
        <span
          className={cn('font-medium text-primary-500', {
            'body-large': size === 'default',
            'body-xlarge': size === 'lg',
            italic: isGenusOrBelow(taxon),
          })}
        >
          {taxon.name}
        </span>
      </TaxonLabel>
      {parents.length ? (
        <div className="flex items-center flex-wrap gap-1 body-small font-medium text-muted-foreground">
          {mainParent ? (
            <div className="flex items-center gap-1">
              <TaxonLabel onTaxonClick={onTaxonClick} taxon={mainParent}>
                {mainParent.name}
              </TaxonLabel>
              <MinusIcon className="w-4 h-4 text-neutral-400 rotate-90" />
            </div>
          ) : null}
          {parents.map((parent, index) => (
            <div key={index} className="flex items-center gap-1">
              <TaxonLabel onTaxonClick={onTaxonClick} taxon={parent}>
                {parent.name}
              </TaxonLabel>
              {index < parents.length - 1 ? (
                <ChevronRightIcon className="w-4 h-4 text-neutral-400" />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

const TaxonLabel = ({
  children,
  onTaxonClick,
  taxon,
}: {
  children: ReactNode
  onTaxonClick?: (id: string) => void
  taxon: Omit<Taxon, 'parents'>
}) => {
  if (!onTaxonClick) {
    return <>{children}</>
  }

  return (
    <Tooltip.Provider delayDuration={0}>
      <Tooltip.Root>
        <Tooltip.Trigger
          className="hover:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          onClick={() => onTaxonClick(taxon.id)}
        >
          {children}
        </Tooltip.Trigger>
        <Tooltip.Content side="bottom">
          <span>{taxon.rank}</span>
        </Tooltip.Content>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
