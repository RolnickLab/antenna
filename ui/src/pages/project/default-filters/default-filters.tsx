import classNames from 'classnames'
import { useUpdateProjectSettings } from 'data-services/hooks/projects/useUpdateProjectSettings'
import { ProjectDetails } from 'data-services/models/project-details'
import styles from 'design-system/components/dialog/dialog.module.scss'
import { DefaultFiltersForm } from 'pages/project-details/default-filters-form'
import { useEffect } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DefaultFilters = () => {
  const navigate = useNavigate()
  const { project } = useOutletContext<{
    project: ProjectDetails
  }>()
  const { updateProject, isLoading, isSuccess, error } =
    useUpdateProjectSettings(project.id)

  useEffect(() => {
    if (!project.canUpdate) {
      navigate(APP_ROUTES.PROJECT_DETAILS({ projectId: project.id }))
    }
  }, [project.canUpdate])

  if (!project.canUpdate) {
    return null
  }

  return (
    <>
      <div className="bg-background border border-border rounded-md overflow-hidden">
        <div className={classNames(styles.dialogHeader, 'bg-background')}>
          <h1 className={styles.dialogTitle}>
            {translate(STRING.NAV_ITEM_DEFAULT_FILTERS)}
          </h1>
        </div>
        <div>
          <DefaultFiltersForm
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => updateProject({ defaultFilters: data })}
            project={project}
          />
        </div>
      </div>
    </>
  )
}
