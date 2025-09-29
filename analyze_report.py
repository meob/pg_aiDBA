import json
import requests
import sys
import os
import datetime

from utils import load_config, get_ollama_embedding

# --- RAG Imports (optional) ---
try:
    import psycopg2
    from pgvector.psycopg2 import register_vector
    import numpy as np # Import numpy
    RAG_ENABLED = True
except ImportError:
    RAG_ENABLED = False

# --- Configuration ---
CONFIG_FILE = "config.json"

# The model is read from the AI_MODEL environment variable.
AI_MODEL = os.environ.get("AI_MODEL", "llama3:8b")

def get_rag_context(db_stats, config):
    """
    Connects to the RAG database, generates a query from db_stats,
    and retrieves relevant context. Returns an empty string if RAG fails.
    """
    if not RAG_ENABLED:
        print("--- RAG libraries not installed. Skipping RAG context. ---", file=sys.stderr)
        return ""
    
    rag_config = config.get("rag_config", {})
    debug_mode = config.get("debug_mode", False)
        
    if not rag_config or not rag_config.get("connection_string"):
        print("--- RAG not configured. Skipping RAG context. ---", file=sys.stderr)
        return ""

    try:
        print("--- Retrieving RAG context (Ollama)... ---", file=sys.stderr)
        
        # 1. Construct search query from failing KPIs and metadata
        kpis = db_stats.get("kpi_summary", [])
        search_terms = [kpi.get("kpi_name") for kpi in kpis] if kpis else []
        
        metadata = db_stats.get("metadata", {})
        db_name = metadata.get("database_name", "unknown_database")
        pg_version = metadata.get("pg_version", "unknown_version")

        search_query_parts = []
        if search_terms:
            search_query_parts.append(f"Failing KPIs: {', '.join(search_terms)}")
        search_query_parts.append(f"PostgreSQL database: {db_name}")
        search_query_parts.append(f"PostgreSQL version: {pg_version}")
        
        search_query = ". ".join(search_query_parts)
        
        if not search_query_parts:
            print("--- No relevant information to generate RAG query. Skipping. ---", file=sys.stderr)
            return ""

        if debug_mode:
            print(f"--- DEBUG: RAG search query: {search_query} ---", file=sys.stderr)

        # 2. Generate query embedding via Ollama
        embedding_model = rag_config.get("embedding_model")
        if not embedding_model:
            print("Warning: No `embedding_model` configured for RAG. Skipping.", file=sys.stderr)
            return ""

        print(f"--- Generating RAG query embedding with model '{embedding_model}'... ---", file=sys.stderr)
        embedding_list = get_ollama_embedding(embedding_model, search_query, config)
        if not embedding_list:
            print("Warning: Failed to generate RAG query embedding. Skipping RAG context.", file=sys.stderr)
            return ""
        query_embedding = np.array(embedding_list)

        # 3. Connect to DB
        conn = psycopg2.connect(rag_config["connection_string"])
        register_vector(conn)
        cur = conn.cursor()

        # 4. Perform similarity search
        table_name = rag_config.get("table_name", "pg_aidba_rag_kb")
        distance_metric = rag_config.get("distance_metric", "cosine")
        similarity_threshold = rag_config.get("similarity_threshold", 1.0)
        retrieval_limit = rag_config.get("retrieval_limit", 5)

        metric_operators = {"cosine": "<=>", "euclidean": "<->", "inner_product": "<#"}
        op = metric_operators.get(distance_metric, "<=>")

        sql_query = f"SELECT title, content FROM {table_name} "
        if similarity_threshold < 1.0:
            sql_query += f"WHERE embedding {op} %s < %s "
            order_by_clause = f"ORDER BY embedding {op} %s"
            params = (query_embedding, similarity_threshold, query_embedding)
        else:
            order_by_clause = f"ORDER BY embedding {op} %s"
            params = (query_embedding,)
        
        sql_query += f"{order_by_clause} LIMIT %s"
        params += (retrieval_limit,)

        cur.execute(sql_query, params)
        results = cur.fetchall()
        cur.close()
        conn.close()

        if not results:
            return ""

        # 5. Format context
        from collections import defaultdict
        grouped_results = defaultdict(list)
        for title, content in results:
            grouped_results[title].append(content)

        context = "\n\n--- Relevant Knowledge Base Articles ---\n"
        for title, contents in grouped_results.items():
            context += f"\n### From: {title}\n"
            for content in contents:
                context += f"- {content.strip()}\n"
        
        print("--- Successfully retrieved RAG context. ---", file=sys.stderr)
        return context

    except Exception as e:
        print(f"Warning: Failed to retrieve RAG context. Proceeding without it. Error: {e}", file=sys.stderr)
        return ""

def get_analysis_from_llm(prompt_data, params, config):
    """
    Sends the provided data to a compatible LLM API and returns the response.
    """
    ai_api_url = config.get("ai_api_url", "http://localhost:11434/api/generate")
    ai_api_key = config.get("ai_api_key")
    ai_api_timeout = config.get("ai_api_timeout", 120)
    debug_mode = config.get("debug_mode", False)

    try:
        payload = {
            "model": AI_MODEL,
            "prompt": prompt_data,
            "stream": False
        }
        
        if params:
            payload["options"] = params

        headers = {"Content-Type": "application/json"}
        if ai_api_key:
            headers["Authorization"] = f"Bearer {ai_api_key}"

        if debug_mode:
            print(f"--- DEBUG: Sending payload to AI: {json.dumps(payload, indent=2)} ---", file=sys.stderr)
        print(f"--- Contacting AI at {ai_api_url} with model {AI_MODEL}... ---", file=sys.stderr)
        
        response = requests.post(ai_api_url, json=payload, headers=headers, timeout=ai_api_timeout)
        response.raise_for_status()

        print("--- Received response. Generating report... ---", file=sys.stderr)
        
        response_json = response.json()
        if debug_mode:
            print(f"--- DEBUG: Received response from AI: {json.dumps(response_json, indent=2)} ---", file=sys.stderr)
        return response_json.get("response", "").strip()

    except requests.exceptions.Timeout:
        return f"Error: The request to the AI API timed out after {ai_api_timeout} seconds."
    except requests.exceptions.RequestException as e:
        return f"Error: Could not connect to AI API at {ai_api_url}. Please ensure the endpoint is correct and the service is running. Details: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to decode JSON response from the AI API."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def main():
    """
    Main function to read data, generate a prompt, and save the analysis.
    """
    config = load_config()
    analysis_profiles = config.get("analysis_profiles", {})
    llm_params_config = config.get("llm_params", {})

    if len(sys.argv) > 1 and sys.argv[1] in analysis_profiles:
        analysis_type = sys.argv[1]
    else:
        analysis_type = "base"
    
    profile = analysis_profiles.get(analysis_type, {})
    if not profile:
        print(f"Error: Analysis profile '{analysis_type}' not found in {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    data_file = profile.get("data_file")
    prompt_file = profile.get("prompt_file")
    output_prefix = profile.get("output_prefix")
    llm_params = llm_params_config.get(analysis_type, {})

    print(f"--- Running analysis type: '{analysis_type}' ---", file=sys.stderr)

    start_time = datetime.datetime.now()
    
    try:
        with open(data_file, 'r') as f:
            db_stats_json_string = f.read()
            db_stats = json.loads(db_stats_json_string)
    except FileNotFoundError:
        print(f"Error: The file '{data_file}' was not found.", file=sys.stderr)
        print(f"Please run the corresponding SQL script first (e.g., `psql -f {data_file.replace('.json', '.sql')}`).", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{data_file}'. The file might be empty or malformed.", file=sys.stderr)
        sys.exit(1)

    rag_context = ""
    if analysis_type == 'perf':
        rag_context = get_rag_context(db_stats, config)

    try:
        with open(prompt_file, 'r') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file '{prompt_file}' not found.", file=sys.stderr)
        sys.exit(1)

    full_prompt = prompt_template.format(rag_context=rag_context, json_data=db_stats_json_string)

    analysis = get_analysis_from_llm(full_prompt, llm_params, config)
    
    end_time = datetime.datetime.now()

    database_name = db_stats.get("metadata", {}).get("database_name", "unknown_db")
    timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"{output_prefix}.{database_name}.{timestamp_str}.md"

    footer = "\n---\n"
    footer += f"*Report generated by pg_aidba ({analysis_type}) on {start_time.strftime('%Y-%m-%d at %H:%M:%S')}*\n"
    footer += f"*Model used: `{AI_MODEL}`*\n"
    footer += f"*Analysis duration: {(end_time - start_time).total_seconds():.2f} seconds*\n"
    footer += f"*License: Apache 2.0 (meob)*\n"

    final_report = analysis + "\n" + footer

    try:
        with open(output_filename, 'w') as f:
            f.write(final_report)
        print(f"--- Report successfully saved to '{output_filename}' ---", file=sys.stderr)
    except IOError as e:
        print(f"Error: Could not write report to file '{output_filename}'. Details: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
