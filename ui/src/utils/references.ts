import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

/** Another record the API mentions. `name` is null when the record no longer exists. */
export interface Ref {
  type: string
  id: number
  name: string | null
}

/** Where each type of record is shown in the app. A type missing here is shown as text. */
const ROUTES: Record<string, (projectId: string, id: string) => string> = {
  algorithm: (projectId, id) =>
    APP_ROUTES.ALGORITHM_DETAILS({ projectId, algorithmId: id }),
  capture_set: (projectId, id) =>
    getAppRoute({
      to: APP_ROUTES.CAPTURES({ projectId }),
      filters: { collections: id },
    }),
  job: (projectId, id) => APP_ROUTES.JOB_DETAILS({ projectId, jobId: id }),
  occurrence: (projectId, id) =>
    APP_ROUTES.OCCURRENCE_DETAILS({ projectId, occurrenceId: id }),
  taxa_list: (projectId, id) =>
    APP_ROUTES.TAXA_LIST_DETAILS({ projectId, taxaListId: id }),
  taxon: (projectId, id) =>
    APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: id }),
}

/** Where a reference links to, or undefined when the record is gone or has no page. */
export const linkFor = (ref: Ref, projectId: string) =>
  ref.name === null ? undefined : ROUTES[ref.type]?.(projectId, `${ref.id}`)
