"""Derive eco:targetTaxonomicScope from a project's include-taxa filter.

The scope is the lowest common ancestor (LCA) across all taxa in
Project.default_filters_include_taxa. Empty include-list -> empty string
(meta.xml still declares the column; EML notes the gap).

This is the v1 sourcing strategy. v2 will move to a per-Site TaxaList so each
deployment can declare its own expected species pool (the groundwork for
per-taxon absence occurrence rows).
"""

from __future__ import annotations


def derive_target_taxonomic_scope(project) -> str:
    """Return the name of the LCA of the project's include-taxa filter.

    `parents_json` on each Taxon is ordered root-to-leaf (kingdom first).
    The LCA is the deepest (longest) common prefix of the
    `parents_json + [self]` chains across all selected taxa.
    """
    taxa = list(project.default_filters_include_taxa.all())
    if not taxa:
        return ""

    def ancestry(t) -> list[tuple[int, str]]:
        chain: list[tuple[int, str]] = [(p.id, p.name) for p in (t.parents_json or [])]
        chain.append((t.id, t.name))
        return chain

    chains = [ancestry(t) for t in taxa]
    if any(not c for c in chains):
        return ""

    lca_name = ""
    for position in zip(*chains):
        ids = {entry[0] for entry in position}
        if len(ids) != 1:
            break
        lca_name = position[0][1]
    return lca_name
