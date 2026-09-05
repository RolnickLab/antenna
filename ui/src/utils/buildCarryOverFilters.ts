// Carry the source view's active filters into a destination list. `fields` is the
// destination's carry contract (e.g. FILTERS_TO_OCCURRENCES), so source-only state such as
// sort order or page number never reaches the destination URL. Kept dependency-free so it
// can be unit-tested without loading the filter registry. See #1347.
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
