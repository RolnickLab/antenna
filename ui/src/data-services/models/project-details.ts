import { UserPermission } from 'utils/user/types'
import { Project } from './project'

export type ServerProject = any // TODO: Update this type

interface Settings {
  sessionTimeGapSeconds: number
  scoreThreshold: number
  includeTaxa: { id: string; name: string }[]
  excludeTaxa: { id: string; name: string }[]
  defaultProcessingPipeline?: { id: string; name: string }
}

export class ProjectDetails extends Project {
  public constructor(project: ServerProject) {
    super(project)
  }

  get permissionsAdminUrl() {
    return `https://api.antenna.insectai.org/bereich/main/project/${this.id}/permissions/` // TODO: Use dynamic admin URL based on environment?
  }

  get isMember(): boolean {
    return this._project.is_member
  }

  get settings(): Settings {
    const includeTaxa = this._project.settings.default_filters_include_taxa.map(
      (taxon: any) => ({
        id: `${taxon.id}`,
        name: taxon.name,
      })
    )
    const excludeTaxa = this._project.settings.default_filters_exclude_taxa.map(
      (taxon: any) => ({
        id: `${taxon.id}`,
        name: taxon.name,
      })
    )
    const defaultProcessingPipeline = this._project.settings
      .default_processing_pipeline
      ? {
          id: `${this._project.settings.default_processing_pipeline.id}`,
          name: this._project.settings.default_processing_pipeline.name,
        }
      : undefined

    return {
      sessionTimeGapSeconds: this._project.settings.session_time_gap_seconds,
      scoreThreshold: this._project.settings.default_filters_score_threshold,
      includeTaxa,
      excludeTaxa,
      defaultProcessingPipeline,
    }
  }

  get userPermissions(): UserPermission[] {
    return this._project.user_permissions
  }
}
