#!/bin/bash

# run_analysis.sh
# This script runs the full data collection and generates the base operational report.

# --- Configuration ---
# The script uses standard PostgreSQL environment variables for the connection:
# PGDATABASE, PGHOST, PGPORT, PGUSER, PGPASSWORD
# It also requires the AI_MODEL environment variable to be set for the analyzer.
# Example:
# export PGDATABASE=bench0
# export PGUSER=myuser
# export AI_MODEL=llama3:8b

set -e # Exit immediately if a command exits with a non-zero status.

echo "--- (1/3) Running Base operational data collection (pg2aidba_base.sql) ---"
psql -X -q -f pg2aidba_base.sql

echo "--- (2/3) Running Performance data collection (pg2aidba.sql) ---"
psql -X -q -f pg2aidba.sql

echo "--- (3/3) Running Base operational analysis ---"
python3 analyze_report.py base

echo "--- Analysis complete. ---"
