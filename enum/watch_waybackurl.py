#!/usr/bin/env python3
import os, sys, subprocess, requests, re, time
from requests.exceptions import RequestException, ChunkedEncodingError
from datetime import datetime
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
            print(f"[{current_time()}] started with digit, skipping '{subdomain_to_check}'")
            return True
    return False
class colors:
    GRAY = "\033[90m"

def waybackurl(domain, program):
    url = f"https://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=text&fl=original&collapse=urlkey"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; subdomain-collector/1.0)'}
    max_retries, retry_delay = 5, 5
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[{current_time()}]  Fetching from Wayback (attempt {attempt}): {url}")
            response = requests.get(url, headers=headers, timeout=120)
            response.raise_for_status()
            break
        except Exception as e:
            print(f"[{current_time()}]  Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                print(f"[{current_time()}] Failed after {max_retries} attempts.")
                return
    found = set()
    escaped = re.escape(domain)
    pattern = re.compile(rf"https?://([\w.-]+)\.{escaped}", re.IGNORECASE)
    for line in response.text.splitlines():
        m = pattern.search(line)
        if m:
            sub = m.group(1).lower() + '.' + domain
            if sub != domain:
                found.add(sub)
    print(f"[{current_time()}] Found {len(found)} subdomains for {domain}")
    for sub in sorted(found):
        if not should_skip_subdomain(sub):
            upsert_subdomain(program.program_name, sub, 'waybackurl')

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else None
    if not domain:
        print("Usage: watch_waybackurl domain")
        sys.exit(1)
    program = Programs.objects(scopes=domain).first()
    if not program:
        print(f"[{current_time()}] scope for '{domain}' does not exist in watch")
        sys.exit(0)
    print(f"[{current_time()}] running waybackurl module for '{domain}'")
    waybackurl(domain, program)
