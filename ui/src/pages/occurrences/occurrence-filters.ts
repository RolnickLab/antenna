// Filter fields another view may carry into the occurrence list (see useCarryOverFilters).
// A field belongs here only if the occurrence list backend honors it (keep in sync with
// OCCURRENCE_FILTERSET_FIELDS by hand) and the occurrence filter panel can display it, so a
// carried filter is always visible and clearable on arrival. See #1347.
export const FILTERS_TO_OCCURRENCES = [
  'detections__source_image',
  'event',
  'taxon',
  'taxa_list_id',
  'not_taxa_list_id',
  'verified',
  'verified_by_me',
  'collection',
  'date_start',
  'date_end',
  'deployment',
  'deployment__device',
  'deployment__research_site',
  'algorithm',
  'not_algorithm',
  'apply_defaults',
]
