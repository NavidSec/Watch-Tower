#!/usr/bin/env python3
import os,re,sys,time,tldextract,cloudscraper
from datetime import datetime
from bs4 import BeautifulSoup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from db import Programs, upsert_subdomain

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def should_skip_subdomain(sub):
    if re.match(r'^\d+\.', sub):
        ext = tldextract.extract(sub)
        root = f"{ext.domain}.{ext.suffix}"
        if root in ['hubspotpagebuilder.com', 'hs-sites.com']:
            print(f"[{current_time()}] starts with digit, skipping '{sub}'")
            return True
    return False

def fetch_abuseipdb_subdomains(domain):
    url = f"https://www.abuseipdb.com/whois/{domain}"
    print(f"[{current_time()}] Fetching AbuseIPDB for {domain}...")

    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"[{current_time()}] HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        subs = set()

        for hdr in soup.find_all('h4'):
            if 'subdomains' in hdr.get_text(strip=True).lower():
                ul = hdr.find_next('ul')
                if not ul:
                    break
                for li in ul.find_all('li'):
                    raw = li.get_text(strip=True)
                    if not raw:
                        continue
                    sub = raw if raw.endswith(domain) else f"{raw}.{domain}"
                    subs.add(sub.lower())
                break

        return sorted(subs)

    except Exception as e:
        print(f"[{current_time()}] [ERROR] fetch failed: {e}")
        return []


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: watch_abuseipdb <domain>")
        sys.exit(1)

    domain = sys.argv[1].strip().lower()
    program = Programs.objects(scopes=domain).first()

    if not program:
        print(f"[{current_time()}] scope for '{domain}' not found.")
        sys.exit(1)

    print(f"[{current_time()}] running abuseipdb module for '{domain}'")
    found = fetch_abuseipdb_subdomains(domain)

    if not found:
        print(f"[{current_time()}] [INFO] No subdomains found for '{domain}'")
    else:
        count = 0
        for sub in found:
            if sub.startswith('*.'):
                scope = sub[2:]
                if scope not in program.scopes:
                    program.scopes.append(scope)
                    program.save()
                    print(f"[{current_time()}] added wildcard scope: {scope}")
                    count += 1
                else:
                    print(f"[{current_time()}] wildcard '{scope}' exists")
            else:
                if not should_skip_subdomain(sub):
                    upsert_subdomain(program.program_name, sub, 'abuseipdb')
                    count += 1
        print(f"[{current_time()}] [+] {count} observed subdomains for '{domain}'")
