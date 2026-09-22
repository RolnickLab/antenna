# Jobs panel — the two dialogs, as specified on the design canvas

**Status:** design input, harvested 2026-09-22. Not implemented.
**Source:** the two spec panels on the design canvas (`Spec-Create-Job`, `Spec-Run-On-Capture-Set`), drawn after the A-first decision.
**Implements:** phase 4 (the generic dialog) and phase 6 (the contextual entry point) of `2026-09-18-jobs-panel-schema-driven-design.md` §4.

## Why this file exists

The design doc argues the shape of the panel; these two panels fix it. They also settle copy and
two behaviours that the doc leaves open, and they are the first place the class masking field
labels appear in the words an operator will actually read. Phase 1 writes those words into the
pydantic schemas, so they are reproduced verbatim below rather than paraphrased.

## Panel 1 — the generic Create Job dialog

620×880. Header "Create job" with a close button; body; footer.

Field order, top to bottom:

1. **Job type** (required select) — "Post-processing"
2. **Method** (required select) — "Class masking". A paragraph of help text sits under it, taken
   from the task itself.
3. **Capture set** (required select) — shows the set name and its capture count, e.g.
   "Panama 2024 — nightly sample · 12,480 captures"
4. A divider labelled **CLASS MASKING SETTINGS** — the method's own name, uppercased
5. The generated fields for that method (see the copy table below)
6. A warning strip, amber, carrying the in-scope count
7. **Advanced**, collapsed, holding job name and delay

Footer: a **Start immediately** checkbox on the left, **Cancel** and **Create job** on the right.

## Panel 2 — the same form opened from a capture set

Opened from a Run menu on the capture set. The panel's own note states the contract: *"Same form,
same endpoint — only the job type, the method and the scope arrive already answered."*

What changes from panel 1:

- The header becomes the method name, with "Post-processing · Panama 2024 — nightly sample" beneath it.
- Job type and Method are not selects. They are stated, not chosen.
- Scope appears as a line — "Running on **this capture set** · 12,480 captures" — with a **Change**
  link rather than a dropdown.
- The submit button is labelled for the scope: **"Run on 12,480 captures"**, not "Create job".

Everything from the divider down is identical, which is what makes one component with two hosts
work.

## Copy for the class masking fields

Phase 1 turns these into `Field(title=..., description=...)`. They are the panel's exact words.

| Field | Label (`title`) | Help text (`description`) |
|---|---|---|
| taxa list | Taxa list to keep | Classes outside this list are masked out. *(The panel also shows the list's taxon count, which is data, not schema copy.)* |
| algorithm | Source classifier | Its terminal predictions are the ones re-scored. |
| reweight | Reweight scores | Renormalise the kept classes to sum to 1. Off keeps raw absolute scores; the chosen species is the same either way. |

The method's own description, shown under the Method select:

> Masks out classes whose taxon is not on the chosen list and renormalises each prediction over what
> remains. The original classification is kept and demoted.

The warning strip:

> 55,530 classifications are in scope. This rewrites the model's identifications for the whole set;
> originals are demoted, not deleted.

## Three requirements these panels add

1. **A method needs a description, and today none has one.** The Method select's help text and the
   descriptor endpoint both need it, but neither `ClassMaskingTask` nor `SmallSizeFilterTask` has a
   docstring. Phase 1 has to write them, not just annotate fields.

2. **The classifier choices are scoped to the set.** Panel 2 states "Only classifiers that ran on
   this set are listed." That is a filtered queryset keyed on the chosen scope, not a plain list of
   the project's algorithms — a per-field, context-dependent option source that the descriptor
   endpoint's static schema cannot express on its own.

3. **The in-scope count is part of v1's dialog.** The design doc cuts dry-run impact counts to
   phase 7 but keeps "a warning strip carrying the in-scope classification count", and both panels
   show it. It is one query, and the copy above is what it reads.

## Not harvested

The six earlier exploration panels (`B-Catalog`, `C-Wizard`, `D-Contextual`, `E-Field-kit`,
`F-Compare`, `G-A-Holds-Every-Type`) are superseded by the A-first decision recorded in the design
doc. They remain on the canvas.
