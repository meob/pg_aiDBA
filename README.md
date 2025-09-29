# pg_aiDBA - AI-Enhanced PostgreSQL Health & Performance Analyzer

![Logo](logo.png)

This project uses a combination of SQL scripts and an interface to a Large Language Model (LLM) to perform analysis on a PostgreSQL database and generate useful reports in Markdown format. The project is highly configurable and can be run entirely locally (including the LLM) or by leveraging powerful cloud-based models.

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

The `config.json` file allows you to configure the API endpoints for your LLM. This makes it easy to switch to any OpenAI-compatible LLM provider (cloud or local).

- `ai_api_url`: The endpoint for text generation (e.g., `http://localhost:11434/api/generate`).
- `ai_api_embedding_url`: The endpoint for generating embeddings (e.g., `http://localhost:11434/api/embeddings`).

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
- **Adding Documents**: To add knowledge, place your own Markdown (`.md`) or text (`.txt`) files into the `rag_sources/` directory. The project includes technical articles and templates to get you started; it is very important that documents are **customized to what is actually present** in the environments to be checked.
- **Loading Documents**: After adding or changing documents, you must load them into the vector database by running:
  ```bash
  python3 load_rag.py
  ```

### RAG Parameters

The behavior of the RAG data loading process is controlled by the following parameters in the `rag_config` section of the `config.json` file.

- **`embedding_model`**: The name of the embedding model to use, which **must be available on your Ollama instance**. This model is used to create numerical representations (embeddings) of your text documents. Example: `qllama/bge-large-en-v1.5`.
  - **Important Note on Changing Models**: If you change the `embedding_model`, you **must** re-run `python3 load_rag.py`. The script will automatically detect the new embedding dimension and recreate the table if necessary. It is recommended to use a new `table_name` in the configuration or manually drop the old table (`DROP TABLE pg_aidba_rag_kb;`) to avoid issues.

- **`tokenizer_model`**: The name of the model used by the `tiktoken` library for chunking text into tokens. The default, `"gpt-4"`, is a robust choice for general text. You can change it if you have specific tokenization needs.

- **`chunk_size`**: The maximum size of each text chunk **in tokens**. The default of `512` is a good balance between context size and focus, and it matches the context window of many embedding models.

- **`chunk_overlap`**: The number of tokens that overlap between consecutive chunks. This helps prevent sentences from being cut in half and losing their meaning, providing better context.

### RAG Search Parameters

These parameters, also in `rag_config`, control how the RAG system searches for relevant documents in the knowledge base.

- **`distance_metric`**: The metric for the similarity search. It can be `cosine` (default), `euclidean` (L2), or `inner_product`. For text embeddings, `cosine` is generally the recommended and most effective metric.

- **`similarity_threshold`**: A filter to exclude less relevant results. For `cosine` and `euclidean` distance, where lower values mean higher similarity, only results with a distance *less than* this value are returned. The default of `1.0` effectively disables this filter. Note that `pgvector` calculates **cosine distance** (`1 - cosine similarity`), which ranges from 0 (identical) to 2 (opposite). Therefore, a smaller value indicates higher similarity. A value like `0.4` or `0.5` can be used to enforce a stricter similarity match.

- **`retrieval_limit`**: The maximum number of document chunks to retrieve from the knowledge base. These retrieved chunks are then added to the LLM's prompt to provide context for the analysis.

### Advanced Note: RAG vs. Fine-Tuning

This project leverages Retrieval-Augmented Generation (RAG) to provide specific knowledge to the LLM. An alternative approach is to fine-tune a model. However, fine-tuning requires creating a large and expensive training dataset (hundreds of expert-written sample reports). RAG proves to be a more practical and flexible solution, allowing the knowledge base to be updated by simply editing text files in the `rag_sources/` directory, without needing to retrain the model.

### SQL Scripts Customization

Last but not least, the SQL scripts (`pg2aidba_base.sql` and `pg2aidba.sql`) are a critical component. They are the first to be executed and collect all the raw data for the analysis.

The queries in these files have been extracted and adapted from the comprehensive `pg2html.sql` script found in the [db2html project](https://github.com/meob/db2html/tree/master/pg2html/pg2html.sql). You can modify these scripts to add, remove, or alter queries to better suit your specific monitoring needs.

**Important**: If you add new queries or data points, remember to update the corresponding prompt file (`prompt/base_prompt.txt` or `prompt/perf_prompt.txt`). This ensures the LLM is aware of the new data and can include it in its analysis.

## License

This project is released under the Apache 2.0 license (meob).

