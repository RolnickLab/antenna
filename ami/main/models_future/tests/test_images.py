import copy
import datetime
import logging
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from ami.main.models import Deployment, Project
from ami.main.models_future.images import (
    SourceImage,
    SourceImageCollection,
    SourceImageThumbnail,
    sample_captures_by_interval,
)
from ami.tests.fixtures.main import create_captures, create_captures_from_files, setup_test_project
from ami.users.models import User

logger = logging.getLogger(__name__)


NEW_THUMBNAIL_SETTINGS = copy.deepcopy(settings.THUMBNAILS)
NEW_THUMBNAIL_SETTINGS["SIZES"]["small"]["width"] = 300


class TestImageThumbnailViews(TestCase):
    base_url = "http://testserver/api/v2/captures/thumbnails/"

    def setUp(self) -> None:
        self.project, self.deployment = setup_test_project()

        self.captures = create_captures_from_files(deployment=self.deployment)
        self.first_capture = self.captures[0][0]

        return super().setUp()

    def test_thumbnail_no_list(self):
        response = self.client.get("/api/v2/captures/thumbnails/")
        self.assertEqual(response.status_code, 405)

    def test_thumbnail_new(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(thumb.width, 240)
        self.assertEqual(thumb.height, 180)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_new_with_size(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/?label=medium")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="medium")
        self.assertEqual(thumb.width, 1024)
        self.assertEqual(thumb.height, 768)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_new_with_large_size(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/?label=large")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="large")
        # ``width`` stores the requested spec width for the regen gate, not the
        # encoder output. The test fixture is 1024px wide and PIL's thumbnail()
        # never upscales, so the stored file keeps its original dimensions.
        self.assertEqual(thumb.width, 2560)
        self.assertEqual(thumb.height, 768)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_strips_exif_orientation(self):
        """Thumbnails must stay in the source file's raw pixel space so detection
        boxes (stored in raw coordinates) align when overlaid in the UI: neither
        rotate the pixels nor propagate the EXIF Orientation tag to the output.
        """
        from django.core.files.storage import default_storage

        from ami.utils import s3

        ORIENTATION_TAG = 274  # EXIF tag id for Orientation
        source = Image.new("RGB", (320, 240), (10, 120, 30))
        exif = source.getexif()
        exif[ORIENTATION_TAG] = 6  # stored landscape, rotate 90° CW to view
        buffer = BytesIO()
        source.save(buffer, format="JPEG", exif=exif)

        assert self.deployment.data_source is not None
        s3.write_file(self.deployment.data_source.config, self.first_capture.path, buffer.getvalue())

        thumb = self.first_capture.find_or_generate_thumbnail_for_label("large")

        with default_storage.open(thumb.path) as f:
            output = Image.open(f)
            output.load()

        # Pixels stay in raw (landscape) space and the orientation tag is gone.
        self.assertEqual(output.size, (320, 240))
        self.assertIsNone(output.getexif().get(ORIENTATION_TAG))

    def test_thumbnail_blank_path_row_regenerates(self):
        """A row with an empty ``path`` (failed or interrupted generation) must
        trigger regeneration, not redirect to the storage root.
        """
        self.first_capture.thumbnails.create(path="", label="small", width=240, height=180, size=0)
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="small")
        self.assertTrue(thumb.path)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_redirect_is_browser_cacheable(self):
        """The 302 must carry Cache-Control so browsers reuse the redirect across
        page views instead of re-paying the round trip per thumbnail per view.
        """
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Cache-Control"], "private, max-age=300")

    def test_thumbnail_new_with_invalid_size(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/?label=typo")
        self.assertEqual(response.status_code, 400)

    def test_thumbnail_exists(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        t_id = self.first_capture.thumbnails.first().pk
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(self.first_capture.thumbnails.count(), 1)
        self.assertEqual(self.first_capture.thumbnails.first().pk, t_id)
        thumb = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_exists_newer_modified_source(self):
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.first()
        original_pk = thumb.pk
        original_thumb_last_modified = thumb.last_modified
        self.first_capture.last_modified = datetime.datetime.now()
        self.first_capture.save()
        self.assertTrue(self.first_capture.last_modified > thumb.last_modified)
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(self.first_capture.thumbnails.count(), 1)
        # The upsert must reuse the existing row (same PK).
        refreshed = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(refreshed.pk, original_pk)
        # Regen must force-bump last_modified (auto_now_add fires only on INSERT).
        self.assertGreater(refreshed.last_modified, original_thumb_last_modified)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/media/{refreshed.path}")

    def test_thumbnail_source_last_modified_none_does_not_crash(self):
        """Legacy SourceImage rows synced before the upload backfill have last_modified=None.

        Once a thumbnail row exists, the regen check used to raise
        ``TypeError: '<' not supported between instances of 'datetime.datetime' and 'NoneType'``
        on every subsequent request. Now the comparison should treat None as "no signal of
        source change" and reuse the cached thumb.
        """
        # First request generates the thumb (last_modified=None at this point is fine because
        # the short-circuit on ``not thumb`` doesn't reach the comparison).
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        thumb_id = self.first_capture.thumbnails.first().pk

        # Simulate a legacy row with no source mtime.
        SourceImage.objects.filter(pk=self.first_capture.pk).update(last_modified=None)

        # Second request must reuse the cached thumb, not raise.
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.first_capture.thumbnails.count(), 1)
        self.assertEqual(self.first_capture.thumbnails.first().pk, thumb_id)

    def test_thumbnail_regen_reuses_row_via_upsert(self):
        """Regenerating an existing thumbnail must upsert into the same row, not
        delete-then-recreate (which under concurrent gen destroyed the other
        racer's row and storage blob).

        Triggers the regen path by making the cached row's width stale (as if
        ``settings.THUMBNAILS`` changed since generation), then re-requesting.
        Asserts the row's primary key is preserved (proving
        ``update_or_create`` UPDATE was used, not a fresh INSERT after a
        DELETE).
        """
        # First request populates the cache.
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        original_thumb = self.first_capture.thumbnails.get(label="small")
        original_pk = original_thumb.pk

        # Make the cached row stale so the regen branch fires.
        self.first_capture.thumbnails.filter(label="small").update(width=9999)

        # Regen must reuse the same row and not raise on the (source_image, label)
        # UniqueConstraint.
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.first_capture.thumbnails.filter(label="small").count(), 1)
        self.assertEqual(self.first_capture.thumbnails.get(label="small").pk, original_pk)

    def test_upload_handler_backfills_last_modified(self):
        """``create_source_image_from_upload`` must set ``last_modified`` so uploaded
        captures match the parity of S3-synced ones and can be invalidated when re-uploaded.
        """
        from ami.main.models import create_source_image_from_upload

        png = BytesIO()
        Image.new("RGB", (320, 240), (255, 0, 0)).save(png, format="JPEG")
        png.seek(0)
        upload = SimpleUploadedFile("20200101000000-test.jpg", png.read(), content_type="image/jpeg")
        before = timezone.now()
        captured = create_source_image_from_upload(image=upload, deployment=self.deployment, process_now=False)
        after = timezone.now()

        self.assertIsNotNone(captured.last_modified)
        self.assertGreaterEqual(captured.last_modified, before)
        self.assertLessEqual(captured.last_modified, after)

    @override_settings(THUMBNAILS={"STORAGE_PREFIX": "thumbnails/", "SIZES": {}})
    def test_thumbnail_empty_sizes_returns_clear_error(self):
        """If THUMBNAILS['SIZES'] is empty the endpoint must return a clear API error,
        not 500 with ``StopIteration`` from ``next(iter(empty))``.
        """
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"No thumbnail sizes", response.content)

    def test_thumbnail_non_rgb_source_converts(self):
        """RGBA/P/etc. source images must be converted to RGB before JPEG encode."""
        from unittest import mock

        rgba_buf = BytesIO()
        Image.new("RGBA", (320, 240), (255, 0, 0, 128)).save(rgba_buf, format="PNG")
        rgba_bytes = rgba_buf.getvalue()

        with mock.patch("ami.main.models_future.images.fetch_image_content", return_value=rgba_bytes):
            response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")

        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(thumb.width, 240)

    @override_settings(THUMBNAILS=NEW_THUMBNAIL_SETTINGS)
    def test_thumbnail_settings_change_regenerates(self):
        # A pre-existing different size thumb
        self.first_capture.thumbnails.create(path="thumbs/test", label="small", width=240, height=180, size=0)
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(self.first_capture.thumbnails.count(), 1)
        thumb = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(thumb.width, 300)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/media/{thumb.path}")

    def test_thumbnail_row_stores_spec_width_not_encoder_output(self):
        """``PIL.Image.thumbnail()`` preserves aspect ratio and can emit a width
        1-2px below the requested spec (e.g. 239 for a 240 spec). The row must
        record the spec width — it identifies which configured size the row
        satisfies — otherwise the strict-equality regen gate treats the row as
        stale and regenerates on every request. See #1331.
        """
        from unittest import mock

        original_thumbnail = Image.Image.thumbnail

        def rounding_thumbnail(img, size, *args, **kwargs):
            # Simulate Pillow's aspect-preserving rounding landing 1px under spec.
            original_thumbnail(img, (size[0] - 1, size[1]), *args, **kwargs)

        with mock.patch.object(Image.Image, "thumbnail", rounding_thumbnail):
            response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        thumb = self.first_capture.thumbnails.get(label="small")
        spec_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        self.assertEqual(thumb.width, spec_width)
        first_gen_marker = thumb.last_modified

        # Second request must reuse the cached row. A regen force-bumps
        # ``last_modified``, so an unchanged value proves the gate held.
        response = self.client.get(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/")
        self.assertEqual(response.status_code, 302)
        refreshed = self.first_capture.thumbnails.get(label="small")
        self.assertEqual(refreshed.last_modified, first_gen_marker)

    def test_captures_response_includes_thumbnail_urls(self):
        response = self.client.get(f"/api/v2/captures/{self.first_capture.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        rec = response.json()
        self.assertIn("thumbnails", rec)
        self.assertURLEqual(rec["thumbnails"]["small"], f"{self.base_url}{self.first_capture.pk}/?label=small")
        self.assertURLEqual(rec["thumbnails"]["medium"], f"{self.base_url}{self.first_capture.pk}/?label=medium")

    def test_captures_list_response_includes_thumbnail_urls(self):
        response = self.client.get(f"/api/v2/captures/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        capture_json = response.json()["results"][0]
        self.assertIn("thumbnails", capture_json)
        self.assertURLEqual(
            capture_json["thumbnails"]["small"], f"{self.base_url}{self.first_capture.pk}/?label=small"
        )
        self.assertURLEqual(
            capture_json["thumbnails"]["medium"], f"{self.base_url}{self.first_capture.pk}/?label=medium"
        )

    def test_session_example_captures_response_includes_thumbnail_urls(self):
        response = self.client.get(f"/api/v2/events/?deployment={self.deployment.pk}")
        self.assertEqual(response.status_code, 200)
        capture_json = response.json()["results"][0]["example_captures"][0]
        self.assertIn("thumbnails", capture_json)
        self.assertURLEqual(capture_json["thumbnails"]["small"], f"{self.base_url}{capture_json['id']}/?label=small")
        self.assertURLEqual(capture_json["thumbnails"]["medium"], f"{self.base_url}{capture_json['id']}/?label=medium")

    def test_session_first_capture_response_includes_thumbnail_urls(self):
        response = self.client.get(f"/api/v2/events/{self.deployment.events.all()[0].pk}/")
        self.assertEqual(response.status_code, 200)
        capture_json = response.json()["first_capture"]
        self.assertIn("thumbnails", capture_json)
        self.assertURLEqual(capture_json["thumbnails"]["small"], f"{self.base_url}{capture_json['id']}/?label=small")
        self.assertURLEqual(capture_json["thumbnails"]["medium"], f"{self.base_url}{capture_json['id']}/?label=medium")

    def test_source_image_delete_cascades_to_thumbnails(self):
        """Deleting a SourceImage must cascade-delete its SourceImageThumbnail rows.

        The previous SET_NULL FK left orphan rows (and their storage blobs) forever
        with no reaper. CASCADE + the pre_delete signal in ami.main.signals together
        guarantee the row is gone and the blob is cleaned up.
        """
        # Pre-populate two thumbnail rows for the capture.
        for label, width in [("small", 240), ("medium", 1024)]:
            self.first_capture.thumbnails.create(
                path=f"thumbnails/cascadetest_{label}.jpg", label=label, width=width, height=180, size=42
            )
        capture_pk = self.first_capture.pk
        self.assertEqual(SourceImageThumbnail.objects.filter(source_image_id=capture_pk).count(), 2)

        # Delete the parent capture.
        self.first_capture.delete()

        # Thumbnail rows must be gone via CASCADE.
        self.assertEqual(SourceImageThumbnail.objects.filter(source_image_id=capture_pk).count(), 0)

    def test_thumbnail_delete_removes_storage_blob(self):
        """The pre_delete signal must call default_storage.delete on the row's path.

        Covers both explicit row deletes and CASCADE deletes — the signal fires for
        both. Use FileSystemStorage's exists() to verify the blob is gone.
        """
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        # Plant a real blob in storage and wire up a row pointing at it.
        path = default_storage.save("thumbnails/signal_test.jpg", ContentFile(b"\x00\x01\x02\x03"))
        self.assertTrue(default_storage.exists(path))

        thumb = self.first_capture.thumbnails.create(path=path, label="small", width=240, height=180, size=4)
        thumb.delete()

        self.assertFalse(default_storage.exists(path), "pre_delete signal must clean the storage blob")

    def test_serializer_emits_storage_url_when_thumb_row_exists(self):
        """Warm-path optimization: when a SourceImageThumbnail row exists with the
        configured width, the serializer must emit ``default_storage.url(row.path)``
        directly instead of the lazy-regen route URL. This is the whole point of
        the direct-URLs change — every cached thumbnail must skip Django on the
        warm path.
        """
        from django.core.files.storage import default_storage

        # Pre-create a thumbnail row whose width matches THUMBNAILS['SIZES']['small'].
        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        self.first_capture.thumbnails.create(
            path="thumbnails/cached/abc.jpg", label="small", width=configured_width, height=180, size=42
        )

        response = self.client.get(f"/api/v2/captures/{self.first_capture.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        small_url = response.json()["thumbnails"]["small"]

        # ``small`` should be the storage URL, not the route URL.
        expected_storage_url = default_storage.url("thumbnails/cached/abc.jpg")
        self.assertEqual(small_url, expected_storage_url)
        # ``medium`` has no cached row → falls back to the route URL.
        self.assertURLEqual(
            response.json()["thumbnails"]["medium"], f"{self.base_url}{self.first_capture.pk}/?label=medium"
        )

    def test_serializer_falls_back_to_route_url_when_width_mismatches_spec(self):
        """Any width != the configured spec → route URL so the next browser fetch
        triggers lazy regen via the redirect viewset. The check is strict equality,
        so this covers both a changed setting (stored wider/narrower than spec) and
        legacy rows that recorded PIL's rounded output (e.g. 239 for a 240 spec)
        before the #1306 spec-width fix — those self-heal through one regeneration.
        """
        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        # +100 = settings changed since last gen; -1 = legacy encoder rounding.
        for delta in (100, -1):
            with self.subTest(delta=delta):
                self.first_capture.thumbnails.update_or_create(
                    label="small",
                    defaults={
                        "path": f"thumbnails/stale/{delta}.jpg",
                        "width": configured_width + delta,
                        "height": 180,
                        "size": 42,
                    },
                )
                response = self.client.get(f"/api/v2/captures/{self.first_capture.pk}/?project_id={self.project.pk}")
                self.assertEqual(response.status_code, 200)
                self.assertURLEqual(
                    response.json()["thumbnails"]["small"], f"{self.base_url}{self.first_capture.pk}/?label=small"
                )

    def test_serializer_falls_back_to_route_url_when_source_changed(self):
        """If the source image was re-uploaded after the cached row was
        generated (``source.last_modified > row.last_modified``), the serializer
        must emit the route URL so the next browser fetch regenerates via the
        redirect viewset. Mirrors the predicate the generator already uses.

        Guards https://github.com/RolnickLab/antenna/pull/1331#discussion_r3373715397.
        """
        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        # Row generated at T0. ``last_modified`` is ``auto_now_add`` so set
        # ``self.first_capture.last_modified`` to a later timestamp via UPDATE
        # below to flip the staleness predicate.
        self.first_capture.thumbnails.create(
            path="thumbnails/preupload/abc.jpg", label="small", width=configured_width, height=180, size=42
        )
        # Source bytes were re-uploaded after the cached row was written.
        SourceImage.objects.filter(pk=self.first_capture.pk).update(
            last_modified=timezone.now() + datetime.timedelta(minutes=1)
        )

        response = self.client.get(f"/api/v2/captures/{self.first_capture.pk}/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        # Source-changed → emit route URL so the redirect viewset regenerates.
        self.assertURLEqual(
            response.json()["thumbnails"]["small"], f"{self.base_url}{self.first_capture.pk}/?label=small"
        )

    def test_thumbnail_urls_model_method_emits_warm_and_route(self):
        """``SourceImage.thumbnail_urls`` is the single source of truth for the
        per-label URL contract: warm storage URL when a cached row exists at
        the configured width, route URL otherwise.

        Exercising the model method directly keeps the contract regression-tested
        even if the serializer surface changes (e.g. a future template tag or
        management command that needs the same dict).
        """
        from django.core.files.storage import default_storage

        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        self.first_capture.thumbnails.create(
            path="thumbnails/cached/direct.jpg", label="small", width=configured_width, height=180, size=42
        )

        # Prefetch via ``with_thumbnails()`` to exercise the warm path; without the
        # prefetch the method emits route URLs without querying (see the test below).
        capture = SourceImage.objects.with_thumbnails().get(pk=self.first_capture.pk)
        urls = capture.thumbnail_urls(request=None)

        # Warm path → direct storage URL for the cached label.
        self.assertEqual(urls["small"], default_storage.url("thumbnails/cached/direct.jpg"))
        # Cold path → route URL for labels without a cached row. With ``request=None``
        # the URL is path-only (no scheme/host) — matches DRF's reverse() contract.
        self.assertIn(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/", urls["medium"])
        self.assertIn("label=medium", urls["medium"])

    def test_thumbnail_urls_without_prefetch_emits_route_urls_without_querying(self):
        """Without prefetched thumbnails, ``thumbnail_urls`` must not fire a
        per-object SELECT (an N+1 in list contexts) — it falls back to route URLs.
        A cached row exists here, but the un-prefetched call must ignore it rather
        than query for it."""
        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        self.first_capture.thumbnails.create(
            path="thumbnails/cached/noprefetch.jpg", label="small", width=configured_width, height=180, size=42
        )

        capture = SourceImage.objects.get(pk=self.first_capture.pk)
        with self.assertNumQueries(0):
            urls = capture.thumbnail_urls(request=None)

        # Cached row ignored (not prefetched) → route URL, not the storage URL.
        self.assertIn(f"/api/v2/captures/thumbnails/{self.first_capture.pk}/", urls["small"])
        self.assertIn("label=small", urls["small"])

    def test_warm_list_serves_storage_urls_with_single_thumbnail_query(self):
        """The contract this PR exists to deliver: a warm gallery list serves direct
        storage URLs while reading the thumbnail table once (the prefetch), not once
        per row.

        Runtime no longer enforces the prefetch (un-prefetched falls back to route
        URLs without querying), so this test is the only guard against both
        regressions: dropping ``with_thumbnails()`` from the viewset (→ route URLs,
        the perf win silently lost) and a per-row lazy read (→ N+1). Needs a
        multi-row fixture — a single row hides an N+1.
        """
        from django.core.files.storage import default_storage
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        configured_width = settings.THUMBNAILS["SIZES"]["small"]["width"]
        captures = list(SourceImage.objects.filter(deployment=self.deployment))
        self.assertGreater(len(captures), 1, "need >1 capture to detect an N+1")
        for cap in captures:
            cap.thumbnails.create(
                path=f"thumbnails/warm/{cap.pk}.jpg", label="small", width=configured_width, height=180, size=42
            )

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(f"/api/v2/captures/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)

        results = response.json()["results"]
        self.assertGreater(len(results), 1)
        for rec in results:
            # Warm row → direct storage URL (regression guard: dropped prefetch → route URL).
            self.assertEqual(
                rec["thumbnails"]["small"],
                default_storage.url(f"thumbnails/warm/{rec['id']}.jpg"),
            )

        thumb_queries = [q for q in ctx.captured_queries if "sourceimagethumbnail" in q["sql"].lower()]
        self.assertLessEqual(
            len(thumb_queries), 1, f"thumbnails must be one prefetch, not per-row; got {len(thumb_queries)}"
        )


class TestThumbnailDraftProjectVisibility(APITestCase):
    """PR #1306 follow-up: draft (non-public) projects must not route thumbnails
    through the auth-gated thumbnail endpoint.

    The frontend loads thumbnails via an anonymous ``<img>`` tag, which cannot send
    an Authorization header, so a draft project's gated thumbnail endpoint returns
    401 and the image renders broken. The serializer omits thumbnail URLs for draft
    projects so the frontend falls back to the capture's source URL (``capture.url``,
    the pre-thumbnail-layer behavior). Public projects keep server-generated thumbnails.
    """

    def setUp(self) -> None:
        super().setUp()
        self.superuser = User.objects.create_superuser(email="thumb-draft-admin@insectai.org", password="secret")
        # Superuser can view captures of a draft project; we assert on the serialized
        # ``thumbnails`` field, which is independent of who is viewing.
        self.client.force_authenticate(self.superuser)

    def _make_project_with_captures(self, draft: bool):
        project, deployment = setup_test_project(reuse=False)
        if draft:
            project.draft = True
            project.save(update_fields=["draft"])
        captures = create_captures_from_files(deployment=deployment)
        return project, deployment, [c[0] for c in captures]

    def test_public_project_returns_thumbnail_urls(self):
        project, _, captures = self._make_project_with_captures(draft=False)
        response = self.client.get(f"/api/v2/captures/{captures[0].pk}/?project_id={project.pk}")
        self.assertEqual(response.status_code, 200)
        thumbnails = response.json()["thumbnails"]
        self.assertIsNotNone(thumbnails)
        self.assertIn("small", thumbnails)

    def test_draft_project_omits_thumbnail_urls(self):
        project, _, captures = self._make_project_with_captures(draft=True)
        response = self.client.get(f"/api/v2/captures/{captures[0].pk}/?project_id={project.pk}")
        self.assertEqual(response.status_code, 200)
        rec = response.json()
        # No thumbnail endpoint URLs -> frontend falls back to the capture's source URL.
        self.assertIsNone(rec["thumbnails"])
        self.assertTrue(rec["url"], "source URL must still be provided for fallback")

    @override_settings(CACHALOT_ENABLED=False)
    def test_thumbnails_check_does_not_fetch_project_per_capture(self):
        """Reading ``project.thumbnails_enabled`` per capture must not trigger a query.

        The list queryset ``select_related("project")`` so the FK is populated via the
        main JOIN. Without it the serializer would lazy-load ``obj.project`` once per
        capture row — an N+1. We assert no standalone per-row fetch of the project
        table occurs. Query caching is disabled so the count reflects real DB hits.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        project, _, captures = self._make_project_with_captures(draft=True)
        self.assertGreater(len(captures), 1, "need a multi-row fixture to detect an N+1")

        url = f"/api/v2/captures/?project_id={project.pk}"
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()["results"]), 1, "need >1 result row to detect an N+1")

        # A lazy-load of ``obj.project`` reads the project table as the primary FROM
        # (``SELECT ... FROM main_project WHERE id = ?``); the JOINed list query does
        # not. Match without quoted identifiers so it is not tied to one DB backend.
        per_row_project_fetches = [
            q for q in ctx.captured_queries if "from main_project" in q["sql"].lower().replace('"', "")
        ]
        self.assertEqual(
            len(per_row_project_fetches),
            0,
            f"project table fetched {len(per_row_project_fetches)} times across "
            f"{len(captures)} captures (expected 0 via select_related)",
        )


class TestSourceImageCollections(TestCase):
    def setUp(self) -> None:
        from ami.main.models import Deployment, Project

        self.project_one = Project.objects.create(name="Test Project One")
        self.deployment = Deployment.objects.create(name="Test Deployment", project=self.project_one)

        create_captures(deployment=self.deployment, num_nights=2, images_per_night=10, interval_minutes=1)

        return super().setUp()

    def test_random_sample(self):
        sample_size = 10

        collection = SourceImageCollection.objects.create(
            name="Test Random Source Image Collection",
            project=self.project_one,
            method="random",
            kwargs={"size": sample_size},
        )
        collection.save()
        collection.populate_sample()

        assert collection.images.count() == sample_size

    def test_manual_sample(self):
        images = self.deployment.captures.all()

        collection = SourceImageCollection.objects.create(
            name="Test Manual Source Image Collection",
            project=self.project_one,
            method="manual",
            kwargs={"image_ids": [image.pk for image in images]},
        )
        collection.save()
        collection.populate_sample()

        assert collection.images.count() == len(images)
        for image in images:
            assert image in collection.images.all()

    def test_interval_sample(self):
        # Ensure that the images are 5 at least minutes apart and less than 6 minutes apart within each event
        # This depends on the test setUp creating images with a 1 minute interval

        minute_interval = 10

        collection = SourceImageCollection.objects.create(
            name="Test Interval Source Image Collection",
            project=self.project_one,
            method="interval",
            kwargs={"minute_interval": minute_interval},
        )
        collection.save()
        collection.populate_sample()

        events = collection.images.values_list("event", flat=True).distinct()
        for event in events:
            last_image = None
            for image in collection.images.filter(event=event):
                if last_image:
                    interval = image.timestamp - last_image.timestamp
                    assert interval >= datetime.timedelta(minutes=minute_interval)
                    assert interval < datetime.timedelta(minutes=minute_interval + 1)
                last_image = image

    def test_interval_with_excluded_events(self):
        minute_interval = 5
        events = self.deployment.events.all()
        excluded_event = events.first()
        assert excluded_event is not None

        collection = SourceImageCollection.objects.create(
            name="Test Interval With Excluded Events",
            project=self.project_one,
            method="interval",
            kwargs={"minute_interval": minute_interval, "exclude_events": [excluded_event.pk]},
        )
        collection.save()
        collection.populate_sample()

        # Ensure that no images from the excluded event are in the collection
        for image in collection.images.all():
            assert image.event != excluded_event

    def test_extra_arguments(self):
        # Assert that a value error is raised when trying to call a sampling method with extra arguments
        collection = SourceImageCollection.objects.create(
            name="Test Extra Arguments Collection",
            project=self.project_one,
            method="interval",
            kwargs={"birthday": True, "cake": "chocolate"},
        )
        collection.save()

        with self.assertRaises(TypeError):
            collection.populate_sample()

    def test_last_and_random(self):
        collection = SourceImageCollection.objects.create(
            name="Test Last and Random Collection",
            project=self.project_one,
            method="last_and_random_from_each_event",
            kwargs={"num_each": 2},
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # 2 nights, last image from each, 2 additional random images from each
        self.assertEqual(collection_images.count(), 6)

        for event in self.project_one.events.all():
            last_capture = event.captures.last()
            assert last_capture
            # ensure last_capture is in the collection
            self.assertIn(last_capture, collection_images)
            # ensure there are 2 other random images from each event
            self.assertEqual(collection_images.filter(event=event).exclude(pk=last_capture.pk).count(), 2)

    def test_random_from_each_event(self):
        collection = SourceImageCollection.objects.create(
            name="Test Random From Each Event Collection",
            project=self.project_one,
            method="random_from_each_event",
            kwargs={"num_each": 2},
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # 2 nights, 2 random images from each
        assert collection_images.count() == 4

        # Test that there are 2 images from each event
        for event in self.project_one.events.all():
            assert collection_images.filter(event=event).count() == 2

    def test_common_combined_deployment_ids(self):
        """Test that common_combined sampling method correctly filters by deployment_ids"""
        from ami.main.models import Deployment

        # Create two additional deployments
        deployment_two = Deployment.objects.create(name="Test Deployment Two", project=self.project_one)
        deployment_three = Deployment.objects.create(name="Test Deployment Three", project=self.project_one)

        # Create captures for each deployment
        create_captures(deployment=deployment_two, num_nights=2, images_per_night=10, interval_minutes=1)
        create_captures(deployment=deployment_three, num_nights=2, images_per_night=10, interval_minutes=1)

        # Verify that we have images from the deployments
        assert deployment_two.captures.count() > 0
        assert deployment_three.captures.count() > 0

        # Create collection using only deployment_two and deployment_three
        collection = SourceImageCollection.objects.create(
            name="Test Common Combined Deployment IDs",
            project=self.project_one,
            method="common_combined",
            kwargs={
                "deployment_ids": [deployment_two.pk, deployment_three.pk],
                "shuffle": True,
                "max_num": 100,
            },
        )
        collection.save()
        collection.populate_sample()

        collection_images = collection.images.all()

        # Verify images only come from specified deployments
        self.assertEqual(
            collection_images.filter(deployment__in=[deployment_two, deployment_three]).count(),
            collection_images.count(),
        )
        self.assertEqual(collection_images.filter(deployment=self.deployment).count(), 0)

        # Verify we got images from both specified deployments
        self.assertGreater(collection_images.filter(deployment=deployment_two).count(), 0)
        self.assertGreater(collection_images.filter(deployment=deployment_three).count(), 0)

    def test_interval_sample_multiple_deployments(self):
        """
        Ensure interval sampling applies independently per deployment (station).

        Create two deployments with captures spaced 1 minute apart for a few hours,
        then sample with `minute_interval=60` and verify the total sampled count equals
        the sum of per-deployment hourly samples.
        """
        # Create a new project and two deployments
        project = Project.objects.create(name="Multi Dep Project", create_defaults=False)
        dep1 = Deployment.objects.create(name="Dep One", project=project)
        dep2 = Deployment.objects.create(name="Dep Two", project=project)

        # Create captures: 3 hours worth of captures at 1-minute intervals (~180 images)
        images_per_night = 180
        create_captures(deployment=dep1, num_nights=1, images_per_night=images_per_night, interval_minutes=1)
        create_captures(deployment=dep2, num_nights=1, images_per_night=images_per_night, interval_minutes=1)

        collection = SourceImageCollection.objects.create(
            name="Test Multi-Dep Interval",
            project=project,
            method="interval",
            kwargs={"minute_interval": 60},
        )
        collection.save()
        collection.populate_sample()

        sampled_count = collection.images.count()

        # Compute expected by sampling each deployment separately
        expected = 0
        for dep in [dep1, dep2]:
            qs = SourceImage.objects.filter(deployment=dep).exclude(timestamp=None).order_by("timestamp")
            expected += len(list(sample_captures_by_interval(60, qs)))

        self.assertEqual(sampled_count, expected)
