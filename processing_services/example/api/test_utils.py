import pathlib
import tempfile
import unittest
from unittest import mock

from . import utils


class FakeResponse:
    def __init__(self, chunks: list[bytes], content_length: int | None = None, error: Exception | None = None):
        self._chunks = chunks
        self._error = error
        length = sum(len(c) for c in chunks) if content_length is None else content_length
        self.headers = {"content-length": str(length)}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self._chunks
        if self._error:
            raise self._error


class TestGetOrDownloadFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache_root = pathlib.Path(self.tmp.name) / "cache"
        patcher = mock.patch.object(utils, "get_cache_root", return_value=self.cache_root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_local_path_is_returned_without_a_request(self):
        local_file = pathlib.Path(self.tmp.name) / "weights.pth"
        local_file.write_bytes(b"abc")
        with mock.patch.object(utils.requests, "get") as get:
            self.assertEqual(utils.get_or_download_file(str(local_file)), local_file)
            self.assertEqual(utils.get_or_download_file(local_file), local_file)
        get.assert_not_called()

    def test_missing_local_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            utils.get_or_download_file(str(pathlib.Path(self.tmp.name) / "missing.pth"))

    def test_download_uses_a_timeout_and_caches_the_result(self):
        url = "https://example.org/models/weights.pth?token=abc"
        with mock.patch.object(utils.requests, "get", return_value=FakeResponse([b"ab", b"cd"])) as get:
            path = utils.get_or_download_file(url, tempdir_prefix="models")
            again = utils.get_or_download_file(url, tempdir_prefix="models")

        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["timeout"], utils.DOWNLOAD_TIMEOUT)
        self.assertEqual(path.read_bytes(), b"abcd")
        self.assertEqual(path.name, "weights.pth")
        self.assertEqual(again.resolve(), path.resolve())
        self.assertEqual([p.name for p in (self.cache_root / "models").iterdir()], ["weights.pth"])

    def test_interrupted_download_leaves_nothing_in_the_cache(self):
        response = FakeResponse([b"ab"], error=ConnectionError("dropped"))
        with mock.patch.object(utils.requests, "get", return_value=response):
            with self.assertRaises(ConnectionError):
                utils.get_or_download_file("https://example.org/weights.pth", tempdir_prefix="models")
        self.assertEqual(list((self.cache_root / "models").iterdir()), [])

    def test_truncated_download_is_rejected(self):
        response = FakeResponse([b"ab"], content_length=10)
        with mock.patch.object(utils.requests, "get", return_value=response):
            with self.assertRaises(OSError):
                utils.get_or_download_file("https://example.org/weights.pth", tempdir_prefix="models")
        self.assertEqual(list((self.cache_root / "models").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
