import classNames from 'classnames'
import { useUpdateProject } from 'data-services/hooks/projects/useUpdateProject'
import { Project } from 'data-services/models/project'
import styles from 'design-system/components/dialog/dialog.module.scss'
import { DeleteProjectDialog } from 'pages/project-details/delete-project-dialog'
import { ProjectDetailsForm } from 'pages/project-details/project-details-form'
import { useEffect } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const General = () => {
  const navigate = useNavigate()
  const { project } = useOutletContext<{
    project: Project
  }>()
  const {
    updateProject,
    isLoading: isUpdateLoading,
    isSuccess,
    error,
  } = useUpdateProject(project.id)

  useEffect(() => {
    if (project.canUpdate) {
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
            {translate(STRING.NAV_ITEM_GENERAL)}
          </h1>
          {project.canDelete && <DeleteProjectDialog id={project.id} />}
        </div>
        <div>
          <ProjectDetailsForm
            project={project}
            error={error}
            isLoading={isUpdateLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => updateProject(data)}
          />
        </div>
      </div>
    </>
  )
}
