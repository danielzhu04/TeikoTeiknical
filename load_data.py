#!/usr/bin/env python3
"""Create the cell-count SQLite database and load cell-count.csv.

Each CSV row is one biological sample. Subject attributes (project, condition,
age, sex, treatment, response) do not change across a subject's samples, so
they live on the subjects table. Each sample is one row in samples. The five
immune cell counts are stored as one row per population in cell_counts.

Run from anywhere:

    python load_data.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "cell-count.csv"
DB_PATH = ROOT / "cell_count.db"

POPULATIONS = (
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
)

SCHEMA = """
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS sample_frequencies;
DROP TABLE IF EXISTS cell_counts;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS populations;

-- The five cell types: b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte
CREATE TABLE populations (
    population TEXT PRIMARY KEY
);

-- One row per person: project, condition, age, sex, treatment, and response
-- (yes, no, or empty for healthy)
CREATE TABLE subjects (
    subject TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    condition TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0),
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    treatment TEXT NOT NULL,
    response TEXT CHECK (response IN ('yes', 'no'))
);

-- One row per sample: sample id, which person it came from,
-- sample type (PBMC or whole blood), and days since treatment started
CREATE TABLE samples (
    sample TEXT PRIMARY KEY,
    subject TEXT NOT NULL REFERENCES subjects(subject),
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL
);

-- One row per cell type per sample, with that type's count
CREATE TABLE cell_counts (
    sample TEXT NOT NULL REFERENCES samples(sample),
    population TEXT NOT NULL REFERENCES populations(population),
    count INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample, population)
);

CREATE INDEX idx_samples_subject ON samples(subject);
CREATE INDEX idx_samples_type_time ON samples(sample_type, time_from_treatment_start);
CREATE INDEX idx_subjects_cohort ON subjects(condition, treatment, response, sex, project);
CREATE INDEX idx_cell_counts_population ON cell_counts(population);
"""


def _response(value):
    text = (value or "").strip()
    return text if text else None


def load_rows(csv_path):
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in ("project", "subject", "condition", "age", "sex", "treatment", "response", "sample", "sample_type", "time_from_treatment_start", *POPULATIONS) if name not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"cell-count.csv is missing columns: {', '.join(missing)}")

        subjects = {}
        samples = []
        counts = []
        for row in reader:
            subject = row["subject"]
            meta = (
                subject,
                row["project"],
                row["condition"],
                int(row["age"]),
                row["sex"],
                row["treatment"],
                _response(row["response"]),
            )
            previous = subjects.get(subject)
            if previous is None:
                subjects[subject] = meta
            elif previous != meta:
                raise SystemExit(f"Subject {subject} has conflicting metadata")

            sample = row["sample"]
            samples.append(
                (
                    sample,
                    subject,
                    row["sample_type"],
                    int(row["time_from_treatment_start"]),
                )
            )
            for population in POPULATIONS:
                counts.append((sample, population, int(row[population])))

    return list(subjects.values()), samples, counts


def main():
    if not CSV_PATH.is_file():
        raise SystemExit(f"Could not find {CSV_PATH}")

    subjects, samples, counts = load_rows(CSV_PATH)

    if DB_PATH.exists():
        DB_PATH.unlink()

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO populations (population) VALUES (?)",
            [(population,) for population in POPULATIONS],
        )
        connection.executemany(
            """
            INSERT INTO subjects (
                subject, project, condition, age, sex, treatment, response
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            subjects,
        )
        connection.executemany(
            """
            INSERT INTO samples (
                sample, subject, sample_type, time_from_treatment_start
            ) VALUES (?, ?, ?, ?)
            """,
            samples,
        )
        connection.executemany(
            """
            INSERT INTO cell_counts (sample, population, count)
            VALUES (?, ?, ?)
            """,
            counts,
        )
        connection.commit()
    finally:
        connection.close()

    print(f"Wrote {DB_PATH.name}")
    print(f"  subjects:    {len(subjects)}")
    print(f"  samples:     {len(samples)}")
    print(f"  cell_counts: {len(counts)}")


if __name__ == "__main__":
    main()
