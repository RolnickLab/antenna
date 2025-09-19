import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

export const CollectionDetails = () => {
  const { projectId, id } = useParams()
  const navigate = useNavigate()

  useEffect(
    () =>
      navigate(
        getAppRoute({
          to: APP_ROUTES.CAPTURES({ projectId: projectId as string }),
          filters: { collections: id as string },
        })
      ),
    []
  )

  return null
}
