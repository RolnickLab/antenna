import { TaxaList } from 'data-services/models/taxa-list'
import { Badge, Tooltip } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

// Shown next to a taxa list's name on the taxa lists page and its detail
// page: which projects can see it, and which classifier it mirrors, if any.
export const TaxaListBadges = ({
  projectId,
  taxaList,
}: {
  projectId: string
  taxaList: TaxaList
}) => (
  <div className="flex items-center gap-2">
    {taxaList.isPublic ? <Badge label={translate(STRING.PUBLIC)} /> : null}
    {taxaList.isManaged ? (
      <Tooltip.Provider delayDuration={0}>
        <Tooltip.Root>
          <Tooltip.Trigger>
            <Badge label={translate(STRING.TAXA_LIST_MANAGED_BADGE)} />
          </Tooltip.Trigger>
          <Tooltip.Content side="bottom" className="p-4 max-w-xs">
            <p className="mb-2">
              {translate(STRING.MESSAGE_TAXA_LIST_MANAGED)}
            </p>
            {taxaList.algorithms.map((algorithm) => (
              <Link
                key={algorithm.id}
                className="block underline"
                to={APP_ROUTES.ALGORITHM_DETAILS({
                  projectId,
                  algorithmId: `${algorithm.id}`,
                })}
              >
                {algorithm.name}
              </Link>
            ))}
          </Tooltip.Content>
        </Tooltip.Root>
      </Tooltip.Provider>
    ) : null}
  </div>
)
