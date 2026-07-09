"""Auto-mode class masking (#1364, Phase 3).

Class masking can resolve its taxa list automatically from the scope's configured
region instead of an operator picking one each run: an occurrence prefers its site's
list, then its project's default; a collection resolves at the project level. When
nothing is configured the run is a safe no-op, so a pipeline can enable masking before
a project has set up a region. These tests pin the config validation, the resolution
ladder, and the no-op path — the masking maths itself is covered in test_class_masking.
"""

import pydantic
from django.test import TestCase

from ami.main.models import Deployment, Occurrence, Project, Site, SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm, AlgorithmTaskType
from ami.ml.post_processing.class_masking import ClassMaskingConfig, ClassMaskingTask


class ClassMaskingConfigValidationTest(TestCase):
    def _config(self, **overrides):
        values = dict(occurrence_id=1, algorithm_id=1)
        values.update(overrides)
        return ClassMaskingConfig(**values)

    def test_default_mode_is_explicit_and_requires_a_list(self):
        with self.assertRaises(pydantic.ValidationError):
            self._config()  # explicit by default, no taxa_list_id
        self.assertEqual(self._config(taxa_list_id=5).taxa_list_mode, "explicit")

    def test_explicit_with_list_is_valid(self):
        config = self._config(taxa_list_mode="explicit", taxa_list_id=5)
        self.assertEqual(config.taxa_list_id, 5)

    def test_auto_must_omit_the_list(self):
        with self.assertRaises(pydantic.ValidationError):
            self._config(taxa_list_mode="auto", taxa_list_id=5)

    def test_auto_without_a_list_is_valid(self):
        config = self._config(taxa_list_mode="auto")
        self.assertEqual(config.taxa_list_mode, "auto")
        self.assertIsNone(config.taxa_list_id)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            self._config(taxa_list_mode="regional", taxa_list_id=5)


class ClassMaskingAutoResolutionTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Auto Project", create_defaults=False)
        self.algorithm = Algorithm.objects.create(
            name="Source classifier", key="auto_src_clf", task_type=AlgorithmTaskType.CLASSIFICATION.value
        )

    def _task(self, **config):
        values = dict(taxa_list_mode="auto", algorithm_id=self.algorithm.pk)
        values.update(config)
        return ClassMaskingTask(**values)

    def _occurrence(self, *, site=None):
        deployment = Deployment.objects.create(name="D", project=self.project, research_site=site)
        return Occurrence.objects.create(project=self.project, deployment=deployment)

    def test_occurrence_prefers_its_sites_list(self):
        site_list = TaxaList.objects.create(name="Site list")
        self.project.default_taxa_list = TaxaList.objects.create(name="Project list")
        self.project.save()
        site = Site.objects.create(name="S", project=self.project, taxa_list=site_list)
        occurrence = self._occurrence(site=site)

        task = self._task(occurrence_id=occurrence.pk)
        self.assertEqual(task._resolve_auto_taxa_list(task.config), site_list)

    def test_occurrence_falls_back_to_project_default(self):
        project_list = TaxaList.objects.create(name="Project list")
        self.project.default_taxa_list = project_list
        self.project.save()
        site = Site.objects.create(name="S", project=self.project)  # no taxa_list on the site
        occurrence = self._occurrence(site=site)

        task = self._task(occurrence_id=occurrence.pk)
        self.assertEqual(task._resolve_auto_taxa_list(task.config), project_list)

    def test_occurrence_resolves_to_none_when_unconfigured(self):
        occurrence = self._occurrence(site=None)
        task = self._task(occurrence_id=occurrence.pk)
        self.assertIsNone(task._resolve_auto_taxa_list(task.config))

    def test_collection_uses_project_default(self):
        project_list = TaxaList.objects.create(name="Project list")
        self.project.default_taxa_list = project_list
        self.project.save()
        collection = SourceImageCollection.objects.create(name="C", project=self.project)

        task = self._task(source_image_collection_id=collection.pk)
        self.assertEqual(task._resolve_auto_taxa_list(task.config), project_list)

    def test_collection_resolves_to_none_without_a_default(self):
        collection = SourceImageCollection.objects.create(name="C", project=self.project)
        task = self._task(source_image_collection_id=collection.pk)
        self.assertIsNone(task._resolve_auto_taxa_list(task.config))

    def test_run_is_a_noop_when_auto_resolves_to_nothing(self):
        occurrence = self._occurrence(site=None)
        self._task(occurrence_id=occurrence.pk).run()
        # No masking algorithm is created when there is no list to apply.
        self.assertFalse(
            Algorithm.objects.filter(key__startswith=f"{self.algorithm.key}_filtered_by_taxa_list_").exists()
        )
