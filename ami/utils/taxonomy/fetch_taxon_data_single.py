from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass
class Taxon:
    name: str
    rank: str


@dataclass
class TaxonData:
    genus: str
    tribe: str = ""
    subfamily: str = ""
    superfamily: str = ""
    other_fields: dict[str, str] = field(default_factory=dict)


def fetch_col_data(genus: str) -> dict | None:
    """Fetch taxon data from Catalog of Life API."""
    url = f"https://api.catalogueoflife.org/dataset/3LR/nameusage/search?q={genus}&content=SCIENTIFIC_NAME&rank=genus&limit=1"  # noqa
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["result"] and len(data["result"]) > 0:
            return data["result"][0]
    except requests.RequestException as e:
        logging.error(f"Error fetching data for genus {genus}: {e}")
    except (KeyError, IndexError) as e:
        logging.error(f"Error parsing data for genus {genus}: {e}")
    return None


def process_row(row: dict[str, str], genus_data: dict[str, dict]) -> TaxonData:
    """Process a single row of data."""
    taxon_data = TaxonData(genus=row["genus"], other_fields=row.copy())
    if taxon_data.genus in genus_data:
        col_data = genus_data[taxon_data.genus]
        classification = col_data.get("classification", [])

        for taxon in classification:
            rank = taxon.get("rank", "").lower()
            if rank == "tribe":
                taxon_data.tribe = taxon.get("name", "")
            elif rank == "subfamily":
                taxon_data.subfamily = taxon.get("name", "")
            elif rank == "superfamily":
                taxon_data.superfamily = taxon.get("name", "")

    return taxon_data


def process_csv(input_file: str, output_file: str) -> None:
    """Process the CSV file."""
    genera: set[str] = set()
    rows: list[dict[str, str]] = []

    try:
        with open(input_file) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                genera.add(row["genus"])
                rows.append(row)
    except OSError as e:
        logging.error(f"Error reading input file: {e}")
        return

    # Fetch data for each genus
    genus_data: dict[str, dict] = {}
    for genus in genera:
        logging.info(f"Fetching data for genus: {genus}")
        col_data = fetch_col_data(genus)
        if col_data:
            genus_data[genus] = col_data

    # Process rows and write to output CSV
    try:
        with open(output_file, "w", newline="") as csvfile:
            fieldnames = list(rows[0].keys()) + ["tribe", "subfamily", "superfamily"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for row in rows:
                processed_row = process_row(row, genus_data)
                writer.writerow(
                    {
                        **processed_row.other_fields,
                        "tribe": processed_row.tribe,
                        "subfamily": processed_row.subfamily,
                        "superfamily": processed_row.superfamily,
                    }
                )
    except OSError as e:
        logging.error(f"Error writing output file: {e}")
        return

    logging.info(f"Processing complete. Output written to {output_file}")


def test_genus_processing() -> None:
    """Test function for genus processing."""
    test_genera = {
        "Bombus": Taxon(name="Bombus", rank="genus"),
        "Lophocampa": Taxon(name="Lophocampa", rank="genus"),
    }

    expected_results = {
        "Bombus": TaxonData(genus="Bombus", tribe="Bombini", subfamily="Apinae", superfamily="Apoidea"),
        "Lophocampa": TaxonData(genus="Lophocampa", tribe="Arctiini", subfamily="Arctiinae", superfamily="Noctuoidea"),
    }

    for genus, taxon in test_genera.items():
        logging.info(f"Testing genus: {genus}")
        col_data = fetch_col_data(genus)
        if col_data:
            processed_data = process_row({"genus": genus}, {genus: col_data})
            logging.info(f"Taxon data received: {processed_data}")
            expected = expected_results[genus]

            assert processed_data.tribe == expected.tribe, f"Tribe mismatch for {genus}"
            assert processed_data.subfamily == expected.subfamily, f"Subfamily mismatch for {genus}"
            assert processed_data.superfamily == expected.superfamily, f"Superfamily mismatch for {genus}"

            logging.info(f"Test passed for {genus}")
        else:
            logging.error(f"Failed to fetch data for {genus}")

    logging.info("All tests passed successfully!")


if __name__ == "__main__":
    try:
        test_genus_processing()
        # After tests pass, you can process your actual data
        # process_csv('input.csv', 'output.csv')
    except AssertionError as e:
        logging.error(f"Test failed: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
