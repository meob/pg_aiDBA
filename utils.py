import json
import sys
import requests

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

def get_ollama_embedding(model_name, text, config):
    """Gets an embedding from an Ollama-compatible API."""
    ai_api_embedding_url = config.get("ai_api_embedding_url")
    ai_api_key = config.get("ai_api_key")
    ai_api_timeout = config.get("ai_api_timeout", 120) # Get timeout
    
    if not ai_api_embedding_url:
        print("Error: `ai_api_embedding_url` not configured.", file=sys.stderr)
        return None

    try:
        payload = {
            "model": model_name,
            "prompt": text
        }
        headers = {"Content-Type": "application/json"}
        if ai_api_key:
            headers["Authorization"] = f"Bearer {ai_api_key}"

        response = requests.post(ai_api_embedding_url, json=payload, headers=headers, timeout=ai_api_timeout)
        response.raise_for_status()
        
        response_json = response.json()
        return response_json.get("embedding")

    except requests.exceptions.Timeout:
        print(f"Warning: The request to the AI embedding API timed out after {ai_api_timeout} seconds.", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not connect to AI embedding API at {ai_api_embedding_url}. Details: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: An unexpected error occurred during embedding generation: {e}", file=sys.stderr)
        return None
