import { Taxon } from 'data-services/models/taxa'

export const getCommonRanks = ({
  occurrenceTaxa,
  rejectOptions,
}: {
  occurrenceTaxa: Taxon[]
  rejectOptions: { label: string; value: string }[]
}) => {
  const ranks = occurrenceTaxa.map((taxon) =>
    [
      ...taxon.ranks,
      {
        id: taxon.id,
        name: taxon.name,
        rank: taxon.rank,
      },
    ].reverse()
  )

  const commonRanks = ranks.shift()?.filter((rank1) => {
    if (rejectOptions.some((o) => o.value === rank1.id)) {
      // Filter out options of type reject
      return false
    }

    return ranks.every((list) => list.some((rank2) => rank1.id === rank2.id))
  })

  return commonRanks ?? []
}
