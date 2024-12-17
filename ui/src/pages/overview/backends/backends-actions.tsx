import { usePopulateBackend } from 'data-services/hooks/backends/usePopulateBackend'
import { Backend } from 'data-services/models/backend'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const PopulateBackend = ({
  backend,
}: {
  backend: Backend
}) => {
  const [timestamp, setTimestamp] = useState<string>()
  const { populateBackend, isLoading } = usePopulateBackend()

  // TODO: It would be better to inspect task status here, but we currently don't have this information.
  const isPopulating = isLoading || timestamp === backend.updatedAtDetailed

  return (
    <Button
      label={translate(STRING.SYNC)}
      loading={isPopulating}
      disabled={isPopulating}
      theme={ButtonTheme.Success}
      onClick={() => {
        populateBackend(backend.id)
        setTimestamp(backend.updatedAtDetailed)
      }}
    />
  )
}
