#!/usr/bin/env python3
"""Part 2: relative frequency of each immune cell population in each sample.

For every sample, the total cell count is the sum of the five populations.
Each population's percentage is its count divided by that total x 100.
The result is one row per population per sample, saved as the
sample_frequencies view inside cell_count.db and as a CSV.

Run after load_data.py:

    python frequencies.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cell_count.db"
OUTPUT_PATH = ROOT / "output" / "sample_frequencies.csv"

POPULATION_ORDER = """
CASE population
    WHEN 'b_cell' THEN 1
    WHEN 'cd8_t_cell' THEN 2
    WHEN 'cd4_t_cell' THEN 3
    WHEN 'nk_cell' THEN 4
    WHEN 'monocyte' THEN 5
    ELSE 6
END
"""

COLUMNS = ("sample", "total_count", "population", "count", "percentage")

VIEW_SQL = """
DROP VIEW IF EXISTS sample_frequencies;

CREATE VIEW sample_frequencies AS
SELECT
    c.sample AS sample,
    t.total_count AS total_count,
    c.population AS population,
    c.count AS count,
    (100.0 * c.count / t.total_count) AS percentage
FROM cell_counts AS c
JOIN (
    SELECT sample, SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample
) AS t ON t.sample = c.sample;
"""

FREQUENCY_SQL = f"""
SELECT sample, total_count, population, count, percentage
FROM sample_frequencies
ORDER BY sample, {POPULATION_ORDER}
"""


def connect():
    if not DB_PATH.is_file():
        raise SystemExit("cell_count.db was not found. Run python load_data.py first.")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_frequency_view(connection):
    connection.executescript(VIEW_SQL)


def write_frequency_table(connection):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = connection.execute(FREQUENCY_SQL)
    with OUTPUT_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        count = 0
        for row in rows:
            writer.writerow(
                [
                    row["sample"],
                    row["total_count"],
                    row["population"],
                    row["count"],
                    f"{row['percentage']:.6f}",
                ]
            )
            count += 1
    return count


def preview(connection, samples=2):
    limit = samples * 5
    rows = connection.execute(FREQUENCY_SQL + f"\nLIMIT {limit}").fetchall()
    headers = COLUMNS
    rendered = []
    for row in rows:
        rendered.append(
            [
                row["sample"],
                str(row["total_count"]),
                row["population"],
                str(row["count"]),
                f"{row['percentage']:.2f}",
            ]
        )
    widths = [
        max(len(header), *(len(values[index]) for values in rendered))
        for index, header in enumerate(headers)
    ]
    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    print(header_line)
    print("  ".join("-" * width for width in widths))
    for values in rendered:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(values)))


def check_percentages(connection):
    off = connection.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT sample
            FROM sample_frequencies
            GROUP BY sample
            HAVING ABS(SUM(percentage) - 100) > 0.000001
        )
        """
    ).fetchone()[0]
    sample_count = connection.execute(
        "SELECT COUNT(DISTINCT sample) FROM sample_frequencies"
    ).fetchone()[0]
    return sample_count, off


def main():
    connection = connect()
    try:
        create_frequency_view(connection)
        row_count = write_frequency_table(connection)
        sample_count, off = check_percentages(connection)
        print(f"Wrote {row_count} rows to {OUTPUT_PATH.relative_to(ROOT)}")
        print(f"View sample_frequencies covers {sample_count} samples.")
        if off:
            raise SystemExit(f"{off} samples do not sum to 100%.")
        print("Each sample's five percentages sum to 100.")
        print()
        print("First two samples:")
        preview(connection)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
