from fastapi import FastAPI, Query, HTTPException
import os
import subprocess
import json
import sqlite3
import requests
import markdown
import duckdb
import logging
from pathlib import Path
from datetime import datetime
import openai
from functools import lru_cache

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# Get AI Proxy Token Securely
api_key = os.environ.get("AIPROXY_TOKEN")
if not api_key:
    raise RuntimeError("AIPROXY_TOKEN environment variable is missing!")
openai.api_key = api_key

# Security check: Prevent access outside /data
def validate_path(filepath: str):
    """Ensure file access is restricted to /data."""
    real_path = os.path.realpath(filepath)
    if not real_path.startswith("/data"):
        logging.warning(f"Unauthorized file access attempt: {filepath}")
        raise HTTPException(status_code=403, detail="Access outside /data is forbidden.")
    return real_path

# Use caching to avoid redundant LLM calls
@lru_cache(maxsize=100)
def parse_task_with_llm(task_description: str) -> str:
    """Uses LLM to parse task descriptions into executable steps."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Convert the following task into an executable command."},
                {"role": "user", "content": task_description}
            ],
            max_tokens=50
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"LLM parsing error: {e}")
        raise HTTPException(status_code=500, detail="LLM parsing error")

def execute_task(task_description: str) -> str:
    """Executes a task securely by validating and running commands."""
    try:
        command = parse_task_with_llm(task_description)
        if not command:
            raise ValueError("Failed to parse task.")

        # Validate and execute securely
        command_parts = command.split()
        if command_parts[0] in ["rm", "delete"]:
            raise HTTPException(status_code=403, detail="File deletion is not allowed.")

        result = subprocess.run(command_parts, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            raise Exception(result.stderr)

        return result.stdout.strip()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Task execution timeout.")
    except Exception as e:
        logging.error(f"Task execution error: {e}")
        raise HTTPException(status_code=500, detail="Internal agent error")

@app.post("/run")
def run_task(task: str = Query(..., description="Task description in plain English")):
    """Executes a task based on the provided description."""
    try:
        result = execute_task(task)
        return {"status": "success", "message": result}
    except HTTPException as e:
        raise e
    except Exception:
        logging.exception("Unexpected server error")
        raise HTTPException(status_code=500, detail="Unexpected server error.")

@app.get("/read")
def read_file(path: str = Query(..., description="File path to read")):
    """Returns the content of the specified file."""
    real_path = validate_path(path)
    if not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        with open(real_path, "r", encoding="utf-8") as file:
            return {"status": "success", "content": file.read()}
    except Exception as e:
        logging.error(f"Error reading file {path}: {e}")
        raise HTTPException(status_code=500, detail="Error reading file")

def fetch_api_data(url: str, save_path: str):
    """Fetches data from an API and saves it securely."""
    validate_path(save_path)
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        with open(save_path, "w", encoding="utf-8") as file:
            file.write(response.text)
    except requests.RequestException as e:
        logging.error(f"API fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch API data.")

def run_sql_query(db_path: str, query: str):
    """Executes a SQL query safely using DuckDB."""
    validate_path(db_path)
    try:
        with duckdb.connect(db_path) as conn:
            result = conn.execute(query).fetchall()
        return result
    except Exception as e:
        logging.error(f"SQL query error: {e}")
        raise HTTPException(status_code=500, detail="Database query error")
