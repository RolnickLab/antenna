// The occurrence list's filter carry-over contract: filter fields that another view may
// carry into the occurrence list (see useCarryOverFilters). A field belongs here only if
// both bounds hold:
//
//   1. The occurrence list backend honors it — keep this in sync by hand with the server
//      filterset (OCCURRENCE_FILTERSET_FIELDS, the custom occurrence filter backends, and
//      TaxonViewSet.get_occurrence_filters in ami/main/api/views.py).
//   2. The occurrence filter panel can display it — every field here has a control on the
//      panel (a pickable control, or a readonly chip such as event/capture that appears
//      once set), so a carried filter is always visible and clearable on arrival rather
//      than silently shrinking the list.
//
// This is a curated subset, not "every field the panel renders" — a field can be on the
// panel yet deliberately left out of carry-over. The carryOverFilters test pins that every
// field here is a registered filter.
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
