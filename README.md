# pg_aiDBA - AI-Enhanced PostgreSQL Health & Performance Analyzer

![Logo](logo.png)

This project uses a combination of SQL scripts and an interface to a Large Language Model (LLM) to perform analysis on a PostgreSQL database and generate useful reports in Markdown format.

The system is designed with two distinct analysis levels: **base** (for operational checks) and **perf** (for expert performance tuning).

## Components

- `analyze_report.py`: The main Python script that reads data, contacts the LLM, and generates the final report.
- `config.json`: The main configuration file for the project. It defines the AI API endpoint and the analysis profiles.
- `run_analysis.sh`: An executable bash script that orchestrates the entire process of data collection and report generation.
- `pg2aidba.sql`: "perf" analysis SQL script. Collects a comprehensive set of performance metrics from the PostgreSQL database.
- `pg2aidba_base.sql`: "base" analysis SQL script. Collects operational data for a status report.
- `prompt/`: A directory containing the prompt templates for the LLM (`base_prompt.txt` and `perf_prompt.txt`).

## Quick Start

The easiest way to run an analysis is to use the launcher script.

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3**: The analysis script is written in Python 3.
- **PostgreSQL Client (`psql`)**: Required to run the data collection SQL scripts.
- **Ollama**: The system defaults to a local Ollama instance. You can find installation instructions at [ollama.com](https://ollama.com/). You can also use any OpenAI-compatible API endpoint.

### 1. Configure Environment

First, set the necessary environment variables for the database connection and the LLM model.

```bash
# Set PostgreSQL connection variables (used by psql)
export PGDATABASE=your_db_name
export PGUSER=your_user
export PGPASSWORD=your_password
# PGHOST and PGPORT can also be set if not default

# Set the AI model to use. For the default base analysis, a local model is sufficient.
export AI_MODEL=llama3:8b

# Load the default LLM
ollama pull llama3:8b
```

### 2. Run the Script

The launch script runs both data collection scripts and then generates the **base** report by default.

```bash
./run_analysis.sh
```

This will create a report file named `pg2aidba-base.<db_name>.<timestamp>.md`.

## Configuration

The `config.json` file allows you to configure the `ai_api_url`. This makes it easy to switch to any OpenAI-compatible LLM provider (cloud or local) by changing the URL.

For the `base` analysis, it is recommended to have a local Ollama instance running with the `llama3:8b` model pulled (`ollama pull llama3:8b`).

## Advanced Usage

The `run_analysis.sh` script is a convenient wrapper, but the components can be executed separately for greater control. This is particularly useful for the `perf` analysis.

The workflow consists of two main steps:
1.  **Data Collection**: Run the `psql` script to query the database and generate a JSON file.
2.  **Analysis**: Run the `analyze_report.py` script, pointing to the generated JSON, to produce the Markdown report.

To generate the more detailed **"perf"** (performance) report, you would run the specific components:

```bash
# 1. Run the performance data collection script
# This connects to the database and creates pg2aidba.json
psql -X -q -f pg2aidba.sql

# 2. Set AI_MODEL to a powerful model (local or cloud)
# Performance analysis provides much better results with a powerful model.
export AI_MODEL=gpt-oss:120b-cloud

# 3. Run the performance analysis script
python3 analyze_report.py perf
```

This modularity allows you to re-run the analysis with different models or customized prompts without querying the database every time.

## Customization: The Performance Prompt

The quality of the performance report (`perf`) is highly dependent on the prompt used to instruct the AI. The default prompt is located at `prompt/perf_prompt.txt`.

**This prompt is designed to be customized.** You can and should edit it to include specific details about your environment, such as:
- Known workload patterns (e.g., "This is an OLTP system with high write contention on the `orders` table").
- Application behavior (e.g., "The application uses a connection pool of 50 connections").
- Hardware context (e.g., "The database runs on a server with 128GB of RAM and fast NVMe storage").

Providing this context will allow the AI to generate much more relevant and actionable recommendations.

## Roadmap

- **Retrieval-Augmented Generation (RAG)**: We plan to enhance the analysis by incorporating a RAG approach. This will allow the AI to reference external documentation, articles, or internal knowledge bases to provide even more insightful and context-aware recommendations.
- **Cloud LLM Integration**: Improve integration with cloud-based LLMs by adding robust support for API keys and adapting to different API schemas.

## License

This project is released under the Apache 2.0 license (meob).
