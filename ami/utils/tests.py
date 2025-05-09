import datetime
from unittest import TestCase


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
