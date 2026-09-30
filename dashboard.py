#!/usr/bin/env python3
"""Interactive dashboard for the Part 2, 3, and 4 results stored in cell_count.db.

Start it with:

    make dashboard

Then open http://localhost:8501
"""

import sqlite3

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from frequencies import DB_PATH, POPULATION_ORDER
from response_comparison import COHORT_SQL, LABELS, POPULATIONS

REQUIRED = (
    "sample_frequencies",
    "response_comparisons",
    "baseline_subset_counts",
    "baseline_miraclib_pbmc",
)

QUESTION_LABELS = {
    "samples_per_project": "Project",
    "subjects_by_response": "Response",
    "subjects_by_sex": "Sex",
}

GROUP_LABELS = {
    "prj1": "Project 1",
    "prj2": "Project 2",
    "prj3": "Project 3",
    "responder": "Responder",
    "non-responder": "Non-responder",
    "female": "Female",
    "male": "Male",
}

PLOT_BLUE = "#6FA0D8"
PLOT_BLUE_DARK = "#2F5F93"

CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap");

html, body, .stApp, [data-testid="stMarkdownContainer"], [data-testid="stMetric"] {
    font-family: "IBM Plex Sans", sans-serif;
}

[data-testid="stIconMaterial"],
.material-icons,
.material-symbols-rounded,
.material-symbols-outlined {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
    font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
    letter-spacing: 0;
}

.stApp, [data-testid="stAppViewContainer"] {
    background: #F4F5F7;
}

[data-testid="stHeader"] {
    background: #F4F5F7;
    height: 3.25rem;
}
[data-testid="stMain"],
[data-testid="stSidebarContent"] {
    overflow-y: auto;
}

[data-testid="stSidebar"] {
    background: #F7F8FA;
    border-right: 1px solid #E6E8EC;
}
[data-testid="stSidebar"] > div:first-child {
    width: 15.5rem;
}
.brand {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1F2430;
    margin: 0.2rem 0 0;
}
.brand-sub, .nav-section {
    color: #8B93A1;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 1.1rem 0 0.35rem;
}
.brand-sub {
    margin: 0.15rem 0 0.4rem;
    letter-spacing: 0.04em;
    text-transform: none;
    font-weight: 500;
    font-size: 0.78rem;
}
.side-nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}
.side-nav a {
    display: block;
    text-decoration: none;
    color: #3A4250;
    border-radius: 8px;
    font-weight: 500;
    padding: 0.5rem 0.7rem;
}
.side-nav a:hover {
    background: #EEF0F3;
    color: #1F2430;
}
.side-nav a.active {
    background: #FDECEE;
    color: #D3122A;
}

.context {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.7rem;
    align-items: baseline;
    color: #1F2430;
    font-size: 0.92rem;
}
.context em {
    color: #D3122A;
    font-style: normal;
    font-weight: 600;
    margin-right: 0.28rem;
}
.context .sep {
    color: #C5CAD3;
}

.panel-title {
    text-align: center;
    font-size: 1.05rem;
    font-weight: 650;
    color: #1F2430;
    margin: 0.15rem 0 0.6rem;
}

[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E6E8EC;
    border-radius: 10px;
    padding: 0.55rem 0.8rem;
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem;
    color: #6B7280;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem;
    color: #1F2430;
}

div[data-testid="stAlert"] {
    border-radius: 10px;
}

[data-testid="stDataFrame"] {
    border: 1px solid #ECEEF2;
    border-radius: 8px;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    overflow: visible;
    scroll-margin-top: 4.5rem;
}

.section-anchor {
    scroll-margin-top: 4.5rem;
    height: 0;
}

.section-gap {
    height: 1.75rem;
}

.block-container {
    padding-top: 4.5rem;
    padding-bottom: 4rem;
    max-width: 1240px;
}
</style>
"""


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


def add_cell_labels(frame):
    labeled = frame.copy()
    labeled["Cell type"] = labeled["population"].map(LABELS)
    return labeled


def format_frequencies(frame):
    shown = add_cell_labels(frame)
    shown["percentage"] = shown["percentage"].map(lambda value: f"{float(value):.2f}")
    shown = shown.rename(
        columns={
            "sample": "Sample",
            "total_count": "Total cells",
            "count": "Count",
            "percentage": "Percentage",
        }
    )
    return shown[["Sample", "Total cells", "Cell type", "Count", "Percentage"]]


def chart_theme(chart):
    return (
        chart.configure_view(stroke=None)
        .configure_axis(
            gridColor="#EEF0F3",
            domainColor="#D5D8DE",
            labelColor="#3A4250",
            titleColor="#6B7280",
            labelFontSize=11,
            titleFontSize=11,
        )
        .configure_header(labelColor="#1F2430", labelFontSize=13, labelFontWeight="bold")
    )


def frequency_chart(frame):
    chart_data = add_cell_labels(frame)
    order = [LABELS[name] for name in POPULATIONS]
    chart = (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusEnd=3, size=18, color=PLOT_BLUE)
        .encode(
            x=alt.X("percentage:Q", title="Percent of sample", scale=alt.Scale(domain=[0, 40])),
            y=alt.Y("Cell type:N", sort=order, title=None),
            tooltip=[
                alt.Tooltip("Cell type:N"),
                alt.Tooltip("count:Q", title="Count", format=","),
                alt.Tooltip("percentage:Q", title="Percentage", format=".2f"),
            ],
        )
        .properties(height=230)
    )
    return chart_theme(chart)


BOX_WIDTH = 42


def boxplot_chart(cohort):
    plot = add_cell_labels(cohort)
    plot["Group"] = plot["response"].map({"yes": "Responder", "no": "Non-responder"})
    order = [LABELS[name] for name in POPULATIONS]
    base = alt.Chart(plot)
    shared = dict(
        x=alt.X(
            "Group:N",
            sort=["Responder", "Non-responder"],
            title=None,
            axis=alt.Axis(labelAngle=-20, ticks=False, labelLimit=90),
        ),
        y=alt.Y("percentage:Q", title="Relative frequency (%)", scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("Cell type:N"),
            alt.Tooltip("Group:N"),
            alt.Tooltip("percentage:Q", title="Percent", format=".2f"),
        ],
    )
    boxes = base.mark_boxplot(
        size=BOX_WIDTH,
        extent=1.5,
        outliers=False,
        ticks=False,
        color=PLOT_BLUE_DARK,
        box={"fill": "#F7FBFF", "stroke": PLOT_BLUE_DARK, "strokeWidth": 1.8},
        median={"color": "#16324F", "strokeWidth": 2.6},
        rule={"strokeWidth": 1.6},
    ).encode(**shared)
    caps = (
        base.transform_joinaggregate(
            q1="q1(percentage)",
            q3="q3(percentage)",
            groupby=["Cell type", "Group"],
        )
        .transform_filter(
            "(datum.percentage >= datum.q1 - 1.5 * (datum.q3 - datum.q1))"
            " && (datum.percentage <= datum.q3 + 1.5 * (datum.q3 - datum.q1))"
        )
        .transform_aggregate(
            low="min(percentage)",
            high="max(percentage)",
            groupby=["Cell type", "Group"],
        )
        .transform_fold(["low", "high"], as_=["end", "Whisker"])
        .mark_tick(orient="horizontal", size=BOX_WIDTH, thickness=1.6, color=PLOT_BLUE_DARK)
        .encode(
            x=alt.X("Group:N", sort=["Responder", "Non-responder"], axis=None),
            y=alt.Y("Whisker:Q", axis=None),
        )
    )
    points = (
        base.transform_calculate(jitter="(random() - 0.5) * 12")
        .mark_circle(size=18, color=PLOT_BLUE, opacity=0.22)
        .encode(**shared, xOffset="jitter:Q")
    )
    layers = alt.layer(boxes, points, caps).properties(width=148, height=250)
    return chart_theme(
        layers.facet(
            column=alt.Column(
                "Cell type:N",
                sort=order,
                title=None,
                header=alt.Header(labelOrient="top"),
            )
        )
    )


def baseline_chart(subset, title):
    chart_data = subset.copy()
    chart_data["Group"] = chart_data["group_name"].map(lambda name: GROUP_LABELS.get(name, name))
    chart = (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusEnd=3, size=16, color=PLOT_BLUE)
        .encode(
            x=alt.X("n:Q", title=None),
            y=alt.Y("Group:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("Group:N"), alt.Tooltip("n:Q", title="Count", format=",")],
        )
        .properties(height=150, title=alt.TitleParams(text=title, anchor="start", fontSize=13, color="#1F2430"))
    )
    return chart_theme(chart)


def context(items):
    parts = []
    for index, (label, value) in enumerate(items):
        if index:
            parts.append('<span class="sep">/</span>')
        parts.append(f"<span><em>{label}</em> {value}</span>")
    st.markdown(f'<div class="context">{"".join(parts)}</div>', unsafe_allow_html=True)


def panel_title(text):
    st.markdown(f'<p class="panel-title">{text}</p>', unsafe_allow_html=True)


def page_frequencies():
    stamp = database_stamp()
    row_count, sample_count = frequency_summary(stamp)
    with st.container(border=True):
        context(
            [
                ("View", "One sample"),
                ("Samples", f"{sample_count:,}"),
                ("Rows", f"{row_count:,}"),
            ]
        )
        sample_id = st.text_input(
            "Search for one sample",
            value="sample00000",
            placeholder="sample00000",
            help="Enter one sample id, such as sample00000.",
        )
    looked_up = sample_frequencies(sample_id.strip(), stamp)
    with st.container(border=True):
        panel_title("Population frequencies for this sample")
        if looked_up.empty:
            st.warning(f"No sample named {sample_id.strip()} is in the summary.")
        else:
            chart_col, table_col = st.columns((1.15, 1), gap="large")
            with chart_col:
                st.altair_chart(frequency_chart(looked_up), width="stretch")
            with table_col:
                st.dataframe(
                    format_frequencies(looked_up),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Total cells": st.column_config.NumberColumn(format="%d"),
                        "Count": st.column_config.NumberColumn(format="%d"),
                        "Percentage": st.column_config.TextColumn(),
                    },
                )
                st.caption(f"These five percentages sum to {looked_up['percentage'].sum():.2f}%.")

    with st.container(border=True):
        panel_title("Summary table")
        filter_col, rows_col = st.columns((2, 1))
        with filter_col:
            selected_label = st.selectbox("Cell type", ["All", *[LABELS[name] for name in POPULATIONS]])
        with rows_col:
            limit = int(st.slider("Rows", min_value=10, max_value=200, value=25, step=5))
        population = "All" if selected_label == "All" else next(
            name for name, label in LABELS.items() if label == selected_label
        )
        preview = format_frequencies(frequency_preview(population, limit, stamp))
        st.dataframe(
            preview,
            hide_index=True,
            width="stretch",
            column_config={
                "Total cells": st.column_config.NumberColumn(format="%d"),
                "Count": st.column_config.NumberColumn(format="%d"),
                "Percentage": st.column_config.TextColumn(),
            },
        )
        st.caption(f"Showing {len(preview):,} of {row_count:,} summary rows.")


def page_comparison():
    stats, cohort = response_statistics(database_stamp())
    responders = int(stats["n_responders"].iloc[0])
    non_responders = int(stats["n_non_responders"].iloc[0])
    significant_names = [
        LABELS[row["population"]] for _, row in stats.iterrows() if int(row["significant"])
    ]
    with st.container(border=True):
        context(
            [
                ("Condition", "Melanoma"),
                ("Treatment", "miraclib"),
                ("Sample type", "PBMC"),
                ("Compare", "Responder vs non-responder"),
            ]
        )
    if significant_names:
        st.success("Significant after adjustment: " + ", ".join(significant_names) + ".")
    else:
        st.info(
            f"No cell type differed significantly. {responders} responders and {non_responders} non-responders, one value per person."
        )

    with st.container(border=True):
        panel_title("Population frequencies")
        st.altair_chart(boxplot_chart(cohort), width="stretch")
        st.caption("Each point is one patient. Boxes compare responders with non-responders.")

    shown = add_cell_labels(stats)
    shown["significant"] = shown["significant"].map(lambda value: "Yes" if int(value) else "No")
    shown = shown.rename(
        columns={
            "median_responder_pct": "Responder median (%)",
            "median_non_responder_pct": "Non-responder median (%)",
            "median_difference_pct_points": "Difference",
            "u_statistic": "U",
            "p_value": "p-value",
            "p_value_adjusted": "Adjusted p",
            "significant": "Significant",
        }
    )
    display = shown[
        [
            "Cell type",
            "Responder median (%)",
            "Non-responder median (%)",
            "Difference",
            "U",
            "p-value",
            "Adjusted p",
            "Significant",
        ]
    ]
    with st.container(border=True):
        panel_title("Cell type comparison")
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_config={
                "Responder median (%)": st.column_config.NumberColumn(format="%.2f"),
                "Non-responder median (%)": st.column_config.NumberColumn(format="%.2f"),
                "Difference": st.column_config.NumberColumn(format="%+.2f"),
                "U": st.column_config.NumberColumn(format="%.0f"),
                "p-value": st.column_config.NumberColumn(format="%.3g"),
                "Adjusted p": st.column_config.NumberColumn(format="%.3g"),
            },
        )


def page_baseline():
    counts, samples = baseline_results(database_stamp())
    with st.container(border=True):
        context(
            [
                ("Condition", "Melanoma"),
                ("Treatment", "miraclib"),
                ("Sample type", "PBMC"),
                ("Time", "Day 0"),
            ]
        )
    response_yes = int(counts.loc[counts["group_name"] == "responder", "n"].sum())
    response_no = int(counts.loc[counts["group_name"] == "non-responder", "n"].sum())
    female = int(counts.loc[counts["group_name"] == "female", "n"].sum())
    male = int(counts.loc[counts["group_name"] == "male", "n"].sum())
    one, two, three, four = st.columns(4)
    one.metric("Samples", f"{len(samples):,}")
    two.metric("Projects with samples", "2 of 3")
    three.metric("Responders / non-responders", f"{response_yes} / {response_no}")
    four.metric("Female / male", f"{female} / {male}")

    with st.container(border=True):
        panel_title("Baseline composition")
        charts = st.columns(3)
        for column, (question, title) in zip(charts, QUESTION_LABELS.items()):
            subset = counts[counts["question"] == question]
            with column:
                st.altair_chart(baseline_chart(subset, title), width="stretch")

    labeled = samples.copy()
    labeled["response"] = labeled["response"].map({"yes": "Responder", "no": "Non-responder"})
    labeled["sex"] = labeled["sex"].map({"F": "Female", "M": "Male"})
    labeled = labeled.rename(
        columns={
            "sample": "Sample",
            "subject": "Subject",
            "project": "Project",
            "response": "Response",
            "sex": "Sex",
        }
    )
    with st.container(border=True):
        panel_title("Samples in this subset")
        search = st.text_input(
            "Filter by sample, subject, or project",
            value="",
            placeholder="prj1, sbj000, sample00000",
        )
        filtered = labeled
        if search.strip():
            needle = search.strip().lower()
            mask = (
                filtered["Sample"].str.lower().str.contains(needle, regex=False)
                | filtered["Subject"].str.lower().str.contains(needle, regex=False)
                | filtered["Project"].str.lower().str.contains(needle, regex=False)
            )
            filtered = filtered[mask]
        st.dataframe(filtered, hide_index=True, width="stretch")


def scroll_nav():
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const links = () => [...doc.querySelectorAll(".side-nav a")];
        const sections = () => links()
            .map((link) => doc.getElementById(link.getAttribute("href").slice(1)))
            .filter(Boolean);
        links().forEach((link) => {
            link.addEventListener("click", (event) => {
                event.preventDefault();
                const target = doc.getElementById(link.getAttribute("href").slice(1));
                if (target) target.scrollIntoView({behavior: "smooth", block: "start"});
            });
        });
        const mark = () => {
            const nodes = sections();
            let current = 0;
            nodes.forEach((node, index) => {
                if (node.getBoundingClientRect().top < 160) current = index;
            });
            links().forEach((link, index) => link.classList.toggle("active", index === current));
        };
        const scroller = doc.querySelector('[data-testid="stMain"]') || doc;
        scroller.addEventListener("scroll", mark, {passive: true});
        doc.addEventListener("scroll", mark, {passive: true});
        mark();
        </script>
        """,
        height=0,
    )


def main():
    st.set_page_config(page_title="Miraclib cell counts", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    require_database()
    with st.sidebar:
        st.markdown('<p class="brand">Miraclib trial</p>', unsafe_allow_html=True)
        st.markdown('<p class="brand-sub">Loblaw Bio</p>', unsafe_allow_html=True)
        st.markdown('<p class="nav-section">Analysis</p>', unsafe_allow_html=True)
        st.markdown(
            """
            <nav class="side-nav">
                <a href="#frequencies">Cell frequencies</a>
                <a href="#response">Immune changes</a>
                <a href="#baseline">Baseline subset</a>
            </nav>
            """,
            unsafe_allow_html=True,
        )
        scroll_nav()
    st.markdown('<div id="frequencies" class="section-anchor"></div>', unsafe_allow_html=True)
    page_frequencies()
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div id="response" class="section-anchor"></div>', unsafe_allow_html=True)
    page_comparison()
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div id="baseline" class="section-anchor"></div>', unsafe_allow_html=True)
    page_baseline()


if __name__ == "__main__":
    main()
