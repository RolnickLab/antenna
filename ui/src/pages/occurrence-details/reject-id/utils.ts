import { Taxon } from 'data-services/models/taxa'
import { REJECT_OPTIONS } from './constants'

export const getCommonRanks = (occurrencesTaxons: Taxon[]) => {
  const ranks = occurrencesTaxons.map((occurrenceTaxons) =>
    [
      ...occurrenceTaxons.ranks,
      {
        id: occurrenceTaxons.id,
        name: occurrenceTaxons.name,
        rank: occurrenceTaxons.rank,
      },
    ].reverse()
  )

  const commonRanks = ranks.shift()?.filter((rank1) => {
    if (REJECT_OPTIONS.some((o) => o.value === rank1.id)) {
      // Filter out options of type reject
      return false
    }

    return ranks.every((list) => list.some((rank2) => rank1.id === rank2.id))
  })

  return commonRanks ?? []
}
