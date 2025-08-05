#!/usr/bin/env python3
import os, sys, time, requests, tldextract,re
from collections import deque
from threading import Lock
from datetime import datetime 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from db import *
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_KEYS = [
    '98998e67521c632726585193592b2d2488c5a333cf5de3e3b2a8f4ca7f0bed48',
    'af38997f62e9abb69387b4e8bc2e8fc4e276aef49985c9d408b9ea32d6d5f43a',
    '9bb6167748dd5b296a98aaa0d70e43edf5c7fd24afae7e489ac3dc7ee82f5f68'
]
SECONDS_BETWEEN_USES = 3
api_usage = {key: 0 for key in API_KEYS}
api_queue = deque(API_KEYS)
blocked_keys = {}
lock = Lock()
class colors:
    GRAY = "\033[90m"

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

def get_next_api_key():
    while True:
        with lock:
            now = time.time()
            for _ in range(len(api_queue)):
                key = api_queue.popleft()

                if key in blocked_keys:
                    if blocked_keys[key] > now:
                        api_queue.append(key)
                        continue
                    else:
                        del blocked_keys[key]

                elapsed = now - api_usage[key]
                if elapsed >= SECONDS_BETWEEN_USES:
                    api_usage[key] = now
                    api_queue.append(key)
                    return key
                api_queue.append(key)
        time.sleep(1)

def virustotal(domain):
    url = f"https://www.virustotal.com/api/v3/domains/{domain}/subdomains"
    subdomains = set()

    session = requests.Session()
    retries = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    print(f"[{current_time()}] Running virustotal module for '{domain}'") 

    while url:
        start_time = time.time()

        api_key = get_next_api_key()
        headers = {
            "x-apikey": api_key,
            "Accept": "application/json"
        }

        try:
            response = session.get(url, headers=headers, timeout=60)
        except requests.exceptions.SSLError as ssl_error:
            print(f"[{current_time()}] [SSL Error] {ssl_error}") 
            break
        except requests.RequestException as e:
            print(f"[{current_time()}]  Request failed: {e}") 
            break

        if response.status_code == 429:
            print(f"[{current_time()}]  Rate limit reached for key {api_key[:6]}..., blocking key for 5 minutes.") 
            blocked_keys[api_key] = time.time() + 300
            continue
        elif response.status_code != 200:
            print(f"[{current_time()}]  Error {response.status_code}: {response.text}") 
            break

        try:
            data = response.json()
        except Exception as e:
            print(f"[{current_time()}]  JSON decode error: {e}") 
            break

        for item in data.get("data", []):
            subdomain = item.get("id")
            if subdomain:
                extracted = tldextract.extract(subdomain)
                root_domain = f"{extracted.domain}.{extracted.suffix}"
                if root_domain == domain and extracted.subdomain:
                    full_domain = f"{extracted.subdomain}.{root_domain}".lower()
                    if full_domain not in subdomains:
                        subdomains.add(full_domain)
                        program = Programs.objects(scopes=domain).first() 
                        if program:
                            if not should_skip_subdomain(full_domain):
                                upsert_subdomain(program.program_name, full_domain, 'virustotal')

        url = data.get("links", {}).get("next")

        elapsed = time.time() - start_time
        if elapsed < 1:
            time.sleep(1)

    return list(subdomains)

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else None
    if not domain:
        print("Usage: watch_virustotal domain")
        sys.exit(1)
    program = Programs.objects(scopes=domain).first()
    if not program:
        print(f"[{current_time()}] scope for '{domain}' does not exist in watch")
        sys.exit(0)
    virustotal(domain)