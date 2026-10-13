// Filter fields another view may carry into the taxa list (see useCarryOverFilters). A field
// belongs here only if the taxa list backend honors it (keep in sync with
// TaxonViewSet.get_occurrence_filters by hand) and the taxa filter panel can display it, so
// a carried filter is always visible and clearable on arrival. See #1347.
export const FILTERS_TO_TAXA = [
  'event',
  'taxon',
  'taxa_list_id',
  'not_taxa_list_id',
  'verified',
  'include_unobserved',
  'deployment',
  'deployment__device',
  'deployment__research_site',
  'tag_id',
  'not_tag_id',
  'apply_defaults',
]
