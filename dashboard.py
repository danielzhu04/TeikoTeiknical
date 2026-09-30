#!/usr/bin/env python3
"""Interactive dashboard for the Part 2, 3, and 4 results stored in cell_count.db.

Start it with:

    make dashboard

Then open http://localhost:8501
"""

import sqlite3

from frequencies import DB_PATH, POPULATION_ORDER
from response_comparison import COHORT_SQL, LABELS, POPULATIONS

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

REQUIRED = (
    "sample_frequencies",
    "response_comparisons",
    "baseline_subset_counts",
    "baseline_miraclib_pbmc",
)

QUESTION_LABELS = {
    "samples_per_project": "Samples from each project",
    "subjects_by_response": "Subjects by response",
    "subjects_by_sex": "Subjects by sex",
}


def query(sql, params=()):
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(sql, connection, params=params)


def database_stamp():
    return DB_PATH.stat().st_mtime


@st.cache_data(show_spinner=False)
def table_names(_stamp):
    frame = query("SELECT name FROM sqlite_master")
    return set(frame["name"])


@st.cache_data(show_spinner=False)
def frequency_summary(_stamp):
    frame = query(
        """
        SELECT COUNT(*) AS rows, COUNT(DISTINCT sample) AS samples
        FROM sample_frequencies
        """
    )
    return int(frame.loc[0, "rows"]), int(frame.loc[0, "samples"])


@st.cache_data(show_spinner=False)
def sample_frequencies(sample_id, _stamp):
    return query(
        f"""
        SELECT sample, total_count, population, count, percentage
        FROM sample_frequencies
        WHERE sample = ?
        ORDER BY {POPULATION_ORDER}
        """,
        (sample_id,),
    )


@st.cache_data(show_spinner=False)
def frequency_preview(population, limit, _stamp):
    if population == "All":
        return query(
            f"""
            SELECT sample, total_count, population, count, percentage
            FROM sample_frequencies
            ORDER BY sample, {POPULATION_ORDER}
            LIMIT ?
            """,
            (limit,),
        )
    return query(
        f"""
        SELECT sample, total_count, population, count, percentage
        FROM sample_frequencies
        WHERE population = ?
        ORDER BY sample
        LIMIT ?
        """,
        (population, limit),
    )


@st.cache_data(show_spinner=False)
def response_statistics(_stamp):
    stats = query(
        """
        SELECT *
        FROM response_comparisons
        ORDER BY CASE population
            WHEN 'b_cell' THEN 1
            WHEN 'cd8_t_cell' THEN 2
            WHEN 'cd4_t_cell' THEN 3
            WHEN 'nk_cell' THEN 4
            WHEN 'monocyte' THEN 5
        END
        """
    )
    cohort = query(COHORT_SQL)
    return stats, cohort


@st.cache_data(show_spinner=False)
def baseline_results(_stamp):
    counts = query(
        """
        SELECT question, group_name, n
        FROM baseline_subset_counts
        ORDER BY question, group_name
        """
    )
    samples = query(
        """
        SELECT sample, subject, project, response, sex
        FROM baseline_miraclib_pbmc
        ORDER BY sample
        """
    )
    return counts, samples


def require_database():
    if not DB_PATH.is_file():
        st.error("cell_count.db was not found. Run `make pipeline` first.")
        st.stop()
    missing = [name for name in REQUIRED if name not in table_names(database_stamp())]
    if missing:
        st.error(
            "The database is missing results from the pipeline: "
            + ", ".join(missing)
            + ". Run `make pipeline` first."
        )
        st.stop()


def format_frequencies(frame):
    shown = frame.copy()
    shown["population"] = shown["population"].map(LABELS)
    shown["percentage"] = shown["percentage"].map(lambda value: f"{value:.2f}")
    shown = shown.rename(
        columns={
            "sample": "Sample",
            "total_count": "Total cells",
            "population": "Cell type",
            "count": "Count",
            "percentage": "Percentage",
        }
    )
    return shown


def page_frequencies():
    st.header("Relative frequency of each cell type")
    st.write(
        "For each sample, the five cell counts are added together. "
        "Each percentage is that cell type's count divided by the sample total."
    )
    stamp = database_stamp()
    row_count, sample_count = frequency_summary(stamp)
    left, right = st.columns(2)
    left.metric("Samples", f"{sample_count:,}")
    right.metric("Rows in the summary", f"{row_count:,}")

    st.subheader("Look up one sample")
    sample_id = st.text_input("Sample id", value="sample00000")
    looked_up = sample_frequencies(sample_id.strip(), stamp)
    if looked_up.empty:
        st.warning(f"No sample named {sample_id.strip()} is in the summary.")
    else:
        shown = format_frequencies(looked_up)
        st.dataframe(shown, hide_index=True, width="stretch")
        chart = looked_up.copy()
        chart["Cell type"] = chart["population"].map(LABELS)
        chart = chart.rename(columns={"percentage": "Percentage"})
        st.bar_chart(chart, x="Cell type", y="Percentage")
        total = looked_up["percentage"].sum()
        st.caption(f"These five percentages sum to {total:.2f}.")

    st.subheader("Browse the summary table")
    population = st.selectbox("Cell type", ["All", *POPULATIONS])
    limit = int(st.number_input("Rows to show", min_value=5, max_value=2000, value=25, step=5))
    preview = format_frequencies(frequency_preview(population, limit, stamp))
    st.dataframe(preview, hide_index=True, width="stretch")
    st.caption("This is the first rows of the filtered summary. The full table is in the database view sample_frequencies.")


def boxplot_figure(cohort, stats):
    figure, axes = plt.subplots(1, 5, figsize=(14, 4.8), sharey=True)
    colors = ("#0072B2", "#D55E00")
    significant = dict(zip(stats["population"], stats["significant"].astype(int)))
    for axis, population in zip(axes, POPULATIONS):
        subset = cohort[cohort["population"] == population]
        drawn = axis.boxplot(
            [
                subset.loc[subset["response"] == "yes", "percentage"],
                subset.loc[subset["response"] == "no", "percentage"],
            ],
            tick_labels=["Responder", "Non-responder"],
            patch_artist=True,
            widths=0.6,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch, color in zip(drawn["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
        mark = "*" if significant.get(population) else "n.s."
        axis.set_title(f"{LABELS[population]}\n{mark}")
        axis.tick_params(axis="x", labelrotation=20)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    axes[0].set_ylabel("Relative frequency (%)")
    figure.suptitle(
        "Melanoma, miraclib, PBMC: responders vs non-responders\n"
        "* adjusted p < 0.05; n.s. = not significant. One value per patient."
    )
    figure.tight_layout()
    return figure


def page_comparison():
    st.header("Responders versus non-responders")
    st.write(
        "Melanoma patients treated with miraclib, using PBMC samples only. "
        "Each patient has three PBMC samples, so those three percentages are averaged "
        "and each patient is counted once. A two-sided Mann-Whitney U test is run "
        "for each cell type. The p-values are then adjusted for the five tests. "
        "A cell type is marked significant when the adjusted p-value is below 0.05."
    )
    stats, cohort = response_statistics(database_stamp())
    responders = int(stats["n_responders"].iloc[0])
    non_responders = int(stats["n_non_responders"].iloc[0])
    left, right = st.columns(2)
    left.metric("Responders", responders)
    right.metric("Non-responders", non_responders)

    figure = boxplot_figure(cohort, stats)
    st.pyplot(figure)
    plt.close(figure)

    shown = stats.copy()
    shown["population"] = shown["population"].map(LABELS)
    shown["significant"] = shown["significant"].map(lambda value: "yes" if int(value) else "no")
    for column in (
        "median_responder_pct",
        "median_non_responder_pct",
        "median_difference_pct_points",
    ):
        shown[column] = shown[column].map(lambda value: f"{value:.2f}")
    shown["p_value"] = stats["p_value"].map(lambda value: f"{value:.3g}")
    shown["p_value_adjusted"] = stats["p_value_adjusted"].map(lambda value: f"{value:.3g}")
    shown["u_statistic"] = stats["u_statistic"].map(lambda value: f"{value:.0f}")
    shown = shown.rename(
        columns={
            "population": "Cell type",
            "n_responders": "Responders",
            "n_non_responders": "Non-responders",
            "median_responder_pct": "Responder median (%)",
            "median_non_responder_pct": "Non-responder median (%)",
            "median_difference_pct_points": "Difference (points)",
            "u_statistic": "Mann-Whitney U",
            "p_value": "p-value",
            "p_value_adjusted": "Adjusted p-value",
            "significant": "Significant",
        }
    )
    st.dataframe(shown, hide_index=True, width="stretch")

    significant_names = shown.loc[shown["Significant"] == "yes", "Cell type"].tolist()
    if significant_names:
        st.success("Significant difference: " + ", ".join(significant_names) + ".")
    else:
        st.info("No cell type differed significantly between responders and non-responders.")


def page_baseline():
    st.header("Baseline melanoma samples on miraclib")
    st.write(
        "PBMC samples from melanoma patients treated with miraclib, "
        "taken on day 0. Each person contributes one sample."
    )
    counts, samples = baseline_results(database_stamp())
    st.metric("Samples", f"{len(samples):,}")

    for question, title in QUESTION_LABELS.items():
        subset = counts[counts["question"] == question]
        st.subheader(title)
        columns = st.columns(len(subset))
        for column, (_, row) in zip(columns, subset.iterrows()):
            column.metric(str(row["group_name"]), int(row["n"]))
        chart = subset.rename(columns={"group_name": "Group", "n": "Count"})
        st.bar_chart(chart, x="Group", y="Count")

    st.subheader("Samples in this subset")
    search = st.text_input("Filter by sample, subject, or project", value="")
    filtered = samples
    if search.strip():
        needle = search.strip().lower()
        mask = (
            filtered["sample"].str.lower().str.contains(needle, regex=False)
            | filtered["subject"].str.lower().str.contains(needle, regex=False)
            | filtered["project"].str.lower().str.contains(needle, regex=False)
        )
        filtered = filtered[mask]
    st.caption(f"Showing {len(filtered):,} of {len(samples):,} samples.")
    st.dataframe(filtered, hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="Miraclib cell counts", layout="wide")
    st.title("Miraclib immune cell counts")
    st.caption("Trial results for Bob Loblaw at Loblaw Bio.")
    require_database()
    page = st.sidebar.radio(
        "Results",
        ["Cell frequencies", "Responders vs non-responders", "Baseline subset"],
    )
    if page == "Cell frequencies":
        page_frequencies()
    elif page == "Responders vs non-responders":
        page_comparison()
    else:
        page_baseline()


if __name__ == "__main__":
    main()
