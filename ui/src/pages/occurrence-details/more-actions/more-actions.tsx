import { ChevronDownIcon, ImagesIcon } from 'lucide-react'
import { Button, buttonVariants, Popover } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const MoreActions = ({
  embeddingAlgorithms,
  occurrenceId,
  projectId,
}: {
  embeddingAlgorithms: { id: number; name: string }[]
  occurrenceId: string
  projectId: string
}) => {
  const [open, setOpen] = useState(false)

  if (!embeddingAlgorithms.length) {
    return null
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button size="small" variant="outline">
          <span>{translate(STRING.MORE_ACTIONS)}</span>
          <ChevronDownIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content className="w-auto p-2" align="start">
        <div className="flex flex-col gap-1">
          {embeddingAlgorithms.map((algorithm) => (
            <Link
              key={algorithm.id}
              className={cn(
                buttonVariants({ size: 'small', variant: 'ghost' }),
                'justify-start'
              )}
              onClick={() => setOpen(false)}
              to={`${APP_ROUTES.OCCURRENCES({
                projectId,
              })}?${new URLSearchParams({
                ordering: 'visual_similarity',
                similar_to: occurrenceId,
                similarity_algorithm: `${algorithm.id}`,
              })}`}
            >
              <ImagesIcon className="w-4 h-4" />
              <span>
                {translate(STRING.SHOW_SIMILAR_BY, { name: algorithm.name })}
              </span>
            </Link>
          ))}
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
