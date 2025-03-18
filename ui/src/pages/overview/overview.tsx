import { ErrorState } from 'components/error-state/error-state'
import { Project } from 'data-services/models/project'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Helmet } from 'react-helmet-async'
import { Outlet, useOutletContext } from 'react-router-dom'
import { Sidebar } from './sidebar/sidebar'

export const Overview = () => {
  const { project, isLoading, error } = useOutletContext<{
    project?: Project
    isLoading: boolean
    isFetching: boolean
    error?: unknown
  }>()

  if (!isLoading && error) {
    return <ErrorState error={error} />
  }

  if (isLoading || !project) {
    return (
      <div className="flex items-center justify-center min-h-[320px]">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <>
      <Helmet>
        <meta property="og:image" content={project.image} />
      </Helmet>
      <div className="flex flex-col gap-6 md:flex-row">
        <Sidebar project={project} />
        <div className="w-full overflow-hidden">
          <Outlet context={{ project }} />
        </div>
      </div>
    </>
  )
}

export default Overview
