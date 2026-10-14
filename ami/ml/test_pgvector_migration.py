"""The pgvector extension migration (ml/0030): it refuses a missing or outdated server package with one
clear message, and only upgrades an extension installed below the minimum version."""

import importlib
from unittest import mock

from django.test import SimpleTestCase


class TestPgvectorGuard(SimpleTestCase):
    """The extension migration stops with one clear message unless the server offers pgvector 0.8+,
    and only upgrades an extension that is installed below 0.8."""

    @staticmethod
    def _run(row, step="check_pgvector_is_installed"):
        migration = importlib.import_module("ami.ml.migrations.0030_enable_pgvector")
        cursor = mock.MagicMock()
        cursor.__enter__.return_value.fetchone.return_value = row
        schema_editor = mock.Mock()
        schema_editor.connection.cursor.return_value = cursor
        getattr(migration, step)(apps=None, schema_editor=schema_editor)
        return [call.args[0] for call in cursor.__enter__.return_value.execute.call_args_list]

    def test_a_missing_or_old_package_is_refused_and_a_current_one_passes(self):
        with self.assertRaisesRegex(RuntimeError, "not installed"):
            self._run(None)
        with self.assertRaisesRegex(RuntimeError, "found 0.7.4"):
            self._run(("0.7.4",))
        self._run(("0.8.6",))
        self._run(("1.0.0",))

    def test_only_an_extension_installed_below_the_minimum_is_upgraded(self):
        # ALTER EXTENSION ... UPDATE needs ownership even when nothing changes, so a current
        # extension an administrator created must not be touched.
        update = "ALTER EXTENSION vector UPDATE"
        self.assertIn(update, self._run(("0.5.1",), step="update_pgvector_if_older"))
        self.assertNotIn(update, self._run(("0.8.7",), step="update_pgvector_if_older"))
