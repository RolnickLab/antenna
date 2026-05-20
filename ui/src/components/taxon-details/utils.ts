import { Taxon } from "./types";

export const getMainParent = (taxon: Taxon) =>
  taxon.parents.length > 3
    ? taxon.parents.find((p) => p.rank === "FAMILY")
    : undefined;

export const isGenusOrBelow = (taxon: Taxon) =>
  taxon.rank === "GENUS" ||
  taxon.rank === "SPECIES" ||
  taxon.rank === "SUBSPECIES";
