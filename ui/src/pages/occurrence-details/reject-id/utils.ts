import { Taxon } from 'data-services/models/taxa'

export const getCommonRanks = (occurrencesTaxons: Taxon[]) => {
  const ranks = occurrencesTaxons.map((occurrenceTaxons) => [
    {
      id: occurrenceTaxons.id,
      name: occurrenceTaxons.name,
      rank: occurrenceTaxons.rank,
    },
    ...occurrenceTaxons.ranks,
  ])

  const commonRanks = ranks
    .shift()
    ?.filter((rank1) =>
      ranks.every((list) => list.some((rank2) => rank1.id === rank2.id))
    )

  return commonRanks ?? []
}
