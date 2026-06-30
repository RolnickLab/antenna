// Carry filters from one list view into another.
//
// `fields` is the DESTINATION list's carry contract — the filter fields that destination
// honors and is willing to receive — defined as a constant next to that destination's page
// (e.g. FILTERS_TO_OCCURRENCES in pages/occurrences). The source is implicit: whichever of
// those fields is currently active in the source view is carried into the destination URL,
// so the destination keeps the same scope (station, device, site, verification, ...)
// instead of resetting. Passing the destination's own field list — rather than copying the
// whole query string — keeps source-only state (sort order, page number, or a filter the
// destination does not support) out of the URL.
//
// Pure and dependency-free so it can be unit-tested without loading the filter registry.
// The hook form, useCarryOverFilters, lives in useFilters.ts.
export const buildCarryOverFilters = (
  filters: { field: string; value?: string }[],
  fields: string[]
): Record<string, string> =>
  filters.reduce<Record<string, string>>((acc, filter) => {
    if (filter.value && fields.includes(filter.field)) {
      acc[filter.field] = filter.value
    }
    return acc
  }, {})
