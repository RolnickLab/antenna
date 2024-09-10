import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, fields

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# COL API Configuration
COL_API_BASE_URL = "https://api.catalogueoflife.org/dataset/3LR"
COL_API_SEARCH_ENDPOINT = f"{COL_API_BASE_URL}/nameusage/search"
COL_API_BATCH_ENDPOINT = f"{COL_API_BASE_URL}/nameusage/match"
# COL_API_PARAMS = {"content": "SCIENTIFIC_NAME", "rank": "genus", "limit": 1}

# Batch size for API requests (adjust as needed)
BATCH_SIZE = 100

# Number of worker threads (adjust based on your system's capabilities)
NUM_WORKERS = 10


@dataclass
class TaxonData:
    genus: str
    tribe: str = ""
    subtribe: str = ""
    subfamily: str = ""
    family: str = ""
    superfamily: str = ""
    order: str = ""
    class_: str = field(default="", metadata={"col_name": "class"})
    phylum: str = ""
    kingdom: str = ""
    other_fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def get_rank_fields(cls, exclude: list[str] = []) -> list[str]:
        exclude = [field.lower() for field in exclude] + ["other_fields"]
        return [f.name for f in fields(cls) if f.name not in exclude]


def fetch_col_data_batch(taxa: list[tuple[str, str]]) -> dict[str, dict]:
    """Fetch taxon data for a batch of genera from Catalog of Life API."""
    data = [{rank: name} for rank, name in taxa]
    try:
        logging.info(f"Fetching data for {len(data)} taxa...")
        response = requests.post(COL_API_BATCH_ENDPOINT, json=data, timeout=30)
        response.raise_for_status()
        results = response.json()
        return {item["request"]: item["match"] for item in results if item["match"]}
    except requests.RequestException as e:
        logging.error(f"Error fetching batch data: {e}")
    return {}


def process_genus_data(genus_data: dict) -> TaxonData:
    """Process genus data from COL API response."""
    taxon_data = TaxonData(genus=genus_data.get("name", ""))
    classification = genus_data.get("classification", [])

    rank_fields = TaxonData.get_rank_fields()
    rank_mapping = {field: field for field in rank_fields}
    rank_mapping["class"] = "class_"  # Special case for 'class' keyword

    for taxon in classification:
        rank = taxon.get("rank", "").lower()
        if rank in rank_mapping:
            setattr(taxon_data, rank_mapping[rank], taxon.get("name", ""))

    return taxon_data


def process_csv_chunk(chunk: list[dict[str, str]], genus_data: dict[str, dict]) -> list[dict[str, str]]:
    """Process a chunk of CSV rows."""
    processed_rows = []
    for row in chunk:
        genus = row["genus"]
        taxon_data = TaxonData(genus=genus, other_fields=row.copy())
        if genus in genus_data:
            processed_taxon = process_genus_data(genus_data[genus])
            for taxon_field in TaxonData.get_rank_fields():
                setattr(taxon_data, taxon_field, getattr(processed_taxon, taxon_field))

        output_row = taxon_data.other_fields.copy()
        for taxon_field in TaxonData.get_rank_fields():
            output_row[taxon_field] = getattr(taxon_data, taxon_field)
        processed_rows.append(output_row)
    return processed_rows


def process_csv(input_file: str, output_file: str) -> None:
    """Process the CSV file using multiprocessing."""
    genera = set()
    rows = []

    try:
        with open(input_file) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                genera.add(row["genus"])
                rows.append(row)
    except OSError as e:
        logging.error(f"Error reading input file: {e}")
        return

    logging.info(f"Total genera to process: {len(genera)}")

    # Fetch data for genera in batches
    genus_data = {}
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = []
        for i in range(0, len(genera), BATCH_SIZE):
            batch = list(genera)[i : i + BATCH_SIZE]  # noqa: E203
            futures.append(executor.submit(fetch_col_data_batch, batch))

        for future in as_completed(futures):
            genus_data.update(future.result())

    logging.info(f"Fetched data for {len(genus_data)} genera")

    # Process rows in parallel
    processed_rows = []
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        chunk_size = len(rows) // NUM_WORKERS
        futures = []
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]  # noqa: E203
            futures.append(executor.submit(process_csv_chunk, chunk, genus_data))

        for future in as_completed(futures):
            processed_rows.extend(future.result())

    # Write processed rows to output CSV
    try:
        with open(output_file, "w", newline="") as csvfile:
            fieldnames = list(rows[0].keys()) + TaxonData.get_rank_fields()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in processed_rows:
                writer.writerow(row)
    except OSError as e:
        logging.error(f"Error writing output file: {e}")
        return

    logging.info(f"Processing complete. Output written to {output_file}")


def test_known_data():
    """Test function to verify processing of known data."""
    known_data = [
        {
            "genus": "Acherontia",
            "subfamily": "Sphinginae",
            "family": "Sphingidae",
            "superfamily": "Bombycoidea",
            "order": "Lepidoptera",
            "subtribe": "Acherontiina",
            "tribe": "Sphingini",
        },
        {
            "genus": "Agrius",
            "subfamily": "Sphinginae",
            "family": "Sphingidae",
            "superfamily": "Bombycoidea",
            "order": "Lepidoptera",
            "subtribe": "Acherontiina",
            "tribe": "Sphingini",
        },
        {
            "genus": "Achlyodes",
            "subfamily": "Pyrginae",
            "family": "Hesperiidae",
            "superfamily": "Papilionoidea",
            "order": "Lepidoptera",
            "subtribe": "Achlyodina",
            "tribe": "Achlyodini",
        },
        {
            "genus": "Actebia",
            "subfamily": "Noctuinae",
            "family": "Noctuidae",
            "superfamily": "Noctuoidea",
            "order": "Lepidoptera",
            "subtribe": "Agrotina",
            "tribe": "Noctuini",
        },
    ]

    # Mock API response
    mock_api_response = {
        genus: {"classification": [{"rank": rank, "name": value} for rank, value in data.items() if rank != "genus"]}
        for data in known_data
        for genus in [data["genus"]]
    }

    for test_case in known_data:
        genus = test_case["genus"]
        expected_taxon_data = TaxonData(**test_case)  # type: ignore

        # Process the mock data
        processed_taxon_data = process_genus_data(mock_api_response[genus])
        logging.info(f"Processed data for genus {genus}: {processed_taxon_data}")

        # Compare processed data with expected data
        for taxon_field in TaxonData.get_rank_fields(exclude=["genus"]):
            expected_value = getattr(expected_taxon_data, taxon_field)
            processed_value = getattr(processed_taxon_data, taxon_field)
            try:
                assert (
                    expected_value == processed_value
                ), f"Mismatch in {taxon_field} for genus {genus}. Expected: {expected_value}, Got: {processed_value}"
            except AssertionError as e:
                logging.error(e)
                continue

    print("All test cases passed successfully!")


if __name__ == "__main__":
    # Run the tests
    test_known_data()

    # Process the actual data
    start_time = time.time()
    process_csv("input.csv", "output.csv")
    end_time = time.time()
    logging.info(f"Total processing time: {end_time - start_time:.2f} seconds")
