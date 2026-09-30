ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON := $(ROOT).venv/bin/python

export MPLCONFIGDIR := $(ROOT).mplconfig

.PHONY: setup pipeline dashboard

setup:
	python3 -m venv $(ROOT).venv
	$(PYTHON) -m pip install -r $(ROOT)requirements.txt

pipeline:
	$(PYTHON) $(ROOT)load_data.py
	$(PYTHON) $(ROOT)frequencies.py
	$(PYTHON) $(ROOT)response_comparison.py
	$(PYTHON) $(ROOT)baseline_subset.py

dashboard:
	$(PYTHON) -m streamlit run $(ROOT)dashboard.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
