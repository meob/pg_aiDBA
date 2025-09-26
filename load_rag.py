import json
import os
import sys
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
import tiktoken

# --- Configuration ---
CONFIG_FILE = "config.json"

def load_config():
    """Loads configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'.", file=sys.stderr)
        sys.exit(1)

config = load_config()
DEBUG_MODE = config.get("debug_mode", False)

def get_db_connection(connection_string):
    """Establishes a connection to the PostgreSQL database."""
    if DEBUG_MODE:
        print(f"--- DEBUG: Connecting to DB with connection string: {connection_string} ---", file=sys.stderr)
    try:
        conn = psycopg2.connect(connection_string)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database. Please check the connection_string in {CONFIG_FILE}.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)

def chunk_text(text, model_name, chunk_size, chunk_overlap):
    """Splits text into chunks of a specified size with overlap."""
    if not text:
        return []
    
    try:
        # Use tiktoken for more accurate token-based chunking
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback for models not in tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), chunk_size - chunk_overlap):
        chunk_tokens = tokens[i:i + chunk_size]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks

def main():
    """
    Main function to load documents from a directory, generate embeddings,
    and store them in a PostgreSQL/pgvector database.
    """
    print("--- Starting RAG Knowledge Base Loading ---")
    
    config = load_config()
    rag_config = config.get("rag_config")
    DEBUG_MODE = config.get("debug_mode", False)

    if not rag_config:
        print(f"Error: `rag_config` section not found in {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    conn_string = rag_config.get("connection_string")
    model_name = rag_config.get("embedding_model", "all-MiniLM-L6-v2")
    chunk_size = rag_config.get("chunk_size", 512)
    chunk_overlap = rag_config.get("chunk_overlap", 50)
    table_name = rag_config.get("table_name", "pg_aidba_rag_kb")
    
    if not conn_string:
        print(f"Error: `connection_string` not found in the `rag_config` section of {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)

    # --- 1. Connect to Database ---
    print(f"Connecting to the database...")
    conn = get_db_connection(conn_string)
    register_vector(conn)
    cur = conn.cursor()

    # --- 2. Setup Database Table ---
    try:
        print("Enabling pgvector extension...")
        if DEBUG_MODE:
            print(f"--- DEBUG: Executing SQL: CREATE EXTENSION IF NOT EXISTS vector; ---", file=sys.stderr)
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        print(f"Creating table '{table_name}' if it doesn't exist...")
        # Get embedding dimension from the model
        model = SentenceTransformer(model_name)
        embedding_dim = model.get_sentence_embedding_dimension()
        
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            title TEXT,
            content TEXT,
            embedding VECTOR({embedding_dim})
        );
        """
        if DEBUG_MODE:
            print(f"--- DEBUG: Executing SQL: {create_table_sql} ---", file=sys.stderr)
        cur.execute(create_table_sql)

        print(f"Clearing existing data from '{table_name}'...")
        if DEBUG_MODE:
            print(f"--- DEBUG: Executing SQL: TRUNCATE TABLE {table_name}; ---", file=sys.stderr)
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
                    
                    # Heuristic to find the title
                    if first_line.startswith("# "):
                        title = first_line[2:].strip()
                        text = rest_of_text
                    else:
                        title = filename
                        text = first_line + "\n" + rest_of_text

                chunks = chunk_text(text, "gpt-4", chunk_size, chunk_overlap)
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
    print(f"Generating embeddings using model '{model_name}'...")
    try:
        # Extract just the content for embedding
        content_to_embed = [item[1] for item in all_chunks_with_titles]
        if DEBUG_MODE:
            print(f"--- DEBUG: Content to embed: {content_to_embed} ---", file=sys.stderr)
        embeddings = model.encode(content_to_embed, show_progress_bar=True)
        if DEBUG_MODE:
            print(f"--- DEBUG: Generated embeddings (first 5): {embeddings[:5]} ---", file=sys.stderr) # Log only first 5 for brevity
        
        print("Inserting data into the database...")
        for i, (title, content) in enumerate(all_chunks_with_titles):
            embedding = embeddings[i]
            if DEBUG_MODE:
                print(f"--- DEBUG: Executing SQL: INSERT INTO {table_name} (title, content, embedding) VALUES (%s, %s, %s); ---", file=sys.stderr)
                print(f"--- DEBUG: INSERT values: (title='{title}', content='{content[:50]}...', embedding='{embedding[:10]}...') ---", file=sys.stderr) # Log truncated content and embedding
            cur.execute(f"INSERT INTO {table_name} (title, content, embedding) VALUES (%s, %s, %s);", (title, content, embedding))
        
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
