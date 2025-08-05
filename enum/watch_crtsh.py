#!/usr/bin/env python3
import os, sys, subprocess, requests,time
from datetime import datetime # اضافه شده
import re # اضافه شده برای استفاده از عبارات با قاعده
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from db import *
import tldextract

def run_command_in_zsh(command):
    try:
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[{current_time()}] Error occurred: {result.stderr.strip()}") # اضافه کردم current_time
            return False
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        print(f"[{current_time()}] Status: FAIL {exc.returncode}, {exc.output.strip()}") 

class colors:
    GRAY = "\033[90m"

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def should_skip_subdomain(subdomain_to_check):

    if re.match(r'^\d+\.', subdomain_to_check):
        extracted = tldextract.extract(subdomain_to_check)
        root_domain = f"{extracted.domain}.{extracted.suffix}"
        
        if root_domain in ['hubspotpagebuilder.com', 'hs-sites.com']:
            print(f"[{current_time()}] started whith digit cant to upsert '{subdomain_to_check}'")
            return True
    return False

def crtsh(domain, max_retries=5, delay=5):
    url = f"https://crt.sh/?q=%.{domain}&output=json"
    print(f"[{current_time()}] [+] Fetching crt.sh data for {domain} ...") 

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, timeout=60)
            if res.status_code == 200:
                try:
                    data = res.json()
                except ValueError:
                    print(f"[{current_time()}] [ERROR] Could not parse JSON response from crt.sh") 
                    return None

                results = set()
                for entry in data:
                    name_value = entry.get("name_value")
                    if name_value:
                        for sub in name_value.splitlines():
                            if sub.startswith('*.'): 
        
                                results.add(sub.lower().strip())
                            elif sub.endswith(f".{domain}") or sub == domain:
                                results.add(sub.lower().strip())

                if not results:
                    print(f"[{current_time()}] [INFO] No subdomains found on crt.sh for '{domain}'") 
                return list(results)

            elif res.status_code in [502, 503, 504]:
                print(f"[{current_time()}] [WARN] crt.sh server returned {res.status_code}, attempt {attempt}/{max_retries}. Retrying in {delay}s...") 
            else:
                print(f"[{current_time()}] [ERROR] crt.sh returned status {res.status_code}") 
                return None

        except requests.exceptions.RequestException as e:
            print(f"[{current_time()}] [ERROR] Connection to crt.sh failed on attempt {attempt}/{max_retries}: {e}") 
        
        if attempt < max_retries:
            time.sleep(delay)

    print(f"[{current_time()}] [ERROR] crt.sh query failed after {max_retries} attempts.") 
    return None

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else None

    if not domain:
        print("Usage: watch_crtsh domain")
        sys.exit(1)

    program = Programs.objects(scopes=domain).first()
    if program:
        print(f"[{current_time()}] running crtsh module for '{domain}'")
        subs = crtsh(domain)

        if subs is None:
            print(f"[{current_time()}] [WARN] crt.sh query for '{domain}' failed or returned no data.")
        else:
            for sub in subs:
                    if not should_skip_subdomain(sub):
                        upsert_subdomain(program.program_name, sub, 'crtsh')
            print(f"[{current_time()}] [+] Found {len(subs)} subdomain(s) for '{domain}'")
    else:
        print(f"[{current_time()}] scope for '{domain}' does not exist in watch")