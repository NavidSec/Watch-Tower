#!/usr/bin/env python3
import os, json, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime
from config import config
from db import Programs, Subdomains, LiveSubdomains, http, upsert_program

def get_program_names_from_json_dir(json_dir):
    program_names = set()
    for root, _, files in os.walk(json_dir):
        for file in files:
            if file.endswith(".json"):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    pname = data.get("program_name")
                    if pname:
                        program_names.add(pname.strip().lower())
                except Exception as e:
                    print(f"Error reading {file}: {e}")
    return program_names

def sync_programs_and_related_data(json_dir):
    print(f"[{datetime.now()}] Starting sync process...")

    programs_in_json = get_program_names_from_json_dir(json_dir)

    for root, _, files in os.walk(json_dir):
        for file in files:
            if not file.endswith('.json'):
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                pname = data.get('program_name')
                scopes = data.get('scopes', [])
                ooscopes = data.get('ooscopes', [])
                providers = data.get('providers', [])

                if pname and scopes is not None and ooscopes is not None:
                    pname_lower = pname.strip().lower()
                    upsert_program(pname_lower, scopes, ooscopes,providers)
                else:
                    print(f"Missing data in {file}, skipping file")
            except Exception as e:
                print(f"Error processing {file}: {e}")

    print(f"[{datetime.now()}] Sync process finished successfully.")

if __name__ == "__main__":
    directory = os.path.join(config().get('WATCH_DIR'), 'programs')
    sync_programs_and_related_data(directory)
