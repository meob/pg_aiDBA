import os
import sys
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np
import tiktoken

from utils import load_config, get_ollama_embedding

# --- Constants ---
CONFIG_FILE = "config.json"

def get_db_connection(connection_string, debug_mode):
    """Establishes a connection to the PostgreSQL database."""
    if debug_mode:
        print(f"--- DEBUG: Connecting to DB with connection string: {connection_string} ---", file=sys.stderr)
    try:
        conn = psycopg2.connect(connection_string)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database. Please check the connection_string in {CONFIG_FILE}.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)

def chunk_text(text, model_name, chunk_size, chunk_overlap):
    """Splits text into chunks of a specified token size with overlap."""
    if not text:
        return []
    
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), chunk_size - chunk_overlap):
        chunk_tokens = tokens[i:i + chunk_size]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks

def main():
    """
    Main function to load documents from a directory, generate embeddings via Ollama,
    and store them in a PostgreSQL/pgvector database.
    """
    print("--- Starting RAG Knowledge Base Loading (Ollama) ---")
    
    config = load_config()
    rag_config = config.get("rag_config")
    debug_mode = config.get("debug_mode", False)

    if not rag_config:
        print(f"Error: `rag_config` section not found in {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    if not config.get("ai_api_embedding_url"):
        print(f"Error: `ai_api_embedding_url` not found in {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    conn_string = rag_config.get("connection_string")
    model_name = rag_config.get("embedding_model")
    tokenizer_model = rag_config.get("tokenizer_model", "gpt-4") # New
    chunk_size = rag_config.get("chunk_size", 512)
    chunk_overlap = rag_config.get("chunk_overlap", 50)
    table_name = rag_config.get("table_name", "pg_aidba_rag_kb")
    
    if not conn_string:
        print(f"Error: `connection_string` not found in the `rag_config` section of {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)
    if not model_name:
        print(f"Error: `embedding_model` not found in the `rag_config` section of {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    # --- 1. Connect to Database ---
    print("Connecting to the database...")
    conn = get_db_connection(conn_string, debug_mode)
    register_vector(conn)
    cur = conn.cursor()

    # --- 2. Setup Database Table ---
    try:
        print("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        print("Determining embedding dimension...")
        test_embedding_list = get_ollama_embedding(model_name, "test", config)
        if not test_embedding_list:
            print("Error: Failed to get a test embedding to determine vector dimension.", file=sys.stderr)
            sys.exit(1)
        embedding_dim = len(test_embedding_list)
        print(f"Detected embedding dimension: {embedding_dim}")

        print(f"Creating table '{table_name}' if it doesn't exist...")
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            title TEXT,
            content TEXT,
            embedding VECTOR({embedding_dim})
        );
        """
        cur.execute(create_table_sql)

        print(f"Clearing existing data from '{table_name}'...")
        cur.execute(f"TRUNCATE TABLE {table_name};")
        
        conn.commit()
    except Exception as e:
        print(f"Error during database setup: {e}", file=sys.stderr)
        conn.rollback()
        cur.close()
        conn.close()
        sys.exit(1)

    # --- 3. Read and Chunk Documents ---
    print("Reading documents from 'rag_sources/' directory...")
    all_chunks_with_titles = []
    source_dir = "rag_sources"
    try:
        for filename in os.listdir(source_dir):
            if filename.endswith((".md", ".txt")):
                filepath = os.path.join(source_dir, filename)
                print(f"  - Processing {filepath}")
                with open(filepath, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    rest_of_text = f.read()
                    
                    if first_line.startswith("# "):
                        title = first_line[2:].strip()
                        text = rest_of_text
                    else:
                        title = filename
                        text = first_line + "\n" + rest_of_text

                chunks = chunk_text(text, tokenizer_model, chunk_size, chunk_overlap)
                for chunk in chunks:
                    all_chunks_with_titles.append((title, chunk))

    except FileNotFoundError:
        print(f"Error: The '{source_dir}' directory was not found.", file=sys.stderr)
        cur.close()
        conn.close()
        sys.exit(1)

    if not all_chunks_with_titles:
        print("No text chunks to process. Exiting.", file=sys.stderr)
        cur.close()
        conn.close()
        sys.exit(0)
        
    print(f"Total chunks to process: {len(all_chunks_with_titles)}")

    # --- 4. Generate Embeddings and Insert into DB ---
    print(f"Generating embeddings using model '{model_name}' via Ollama...")
    try:
        for i, (title, content) in enumerate(all_chunks_with_titles):
            print(f"  - Generating embedding for chunk {i+1}/{len(all_chunks_with_titles)}...")
            embedding_list = get_ollama_embedding(model_name, content, config)
            
            if embedding_list:
                embedding_array = np.array(embedding_list)
                cur.execute(f"INSERT INTO {table_name} (title, content, embedding) VALUES (%s, %s, %s);", (title, content, embedding_array))
        
        conn.commit()
        print(f"--- Successfully loaded {len(all_chunks_with_titles)} chunks into the knowledge base. ---")

    except Exception as e:
        print(f"Error during embedding generation or database insertion: {e}", file=sys.stderr)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
