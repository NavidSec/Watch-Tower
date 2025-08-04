#!/usr/bin/env python3
import os, sys, subprocess
from datetime import datetime 
import re 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from db import *
import tldextract

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def should_skip_subdomain(subdomain_to_check):

    if re.match(r'^\d+\.', subdomain_to_check):
        extracted = tldextract.extract(subdomain_to_check)
        root_domain = f"{extracted.domain}.{extracted.suffix}"
        
        if root_domain in ['hubspotpagebuilder.com', 'hs-sites.com']:
            print(f"[{current_time()}] started whith digit cant to upsert '{subdomain_to_check}'")
            return True
    return False

def run_command_in_zsh(command):
    try:
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[{current_time()}] Error occurred: {result.stderr.strip()}")
            return False
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        print(f"[{current_time()}] Status: FAIL {exc.returncode}, {exc.output.strip()}")
        return False

class colors:
    GRAY = "\033[90m"

def subfinder(domain):
    command = f"subfinder -d {domain} -silent -all"
    print(f"{colors.GRAY}[{current_time()}] Executing command: {command}{colors.GRAY}")
    
    res = run_command_in_zsh(command)

    if not res or not isinstance(res, list):
        res = []

    print(f"{colors.GRAY}[{current_time()}] done for {domain}, results: {len(res)}{colors.GRAY}")
    return res


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_subfinder.py <domain>") 
        sys.exit(1)

    domain = sys.argv[1]

    program = Programs.objects(scopes=domain).first()
    if not program:
        print(f"[{current_time()}] [!] Domain '{domain}' not found in Programs scope.")
        sys.exit(1)

    if program: 
        print(f"[{current_time()}] running subfinder module for '{domain}'")
        subs = subfinder(domain)
        for sub in subs:
            if not should_skip_subdomain(sub):
                upsert_subdomain(program.program_name, sub , 'subfinder')
    else :
        print(f"[{current_time()}] scope for '{domain}' does not exist in watch")