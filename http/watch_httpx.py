#!/usr/bin/env python3
import os, sys, subprocess, tempfile,json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from db import *
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_command_in_zsh(command):
    try:
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True)

        if result.returncode != 0:
            print("Error occurred:", result.stderr)
            return False

        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print("Status : FAIL", exc.returncode, exc.output)

# def create_temp_file(data):
#     
#     with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
#         temp_file.write(data)
#         return temp_file.name

def httpx(subdomains_array, domain):

    def process_subdomain(subdomain):
        command = f"echo {subdomain} | httpx -silent -json -favicon -fhr -tech-detect -irh -include-chain -timeout 5 --threads 5 -retries 5 -rate-limit 4 -ports 443,80 -extract-fqdn -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS 20180101 Firefox/108.0)' -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS 20180101 Firefox/108.0)' -H 'Referer: https://{subdomain}'"
        #print(f"{colors.GRAY}Executing command: {command}{colors.RESET}")

        out = run_command_in_zsh(command)
        if not out:
            return

        results = out.splitlines()

        for result in results:
            try:
                json_obj = json.loads(result)

                upsert_http({
                    "subdomain": subdomain,
                    "scope": domain,
                    "ips": json_obj.get('a', ''),
                    "tech": json_obj.get('tech') if isinstance(json_obj.get('tech'), (list, tuple)) else [json_obj.get('tech')] if json_obj.get('tech') else [],
                    "title": json_obj.get('title', ''),
                    "status_code": json_obj.get('status_code', ''),
                    "headers": json_obj.get('header', {}),
                    "url": json_obj.get('url', ''),
                    "final_url": json_obj.get('final_url', ''),
                    "favicon": json_obj.get('favicon', '')
                })

            except json.JSONDecodeError:
                print(f"{colors.RESET} JSON decode error for result: {result}{colors.RESET}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_subdomain, sub): sub for sub in subdomains_array}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                sub = futures[fut]
                print(f"{colors.RESET} Exception while processing {sub}: {e}{colors.RESET}")

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else False
    if not domain:
        print("usage: watch_ns domain")
        sys.exit(1)

    subs = LiveSubdomains.objects(scope=domain)
    if subs:
        print(f"{current_time()} running dnsx module for {domain}")
        httpx([sub.subdomain for sub in subs], domain)
