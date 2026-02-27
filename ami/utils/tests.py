import datetime
from unittest import TestCase
from unittest.mock import Mock

import requests


class TestUtils(TestCase):
    def test_extract_timestamps(self):
        from ami.utils.dates import get_image_timestamp_from_filename

        filenames_and_expected_dates = [
            ("aarhus/20220810231507-00-07.jpg", "2022-08-10 23:15:07"),
            ("diopsis/20230124191342.jpg", "2023-01-24 19:13:42"),
            ("vermont_snapshots/20220622000459-108-snapshot.jpg", "2022-06-22 00:04:59"),
            ("cyprus_snapshots/84-20220916202959-snapshot.jpg", "2022-09-16 20:29:59"),
            ("wingscape/Project_20230801023001_4393.JPG", "2023-08-01 02:30:01"),
            ("nikon/DSC_1974.JPG", None),  # Example with no date
            ("not_a_date/happybirthday.jpg", None),  # Example with no date
            ("cannon/IMG_20230801_123456.jpg", "2023-08-01 12:34:56"),
            ("mothbox/2024_01_01 12_00_00.jpg", "2024-01-01 12:00:00"),
            ("other_common/2024-01-01 12:00:00.jpg", "2024-01-01 12:00:00"),
            ("other_common/2024-01-01T12:00:00.jpg", "2024-01-01 12:00:00"),
            # 2-digit year: YYMMDDHHMMSS (Farmscape/NSCF cameras)
            ("farmscape/NSCF----_250927194802_0017.JPG", "2025-09-27 19:48:02"),
            ("farmscape/NSCF----_251004210001_0041.JPG", "2025-10-04 21:00:01"),
        ]

        for filename, expected_date in filenames_and_expected_dates:
            with self.subTest(filename=filename):
                # Convert the expected date string to a datetime object
                if expected_date is not None:
                    expected_date = datetime.datetime.strptime(expected_date, "%Y-%m-%d %H:%M:%S")
                # Call the function and compare the result with the expected date
                # Only use raise_error=True when we expect a date to be present
                raise_error = expected_date is not None
                result = get_image_timestamp_from_filename(filename, raise_error=raise_error)
                self.assertEqual(
                    result, expected_date, f"Failed for {filename}: expected {expected_date}, got {result}"
                )

    def test_extract_error_message_from_response(self):
        """Test extracting error messages from HTTP responses."""
        from ami.utils.requests import extract_error_message_from_response

        # Test with standard 'detail' field (FastAPI)
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_response.json.return_value = {"detail": "CUDA out of memory"}
        result = extract_error_message_from_response(mock_response)
        self.assertEqual(result, "HTTP 500: Internal Server Error | Detail: CUDA out of memory")

        # Test fallback to non-standard fields
        mock_response.json.return_value = {"error": "Invalid input"}
        result = extract_error_message_from_response(mock_response)
        self.assertIn("error: Invalid input", result)

        # Test fallback to text when JSON fails
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "Service unavailable"
        result = extract_error_message_from_response(mock_response)
        self.assertIn("Response text: Service unavailable", result)

        # Test fallback to raw bytes when text access fails
        mock_response.json.side_effect = ValueError("404 Not Found: Could not fetch image")
        mock_response.text = property(lambda self: (_ for _ in ()).throw(Exception("text error")))
        mock_response.content = b"Raw error bytes"
        result = extract_error_message_from_response(mock_response)
        self.assertIn("Response content: b'Raw error bytes'", result)
