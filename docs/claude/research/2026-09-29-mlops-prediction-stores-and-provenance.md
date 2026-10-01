# MLOps prediction stores, run provenance and derived-model lineage

**Question.** How do established ML systems store per-input model outputs (full logits or
top-k, probabilities vs logits, embeddings alongside), normalise run provenance ("this output
came from run R of model M with parameters P"), and express lineage for derived models (a PCA
fitted on model X's embeddings, a head retrained on backbone Y)? Any guidance on storing full
softmax arrays for large label spaces?

**Produced by.** A research agent (Claude Sonnet), 2026-09-29, supervised. Several vendor doc
pages returned thin excerpts; claims marked UNVERIFIED come from search snippets or background
knowledge. The agent did not verify what each vendor stores per row.

## 1. Prediction / inference logging stores

- Arize keys each record by a caller-supplied `prediction_id` (required, used to join delayed
  ground truth) plus `model_id` and `model_version`. Embeddings sit beside predictions as a dict
  of named embedding features. Records carry a score and label, not full logits.
  https://docs.arize.com/arize/machine-learning/concepts-ml/model-schema-reference
- SageMaker Data Capture writes one JSON Lines record per request to S3, input and output
  merged, path `endpoint/variant/yyyy/mm/dd/hh`. Batch mode can emit an inference id to join
  with ground truth. The payload is whatever the model returns; there is no logit or probability
  policy. https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-data-capture.html
- Vertex AI batch prediction writes to BigQuery or Cloud Storage; the prediction schema is
  model-defined. https://docs.cloud.google.com/vertex-ai/docs/model-monitoring/model-monitoring-batch-predictions
- WhyLabs / whylogs stores no per-row outputs, only mergeable statistical profiles per time
  window. https://pypi.org/project/whylogs/
- Seldon Core v1 sends request and response payloads as CloudEvents to a logger (Elasticsearch
  documents); v2 logs step inputs and outputs to Kafka. https://docs.seldon.io/projects/seldon-core/en/latest/analytics/logging.html
- BentoML logs named fields per inference through a `bentoml.monitor` context.
  https://docs.bentoml.com/en/latest/guides/observability/monitoring-and-data-collection.html
- MLflow Tracking is about runs, not per-row predictions. https://www.mlflow.org/docs/latest/ml/tracking/
- Evidently: storage model not verified; it computes reports over a dataframe with prediction
  columns and optional per-class probability columns. UNVERIFIED.

Pattern: the common row key is (caller input id, model id, model version). Run id is rarely part
of it. None of these systems documents keeping full logits by default; they keep label plus
score and treat embeddings as a separate named field.

## 2. Run / execution provenance

- MLflow: a Run is one row holding params, tags, metrics and artifacts; outputs reference the run
  by id, so settings are stored once. https://www.mlflow.org/docs/latest/ml/tracking/
- OpenLineage: Run (client-generated UUID) is an occurrence of a Job that consumes and produces
  Datasets; parameters and provenance travel as facets attached to Run, Job or Dataset.
  https://openlineage.io/docs/spec/object-model/
- MLMD / Vertex ML Metadata: Artifact, Execution and Context joined by Events; an Execution is
  one workflow step annotated with runtime parameters. https://docs.cloud.google.com/vertex-ai/docs/ml-metadata/data-model
- SageMaker Lineage: Context, Action (a step), Artifact, typed Associations.
  https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking-entities.html
- W&B Artifacts: a DAG of runs and versioned artifacts, traversable with `logged_by()` and
  `used_by()`. https://docs.wandb.ai/guides/artifacts/explore-and-traverse-an-artifact-graph
- W3C PROV: Entity, Activity, Agent; `wasGeneratedBy`, `used`, `wasDerivedFrom`,
  `wasAssociatedWith`. https://www.w3.org/TR/prov-o/
- Kedro and DVC: not fetched. UNVERIFIED.

Pattern: every system normalises to one run/execution row with typed parameters, and outputs
hold a foreign key to it. Nobody copies settings per output.

## 3. Lineage for derived models

- MLflow Registry: each model version links to the run that produced it; aliases are mutable
  pointers to immutable versions. https://mlflow.org/docs/latest/ml/model-registry/
- Hugging Face model cards: `base_model` plus `base_model_relation` (adapter, merge, quantized,
  finetune). https://huggingface.co/docs/hub/model-cards
- Vertex and SageMaker express derivation as graph edges (an execution consumed model X and
  produced model Y). Neither has a first-class "PCA fitted on X" concept.

Pattern: a parent pointer with a typed relation, plus a link to the producing run. "PCA fitted on
X's embeddings" is a new model version whose producing run used X's outputs (the agent's
synthesis, not a source statement).

## 4. Full softmax / logits for large label spaces

- Caching only top-k probabilities gives biased, over-confident estimates because the tail mass
  is lost; random sampling of about 12 tokens gives unbiased estimates. Knowledge-distillation
  research on LLM vocabularies, not vision classifiers. https://arxiv.org/abs/2503.16870
- Temperature scaling and other calibration methods need logits, not truncated probabilities
  (background knowledge, UNVERIFIED as a citation).
- No guidance specific to ~29,000-class classifiers was found.

## What transfers to a Postgres/Django platform

1. One run/execution row (job, model version, typed params JSON, settings hash, status,
   timestamps); every output row carries a FK to it. Do not copy settings per output.
2. Key model outputs on (input id, model version); add the run FK on top for post-processing
   decisions.
3. Embeddings in their own table, one row per (item, extractor), with a dimension recorded;
   never mix extractors in one query.
4. Logits off the hot row (float16 array in a side table or a file), with the label-space
   version stored alongside so indices stay decodable.
5. If full logits are too large, keep top-k values with class indices plus the log-sum-exp
   normaliser, so kept-class probabilities stay exact; top-k alone biases calibration.
6. Derived models: `parent` FK plus a `relation_type` enum (pca, head_retrain, quantized,
   finetune) and a `producing_run` FK.
7. Post-processing decisions as rows with run FK, input ids and a reason code; parameters only
   on the run (the PROV pattern).
8. Mutable aliases ("champion") for the current default model, so results keep pointing at
   immutable versions.

## Could not verify

Evidently's storage model; Kedro and DVC provenance; the MLMD GitHub docs (404; Vertex covers the
same model); vendor storage policies for full logits vs top-k; any guidance for ~29,000-class
classifiers.
