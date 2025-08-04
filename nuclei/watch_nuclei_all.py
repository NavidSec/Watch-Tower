#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import config
from db import *

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_nuclei_for_url(url):
    try:
        command = [
            "nuclei",
            "-u", url,
            "-silent",
            "-jsonl",
            "-config", os.path.join(config().get("WATCH_DIR"), "nuclei/public-config.yaml"),
            "-rate-limit", "80",
            "-concurrency", "40",
            "-timeout", "10",
            "-retries", "2"
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_lines = []
        stderr_lines = []

        for line in process.stdout:
            stdout_lines.append(line.strip())

        stderr_lines = process.stderr.read().strip()
        process.wait()

        results = []
        for line in stdout_lines:
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                results.append({"raw_output": line})

        if process.returncode != 0:
            return (url, results, f"Nuclei exited with code {process.returncode}: {stderr_lines or 'No stderr output'}")

        if stderr_lines:
            return (url, results, f"Nuclei stderr: {stderr_lines}")

        return (url, results, None)

    except Exception as e:
        return (url, None, f"Exception: {str(e)}")

def nuclei(urls, max_workers=32):
    print(f"{current_time()} ▶ Running Nuclei on {len(urls)} URLs using {max_workers} workers...\n")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_nuclei_for_url, url): url for url in urls}

        for future in as_completed(futures):
            url = futures[future]
            try:
                url, results, error = future.result()
                print(f"{colors.GRAY}>> {url}{colors.RESET}")

                if error:
                    print(f"{colors.RED}[ERROR] {error}{colors.RESET}")

                if results:
                    print(f"{colors.GREEN}[+] {len(results)} results:{colors.RESET}")
                    for r in results:
                        print(json.dumps(r, indent=2, ensure_ascii=False))
                else:
                    print("[-] No results at all.")

            except Exception as exc:
                print(f"{colors.RED}[EXCEPTION] {url}: {exc}{colors.RESET}")

if __name__ == "__main__":
    https = http.objects().all()
    if https:
        urls = [http.url for http in https]
        nuclei(urls, max_workers=8)
