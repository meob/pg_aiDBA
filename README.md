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
- `requirements.txt`: A file listing the Python dependencies required for the RAG functionality.

## Quick Start

The easiest way to run an analysis is to use the launcher script.

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3** and **pip**: The analysis script is written in Python 3.
- **Python Dependencies**: Install the required libraries for the project, including the optional RAG components.
  ```bash
  pip install -r requirements.txt
  ```
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

## Customization

This project is highly customizable. You can tailor the AI's behavior and knowledge base by editing the configuration and prompt files.

### Performance Prompt

The quality of the performance report (`perf`) is highly dependent on the prompt used to instruct the AI. The default prompt is located at `prompt/perf_prompt.txt`. You can edit this file to include specific details about your environment, workload, or hardware.

### LLM Models and Parameters

The `config.json` file allows you to define which LLM models to use and how they behave.

- **Model Choice**: For `base` analysis, it's recommended to use smaller, local models (e.g., `llama3:8b` via Ollama) due to their efficiency. For `perf` analysis, more powerful models are suggested. Ollama allows you to easily pull and use larger cloud-based models (e.g., `gpt-oss:120b-cloud`) if configured. The `AI_MODEL` environment variable overrides the default.
- **Parameters**: The `llm_params` section in `config.json` controls the LLM's behavior. These parameters influence the creativity and determinism of the model's output.
  - **`temperature`**: Controls randomness. Lower values (e.g., 0.1-0.3) make the output more focused and deterministic. Higher values make it more creative. For this tool, **low values are strongly recommended** to ensure factual and reliable analysis.
  - **`top_p`**: An alternative to temperature that controls the nucleus of probable words for the model to choose from.

The script is generic and will pass any parameter from this section to the model API, nested under an `options` key for Ollama compatibility.

### RAG Knowledge Base

The Retrieval-Augmented Generation (RAG) feature allows the AI to pull context from a custom knowledge base during `perf` analysis.

- **Suitable Documents**: The effectiveness of RAG depends on the quality and relevance of your documents. Ideal documents include:
  - **Application Profiles**: Descriptions of your applications (OLTP, DWH, etc.), their workload patterns, and hardware context.
  - **Known Anti-Patterns**: Documented common issues, inefficient code patterns, or specific behaviors of your application.
  - **Internal Best Practices**: Your organization's specific guidelines for PostgreSQL tuning, deployment, or monitoring.
  - **Domain-Specific Tuning**: Advice tailored to your industry or specific use cases.
- **Adding Documents**: To add knowledge, place your own Markdown (`.md`) or text (`.txt`) files into the `rag_sources/` directory. The project includes technical articles and templates to get you started.
- **Loading Documents**: After adding or changing documents, you must load them into the vector database by running:
  ```bash
  python3 load_rag.py
  ```

### RAG Parameters

The behavior of the RAG system is controlled by the `rag_config` section in `config.json`.

- **`embedding_model`**: The model used to create numerical representations of text. The default is now set to `BAAI/bge-large-en-v1.5`, a powerful and well-regarded model. You can switch to other models, but you **must** re-run `load_rag.py` after changing the name.
  - **Important Note on Changing Models**: If you change the `embedding_model`, you **must** manually drop the RAG table in your PostgreSQL database (e.g., `DROP TABLE pg_aidba_rag_kb;` in `psql`) before re-running `python3 load_rag.py`. This is because different embedding models produce vectors of different dimensions, and the database table needs to be recreated with the correct vector dimension. Alternatively, you can change the `table_name` in `config.json` to use a new table.
  - **Good Alternatives**: `nomic-ai/nomic-embed-text-v1.5` (very efficient), `Salesforce/SFR-Embedding-Mistral` (latest generation), or the lighter `all-MiniLM-L6-v2` (fast, less resource-intensive).
- **`chunk_size`**: The size of each piece of text (in tokens) stored in the vector database. The default of `512` is a good balance between context size and focus.
- **`chunk_overlap`**: The number of tokens that overlap between consecutive chunks. This prevents sentences from being cut in half and losing their meaning.

## RAG Search Parameters

The RAG search functionality has been enhanced to include database metadata and support parametric searches, allowing for more precise and context-aware retrieval of information.

- **Database Metadata Inclusion**: When performing RAG searches, relevant metadata from the PostgreSQL database is now automatically incorporated into the query context. This enriches the search with real-time database schema, statistics, and configuration details, leading to more accurate and tailored recommendations.
- **Parametric Searches**: The RAG system now supports parametric queries, enabling users to specify conditions and filters for their searches. This allows for highly targeted information retrieval based on specific criteria, improving the relevance of the retrieved documents for the LLM.

## License

This project is released under the Apache 2.0 license (meob).
