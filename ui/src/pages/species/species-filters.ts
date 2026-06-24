// The taxa list's filter carry-over contract: filter fields that another view may carry
// into the taxa list (see useCarryOverFilters). A field belongs here only if both bounds
// hold:
//
//   1. The taxa list backend honors it — keep this in sync by hand with the server
//      filterset (TaxonViewSet.filterset_fields and get_occurrence_filters in
//      ami/main/api/views.py).
//   2. The taxa filter panel can display it — every field here has a control on the panel
//      (pickable, or a readonly chip such as event that appears once set), so a carried
//      filter is always visible and clearable on arrival.
//
// Differs from FILTERS_TO_OCCURRENCES where the lists differ: the taxa list carries
// "show unobserved taxa" and the tag filters (its own filters) but not the occurrence-only
// ones. The carryOverFilters test pins that every field here is a registered filter.
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
