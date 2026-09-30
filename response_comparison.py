#!/usr/bin/env python3
"""Part 3: responders versus non-responders among melanoma patients on miraclib.

Uses the Part 2 relative frequencies, limited to PBMC samples. Response is a
property of the patient, and every patient in this group has three PBMC samples
(days 0, 7, and 14). Each patient's three percentages are averaged first, then
responders are compared with non-responders.

For each cell type, a two-sided Mann-Whitney U test asks whether the two groups
come from the same distribution. Five cell types are tested, so p-values are
adjusted with the Benjamini-Hochberg method. A difference is called significant
when the adjusted p-value is below 0.05.

Run after load_data.py and frequencies.py:

    python response_comparison.py
"""

import csv
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu

from frequencies import DB_PATH, ROOT, create_frequency_view

OUTPUT_DIR = ROOT / "output"
PLOT_PATH = OUTPUT_DIR / "response_boxplots.png"
STATS_PATH = OUTPUT_DIR / "response_statistics.csv"
FINDINGS_PATH = OUTPUT_DIR / "response_findings.txt"

POPULATIONS = (
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
)

LABELS = {
    "b_cell": "B cell",
    "cd8_t_cell": "CD8 T cell",
    "cd4_t_cell": "CD4 T cell",
    "nk_cell": "NK cell",
    "monocyte": "Monocyte",
}

ALPHA = 0.05

COHORT_SQL = """
SELECT
    sub.subject AS subject,
    sub.response AS response,
    f.population AS population,
    AVG(f.percentage) AS percentage
FROM sample_frequencies AS f
JOIN samples AS s ON s.sample = f.sample
JOIN subjects AS sub ON sub.subject = s.subject
WHERE sub.condition = 'melanoma'
  AND sub.treatment = 'miraclib'
  AND s.sample_type = 'PBMC'
  AND sub.response IN ('yes', 'no')
GROUP BY sub.subject, sub.response, f.population
"""

BASELINE_SQL = """
SELECT
    sub.response AS response,
    f.population AS population,
    f.percentage AS percentage
FROM sample_frequencies AS f
JOIN samples AS s ON s.sample = f.sample
JOIN subjects AS sub ON sub.subject = s.subject
WHERE sub.condition = 'melanoma'
  AND sub.treatment = 'miraclib'
  AND s.sample_type = 'PBMC'
  AND s.time_from_treatment_start = 0
  AND sub.response IN ('yes', 'no')
"""

STATS_COLUMNS = (
    "population",
    "n_responders",
    "n_non_responders",
    "median_responder_pct",
    "median_non_responder_pct",
    "median_difference_pct_points",
    "u_statistic",
    "p_value",
    "p_value_adjusted",
    "significant",
)


def benjamini_hochberg(p_values):
    """Return FDR-adjusted p-values in the same order as p_values."""
    count = len(p_values)
    order = sorted(range(count), key=lambda index: p_values[index])
    raw = [0.0] * count
    for rank, index in enumerate(order, start=1):
        raw[index] = p_values[index] * count / rank
    adjusted = [0.0] * count
    ceiling = 1.0
    for index in reversed(order):
        ceiling = min(ceiling, raw[index])
        adjusted[index] = ceiling
    return adjusted


def median(values):
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def load_cohort(connection):
    rows = connection.execute(COHORT_SQL).fetchall()
    if not rows:
        raise SystemExit("No melanoma PBMC samples for miraclib responders or non-responders.")
    grouped = {population: {"yes": [], "no": []} for population in POPULATIONS}
    for subject, response, population, percentage in rows:
        grouped[population][response].append(percentage)
    return grouped


def compare(grouped):
    results = []
    for population in POPULATIONS:
        responders = grouped[population]["yes"]
        non_responders = grouped[population]["no"]
        statistic, p_value = mannwhitneyu(
            responders,
            non_responders,
            alternative="two-sided",
            method="asymptotic",
        )
        responder_median = median(responders)
        non_responder_median = median(non_responders)
        results.append(
            {
                "population": population,
                "n_responders": len(responders),
                "n_non_responders": len(non_responders),
                "median_responder_pct": responder_median,
                "median_non_responder_pct": non_responder_median,
                "median_difference_pct_points": responder_median - non_responder_median,
                "u_statistic": float(statistic),
                "p_value": float(p_value),
                "responders": responders,
                "non_responders": non_responders,
            }
        )
    adjusted = benjamini_hochberg([row["p_value"] for row in results])
    for row, p_adjusted in zip(results, adjusted):
        row["p_value_adjusted"] = p_adjusted
        row["significant"] = p_adjusted < ALPHA
    return results


def save_statistics(connection, results):
    connection.execute("DROP TABLE IF EXISTS response_comparisons")
    connection.execute(
        """
        CREATE TABLE response_comparisons (
            population TEXT PRIMARY KEY,
            n_responders INTEGER NOT NULL,
            n_non_responders INTEGER NOT NULL,
            median_responder_pct REAL NOT NULL,
            median_non_responder_pct REAL NOT NULL,
            median_difference_pct_points REAL NOT NULL,
            u_statistic REAL NOT NULL,
            p_value REAL NOT NULL,
            p_value_adjusted REAL NOT NULL,
            significant INTEGER NOT NULL
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO response_comparisons (
            population, n_responders, n_non_responders,
            median_responder_pct, median_non_responder_pct,
            median_difference_pct_points, u_statistic,
            p_value, p_value_adjusted, significant
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["population"],
                row["n_responders"],
                row["n_non_responders"],
                row["median_responder_pct"],
                row["median_non_responder_pct"],
                row["median_difference_pct_points"],
                row["u_statistic"],
                row["p_value"],
                row["p_value_adjusted"],
                int(row["significant"]),
            )
            for row in results
        ],
    )
    connection.commit()

    with STATS_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATS_COLUMNS)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "population": row["population"],
                    "n_responders": row["n_responders"],
                    "n_non_responders": row["n_non_responders"],
                    "median_responder_pct": f"{row['median_responder_pct']:.4f}",
                    "median_non_responder_pct": f"{row['median_non_responder_pct']:.4f}",
                    "median_difference_pct_points": f"{row['median_difference_pct_points']:.4f}",
                    "u_statistic": f"{row['u_statistic']:.4f}",
                    "p_value": f"{row['p_value']:.6g}",
                    "p_value_adjusted": f"{row['p_value_adjusted']:.6g}",
                    "significant": "yes" if row["significant"] else "no",
                }
            )


def baseline_summary(connection):
    """Day 0 only: the frequencies available before treatment could predict response."""
    grouped = {population: {"yes": [], "no": []} for population in POPULATIONS}
    for response, population, percentage in connection.execute(BASELINE_SQL):
        grouped[population][response].append(percentage)
    results = compare(grouped)
    closest = min(results, key=lambda row: row["p_value"])
    return (
        "At baseline (day 0), before treatment could change the blood sample, "
        "no cell type differed after the same adjustment. The smallest unadjusted "
        f"p-value was {closest['p_value']:.3g} for {LABELS[closest['population']]}."
    )


def write_findings(results, baseline_line):
    first = results[0]
    lines = [
        "Melanoma patients treated with miraclib, PBMC samples only.",
        (
            f"{first['n_responders']} responders and {first['n_non_responders']} "
            "non-responders. Each person contributes three PBMC samples "
            "(days 0, 7, and 14). Those three relative frequencies were averaged "
            "before comparing groups, so each person is counted once."
        ),
        (
            "Test: two-sided Mann-Whitney U on the patient averages, for each cell type. "
            "P-values are adjusted across the five cell types with Benjamini-Hochberg. "
            f"A cell type is significant when the adjusted p-value is below {ALPHA}."
        ),
        "",
    ]
    significant = []
    not_significant = []
    for row in results:
        name = LABELS[row["population"]]
        direction = "higher" if row["median_difference_pct_points"] > 0 else "lower"
        sentence = (
            f"{name}: responders' median is {row['median_responder_pct']:.2f}% "
            f"versus {row['median_non_responder_pct']:.2f}% in non-responders "
            f"({abs(row['median_difference_pct_points']):.2f} percentage points {direction} "
            f"in responders). U = {row['u_statistic']:.0f}, "
            f"p = {row['p_value']:.3g}, adjusted p = {row['p_value_adjusted']:.3g}."
        )
        lines.append(sentence)
        if row["significant"]:
            significant.append(name)
        else:
            not_significant.append(name)
    lines.append("")
    if significant:
        lines.append(
            "Significant difference between responders and non-responders: "
            + ", ".join(significant)
            + "."
        )
    else:
        lines.append("No cell type differed significantly between responders and non-responders.")
    if not_significant:
        lines.append("No significant difference: " + ", ".join(not_significant) + ".")
    lines.append(baseline_line)
    text = "\n".join(lines) + "\n"
    FINDINGS_PATH.write_text(text)
    return text


def save_boxplots(results):
    figure, axes = plt.subplots(1, 5, figsize=(14, 4.8), sharey=True)
    colors = ("#0072B2", "#D55E00")
    for axis, row in zip(axes, results):
        drawn = axis.boxplot(
            [row["responders"], row["non_responders"]],
            tick_labels=["Responder", "Non-responder"],
            patch_artist=True,
            widths=0.6,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch, color in zip(drawn["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
        mark = "*" if row["significant"] else "n.s."
        axis.set_title(f"{LABELS[row['population']]}\n{mark}")
        axis.tick_params(axis="x", labelrotation=20)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    axes[0].set_ylabel("Relative frequency (%)")
    figure.suptitle(
        "Melanoma, miraclib, PBMC: responders vs non-responders\n"
        "* adjusted p < 0.05; n.s. = not significant. One value per patient."
    )
    figure.tight_layout()
    figure.savefig(PLOT_PATH, dpi=150)
    plt.close(figure)


def main():
    if not DB_PATH.is_file():
        raise SystemExit("cell_count.db was not found. Run python load_data.py first.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    try:
        create_frequency_view(connection)
        grouped = load_cohort(connection)
        results = compare(grouped)
        save_statistics(connection, results)
        findings = write_findings(results, baseline_summary(connection))
        save_boxplots(results)
    finally:
        connection.close()
    print(findings)
    print(f"Statistics table: {STATS_PATH.relative_to(ROOT)}")
    print(f"Boxplots: {PLOT_PATH.relative_to(ROOT)}")
    print("Database table: response_comparisons in cell_count.db")


if __name__ == "__main__":
    main()
