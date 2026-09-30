#!/usr/bin/env python3
"""Part 4: melanoma PBMC samples at baseline for patients treated with miraclib.

Baseline means time_from_treatment_start is 0. The script saves every matching
sample, then counts:

- samples in each project
- subjects who responded and who did not
- how many subjects were male/female

Run after load_data.py:

    python baseline_subset.py
"""

import csv
import sqlite3
from pathlib import Path

from frequencies import DB_PATH, ROOT

OUTPUT_DIR = ROOT / "output"
SAMPLES_PATH = OUTPUT_DIR / "baseline_miraclib_pbmc.csv"
COUNTS_PATH = OUTPUT_DIR / "baseline_subset_counts.csv"
FINDINGS_PATH = OUTPUT_DIR / "baseline_subset_findings.txt"

FILTER_SQL = """
SELECT
    s.sample AS sample,
    sub.subject AS subject,
    sub.project AS project,
    sub.response AS response,
    sub.sex AS sex
FROM samples AS s
JOIN subjects AS sub ON sub.subject = s.subject
WHERE sub.condition = 'melanoma'
  AND sub.treatment = 'miraclib'
  AND s.sample_type = 'PBMC'
  AND s.time_from_treatment_start = 0
"""

SAMPLE_COLUMNS = ("sample", "subject", "project", "response", "sex")


def connect():
    if not DB_PATH.is_file():
        raise SystemExit("cell_count.db was not found. Run python load_data.py first.")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def save_samples(connection):
    rows = connection.execute(FILTER_SQL + " ORDER BY s.sample").fetchall()
    if not rows:
        raise SystemExit("No baseline melanoma PBMC samples for miraclib were found.")

    connection.execute("DROP TABLE IF EXISTS baseline_miraclib_pbmc")
    connection.execute(
        """
        CREATE TABLE baseline_miraclib_pbmc (
            sample TEXT PRIMARY KEY,
            subject TEXT NOT NULL UNIQUE,
            project TEXT NOT NULL,
            response TEXT,
            sex TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO baseline_miraclib_pbmc (sample, subject, project, response, sex)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (row["sample"], row["subject"], row["project"], row["response"], row["sex"])
            for row in rows
        ],
    )
    connection.commit()

    with SAMPLES_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(SAMPLE_COLUMNS)
        for row in rows:
            writer.writerow([row[column] for column in SAMPLE_COLUMNS])
    return rows


def count_rows(connection, sql):
    return [(row[0], row[1]) for row in connection.execute(sql)]


def save_counts(connection):
    project_counts = count_rows(
        connection,
        """
        SELECT projects.project, COUNT(b.sample)
        FROM (SELECT DISTINCT project FROM subjects) AS projects
        LEFT JOIN baseline_miraclib_pbmc AS b ON b.project = projects.project
        GROUP BY projects.project
        ORDER BY projects.project
        """,
    )
    response_counts = count_rows(
        connection,
        """
        SELECT
            CASE response
                WHEN 'yes' THEN 'responder'
                WHEN 'no' THEN 'non-responder'
                ELSE 'unknown'
            END,
            COUNT(*)
        FROM baseline_miraclib_pbmc
        GROUP BY response
        ORDER BY response
        """,
    )
    sex_counts = count_rows(
        connection,
        """
        SELECT
            CASE sex
                WHEN 'F' THEN 'female'
                WHEN 'M' THEN 'male'
                ELSE sex
            END,
            COUNT(*)
        FROM baseline_miraclib_pbmc
        GROUP BY sex
        ORDER BY sex
        """,
    )

    grouped = (
        ("samples_per_project", project_counts),
        ("subjects_by_response", response_counts),
        ("subjects_by_sex", sex_counts),
    )
    connection.execute("DROP TABLE IF EXISTS baseline_subset_counts")
    connection.execute(
        """
        CREATE TABLE baseline_subset_counts (
            question TEXT NOT NULL,
            group_name TEXT NOT NULL,
            n INTEGER NOT NULL,
            PRIMARY KEY (question, group_name)
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO baseline_subset_counts (question, group_name, n)
        VALUES (?, ?, ?)
        """,
        [
            (question, name, count)
            for question, pairs in grouped
            for name, count in pairs
        ],
    )
    connection.commit()

    with COUNTS_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("question", "group_name", "n"))
        for question, pairs in grouped:
            for name, count in pairs:
                writer.writerow((question, name, count))
    return project_counts, response_counts, sex_counts


def write_findings(sample_count, project_counts, response_counts, sex_counts):
    lines = [
        "Melanoma PBMC samples at baseline (day 0) from patients treated with miraclib.",
        f"{sample_count} samples from {sample_count} subjects. Each subject has one sample in this subset.",
        "",
        "Samples from each project:",
    ]
    for name, count in project_counts:
        lines.append(f"  {name}: {count}")
    lines.append("")
    lines.append("Subjects by response:")
    for name, count in response_counts:
        lines.append(f"  {name}: {count}")
    lines.append("")
    lines.append("Subjects by sex:")
    for name, count in sex_counts:
        lines.append(f"  {name}: {count}")
    text = "\n".join(lines) + "\n"
    FINDINGS_PATH.write_text(text)
    return text


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection = connect()
    try:
        rows = save_samples(connection)
        project_counts, response_counts, sex_counts = save_counts(connection)
        findings = write_findings(len(rows), project_counts, response_counts, sex_counts)
    finally:
        connection.close()
    print(findings)
    print(f"Sample list: {SAMPLES_PATH.relative_to(ROOT)}")
    print(f"Counts: {COUNTS_PATH.relative_to(ROOT)}")
    print("Database tables: baseline_miraclib_pbmc, baseline_subset_counts")


if __name__ == "__main__":
    main()
