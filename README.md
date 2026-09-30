# Miraclib immune cell counts

This project loads `cell-count.csv` into a SQLite database, summarizes immune cell frequencies, compares melanoma patients who respond to miraclib with those who do not, and counts the baseline PBMC subset. An interactive dashboard shows those results.

**Dashboard:** [http://localhost:8501](http://localhost:8501)

In GitHub Codespaces, `make dashboard` forwards port 8501. Open the URL Codespaces shows for that port. On your own machine, the link above opens the dashboard after the server starts.

## Run the project

From the repository root, in GitHub Codespaces or a local terminal:

```bash
make setup
make pipeline
make dashboard
```

Leave `make dashboard` running, then open [http://localhost:8501](http://localhost:8501). Stop the server with Ctrl+C.

`make setup` creates a `.venv` folder and installs the packages in `requirements.txt`.

`make pipeline` runs the analysis from start to finish:

1. `load_data.py` builds `cell_count.db` and loads every row of `cell-count.csv`.
2. `frequencies.py` writes the relative-frequency summary (Part 2).
3. `response_comparison.py` compares responders and non-responders (Part 3).
4. `baseline_subset.py` counts the day-0 melanoma PBMC samples on miraclib (Part 4).

`make dashboard` reads those results from `cell_count.db` and serves the dashboard. Run `make pipeline` before `make dashboard`.

## What the dashboard shows

- **Cell frequencies.** For a chosen sample, each cell type's count and its percentage of that sample's total. You can also browse the full summary.
- **Responders vs non-responders.** Boxplots and the Mann-Whitney test w/ BH correction for melanoma patients on miraclib, PBMC samples only.
- **Baseline subset.** How many day-0 melanoma PBMC samples on miraclib come from each project, and how many of those subjects responded or are male or female.



## Files


| File                     | What it is                                          |
| ------------------------ | --------------------------------------------------- |
| `cell-count.csv`         | Source data                                         |
| `load_data.py`           | Creates `cell_count.db`                             |
| `frequencies.py`         | Part 2 summary                                      |
| `response_comparison.py` | Part 3 comparison and boxplots                      |
| `baseline_subset.py`     | Part 4 subset counts                                |
| `dashboard.py`           | Interactive dashboard                               |
| `Makefile`               | `setup`, `pipeline`, and `dashboard`                |
| `cell_count.db`          | Database created by the pipeline                    |
| `output/`                | CSV tables, the boxplot image, and written findings |


`cell_count.db` and `output/` are created when you run the pipeline. They are not stored in git.