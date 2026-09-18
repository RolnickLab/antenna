# Species lists and category maps: which list is which

Written 2026-09-17 after tracing the UK & Denmark classifier's species list end to end. Use this
before answering "what species can model X predict", "which list did the training use", or
"where do I get GBIF keys for a model's labels", and as the background for building TaxaLists
from category maps (todo A17 in `docs/claude/planning/2026-09-16-tracking-todos-after-feedback.md`).

## Four different lists, easy to confuse

| List | What it is | Where it lives | Size (UK & Denmark Apr 2024) |
|---|---|---|---|
| **Regional checklist** | Every species someone decided belongs to the region, matched to GBIF. Input to the training pipeline, not its output. | Google Drive sheets (Michael's "species lists" folder, id `1ZKnJMP3_CV_m5sZKSDG_AaC21xyj8LTe`): `UK-Denmark_Moth-List_14Sep2023` (id `1T16hy18EOpTB6s1RPWrhGgyrpXj9oDrDMS0PcS1riRU`), combined `Quebec-Vermont-UK-Denmark_Moth-List_24Aug2023` | 3,022 (combined sheet 5,912) |
| **Category map = the model's list** | The exact ordered label set of the trained network. `--num_classes` of the training run. The only list the model "knows". | The JSON file the ADC serves (`labels_path` of the classifier class in `trapdata/ml/models/classification.py`), fetched from the model object store; cached on each ADC box under `~/.cache/torch/hub/models/`; registered into Antenna as `AlgorithmCategoryMap` when the service's `/info` is read | 2,603 |
| **Antenna's copy** | `AlgorithmCategoryMap.labels` (ordered) + `.data` (index, label, taxon_rank, sometimes gbif_key). Each label is resolved to a `Taxon` row by name or `search_names` when a result is saved. | `ami/ml/models/algorithm.py:38` (model), `ami/ml/models/pipeline.py:440` (registration), `pipeline.py:712` (label → Taxon on save) | 2,603, identical to the file |
| **"Taxa returned by <algorithm>"** | Global `TaxaList` that grows as results are saved: only the top-1 label of each saved classification. What the model *has* predicted so far, not what it *can* predict. | Created in `get_or_create_taxon_for_classification` (`pipeline.py:723`) | grows over time |

The new `Algorithm.get_or_create_taxa_list()` (`ami/ml/models/algorithm.py`, branch
`feat/taxa-list-from-category-map`) adds a fifth: **"Category map of <algorithm>"**, a global
`TaxaList` holding every label of the map, resolved to taxa. That is the list a partner copies
and curates into a regional list (the France list is a curated copy of the UK & Denmark one).

## How the UK & Denmark list was verified (2026-09-17)

All four copies of the model's list were byte-for-byte or entry-for-entry identical:

- Object store file `ami-models/moths/classification/02_ami-gbif_fine-grained_w-europe_category_map-with_names.json`
  (URL form: `https://object-arbutus.alliancecan.ca/swift/v1/AUTH_3c987b8fc90743469d42899b1fdb48eb/ami-models/...`;
  the `object-arbutus.cloud.computecanada.ca/ami-models/...` form in the map's `uri` field
  returns 403 anonymously; the swift URL is public). A name → index dict, md5 `00ded5ad7ac25855068f040dc3f73be8`.
- The cached copy on the development server's ADC, same md5.
- Production Antenna `GET /api/v2/ml/labels/52/` (algorithm 12), 2,603 labels, same order.
- Development server category map id 12, exported as `docs/claude/sessions/2026-09-16-uk-denmark-species-list.csv`.

Training run: wandb `moth-ai/ami-gbif-fine-grained/runs/x5u7jcbf` (`w-europe_resnet50_baseline_run3`,
`--num_classes=2603`, category map `final_lists_eccv2024/02_ami-gbif_fine-grained_w-europe_category_map.json`).
ADC class `UKDenmarkMothSpeciesClassifier2024` (`trapdata/ml/models/classification.py:530` at ADC `55d0787`).

So: the model's list is a strict subset of the regional checklist. 412 checklist species did
not make it into training (probably too few GBIF images; not verified). Split of the 2,603 by
checklist source: 1,863 on both UK and Denmark lists, 427 UK only, 297 Denmark only.

## Getting GBIF keys and taxonomy for a model's labels

Antenna's category map for this model carries no `gbif_key` (only index, label, taxon_rank).
The regional checklist sheets do: `accepted_taxon_key`, `gbif_species`, `status`, `match_type`,
`genus`, `family`, `order`, `source`, `Notes`. Join on label = `search_species`, then on
`gbif_species` for renamed taxa. Result for this model: 2,603 of 2,603 matched (2,446 by searched
name, 157 by GBIF name); 2,441 ACCEPTED, 136 SYNONYM, 26 DOUBTFUL; one label (*Orthosia cruda*)
is ambiguous in the sheet itself.

Outputs: `docs/claude/sessions/2026-09-16-uk-denmark-species-list-augmented.csv` (label +
`antenna_taxon_*` + GBIF columns) and `...-comparison.md` (partner-readable). Both are on Drive
in the species-lists folder as a Sheet (`1OFLOQibMB4liz7CEFfJl2sf9H3dgG4OaLCUfrEM61MQ`) and a
Doc (`1_fh6jaiMVi7A1H9tX_vE9dFGhC9rbrUmvKcwEAYVnno`). Join script:
a helper script, not committed.

## Gotchas met on the way

- `Taxon.name` is unique platform-wide, and migrations seed real names (*Vanessa atalanta*); tests
  need synthetic names.
- Reading a 3,000-row Google Sheet through the Drive MCP `read_file_content` truncates; use
  `gws drive files export --params '{"fileId":..., "mimeType":"text/csv"}' -o file.csv`.
- Agent-side Drive uploads are denied by the permission classifier until the user approves in
  chat; `gws drive +upload` keeps the source MIME type, so follow with `gws drive files copy`
  with `mimeType: application/vnd.google-apps.spreadsheet` (or `.document`) to get a Sheet/Doc.
  `gws drive files update --upload file.md` on a Doc converts markdown in place.
- The combined Quebec-Vermont-UK-Denmark sheet has encoding corruption in 380 rows (the space
  before an author citation became two replacement characters).
- A Django shell export of a category map from a dev box over SSH needs `python -u` and
  `ServerAliveInterval`, or the block-buffered output kills the connection (see memory
  `ssh-django-shell-buffering-drops-long-runs`).
- The development server carries a second registration of this model, "UK & Denmark Species
  Classifier" v2 (algorithm id 4), with no category map and no pipeline. A stub; ignore it.

## Related

- `docs/claude/planning/2026-09-16-tracking-todos-after-feedback.md` A6, A17
- `docs/claude/sessions/2026-09-16-uk-denmark-species-list-comparison.md`
- Memory: `reference_bq_regional_taxalists.md` (regional TaxaList = regional ∩ classifier labels for class masking)
