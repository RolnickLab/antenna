// Detail routes (e.g. taxa/:id?, occurrences/:id?) key their dialogs off a database
// primary key. A route id that is not a positive integer cannot be one, and treating it
// as one risks fetching a same-named sibling collection endpoint instead of a 404
// (e.g. /taxa/lists/ is a real endpoint, so "lists" as a taxon id returns 200 for the
// wrong resource rather than failing).
export const isDetailRouteId = (id?: string): boolean =>
  !!id && /^[1-9][0-9]*$/.test(id)
