#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import requests
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
    YELLOW = "\033[93m"
    BLUE = "\033[94m"

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_x9_for_url(url):
    url = url.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    
    print(f"\n{colors.BLUE}▶ {current_time()} - Starting x9 for URL: {url}{colors.RESET}")
    
    try:
        command = [
            "python3",
            "/home/navid/projects/tools/x9/x9_full.py",
            "-u", url,
            "-f",                
            "-gs", "all",        
            "-vs", "suffix",     
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        results = []
        full_stdout = []
        
        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                line = line.rstrip()
                full_stdout.append(line)
                print(f"{colors.GRAY}[x9]{colors.RESET} {line}")

                if line.startswith('{') or line.startswith('['):
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        
        stderr_output = process.stderr.read()
        returncode = process.wait()

        error = None
        if returncode != 0:
            error = f"x9 exited with code {returncode}: {stderr_output.strip() or 'No stderr output'}"
        elif stderr_output.strip():
            error = f"x9 stderr: {stderr_output.strip()}"

        return (url, results, error)

    except Exception as e:
        return (url, None, f"Exception: {str(e)}")
def x9(urls, max_workers=32):
    print(f"{colors.BLUE}{current_time()} - Running x9 on {len(urls)} URLs using {max_workers} workers...{colors.RESET}\n")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_x9_for_url, url): url for url in urls}

    for future in as_completed(futures):
        url = futures[future]
        try:
            url, results, error = future.result()
            
            if error:
                print(f"{colors.RED}[ERROR] {url}: {error}{colors.RESET}")
            
            if results:
                print(f"{colors.GREEN}[+] {len(results)} vulnerability results found for {url}:{colors.RESET}")
                for r in results:
                    print(json.dumps(r, indent=2, ensure_ascii=False))
            elif not error:
                print(f"{colors.GRAY}[-] No vulnerability results found for {url}.{colors.RESET}")

            print(f"{colors.BLUE}✔ {current_time()} - Finished x9 for URL: {url}{colors.RESET}\n")

        except Exception as exc:
            print(f"{colors.RED}[EXCEPTION] {url}: {exc}{colors.RESET}")

if __name__ == "__main__":
    https = http.objects().all()
    if not https:
        print(f"{colors.YELLOW}[-] No URLs found in the database.{colors.RESET}")
        sys.exit(0)

    valid_subdomain= [http.subdomain for http in https if http.status_code==200]

    # print(f"{colors.BLUE}{current_time()} - Checking status codes for {len(subdomain_to_check)} URLs...{colors.RESET}")
    # with ThreadPoolExecutor(max_workers=16) as executor:
    #     futures = [executor.submit(check_url_status, subdomain) for subdomain in subdomain_to_check]
    #     for future in as_completed(futures):
    #         result = future.result()
    #         if result:
    #             valid_subdomain.append(result)

    if valid_subdomain:
        print(f"\n{colors.BLUE}[+] Found {len(valid_subdomain)} valid URLs. Starting x9...{colors.RESET}")
        x9(valid_subdomain, max_workers=8)
    else:
        print(f"{colors.YELLOW}[-] No valid URLs to process. Exiting.{colors.RESET}")