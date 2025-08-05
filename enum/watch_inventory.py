#!/usr/bin/env python3
import os, sys, subprocess, requests, re, time, csv, io,tldextract
from datetime import datetime
from requests.exceptions import RequestException
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
from config import config
from database.db import *

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_content_from_github(file_path):
    url = f"https://raw.githubusercontent.com/trickest/inventory/main/{file_path}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[{current_time()}] Error fetching {url}: {e}")
        return None

def sync_program_data(program):
    program_name = program.program_name
    program_name_upper = program_name[0].upper() + program_name[1:]
    program_name_lower = program_name.lower()

    print(f"[{current_time()}] Starting sync for program: {program_name_lower}")

    hostnames_path = f"{program_name_upper}/hostnames.txt"
    hostnames_content = fetch_content_from_github(hostnames_path)
    if hostnames_content:
        print(f"[{current_time()}] Processing hostnames.txt for {program_name_lower} ...")
        for line in hostnames_content.splitlines():
            subdomain = line.strip()
            if subdomain:
                upsert_subdomain(program_name_lower, subdomain, "inventory")
    else:
        print(f"[{current_time()}] hostnames.txt not found for {program_name_lower}")

    dns_report_path = f"{program_name_upper}/dns-report.csv"
    dns_report_content = fetch_content_from_github(dns_report_path)

    if dns_report_content:
        print(f"[{current_time()}] Processing dns-report.csv for {program_name_lower} ...")
        csv_file = io.StringIO(dns_report_content)
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            subdomain = row.get('host', '').strip()
            ips_raw = row.get('a', '').strip()
            
            if subdomain and ips_raw:
                domain = get_domain_name(subdomain)
                program = Programs.objects(scopes=domain).first()
                ips = ips_raw.split(",") if ',' in ips_raw else [ips_raw]
                
                upsert_lives({
                    "program_name": program.program_name,
                    "subdomain": subdomain,
                    "ips": ips,
                    "info": f"DNS data from {dns_report_path}",
                    "domain": domain
                })
    else:
        print(f"[{current_time()}] dns-report.csv not found or empty for {program_name_lower}")

    server_report_path = f"{program_name_upper}/server-report.csv"
    server_report_content = fetch_content_from_github(server_report_path)
    if server_report_content:
        print(f"[{current_time()}] Processing server-report.csv for {program_name_lower} ...")
        csv_file = io.StringIO(server_report_content)
        reader = csv.DictReader(csv_file)
        for row in reader:
            subdomain = row.get('input', '').strip()
            status_code = int(row.get('status_code', '0').strip())
            ip = row.get('ip', '').strip()
            cdn_name = row.get('cdn', '').strip()
            if subdomain:
                upsert_http({
                    "program_name": program_name_lower,
                    "subdomain": subdomain,
                    "scope": get_domain_name(subdomain),
                    "status_code": status_code,
                    "ips": [ip] if ip else [],
                    "tech": cdn_name,
                    "title": row.get('title', ''),
                    "headers": {},
                    "url": f"http://{subdomain}",
                    "final_url": f"http://{subdomain}",
                    "favicon": None
                })
    else:
        print(f"[{current_time()}] server-report.csv not found or empty for {program_name_lower}")

    print(f"[{current_time()}] Finished syncing program: {program_name_lower}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_inventory <program_name>")
        sys.exit(1)

    program_name_arg = sys.argv[1]
    programs = Programs.objects(program_name=program_name_arg)
    if programs:
        for program in programs:
            print(f"[{current_time()}] Running inventory sync for '{program.program_name}'")
            sync_program_data(program)
    else:
        print(f"[{current_time()}] Program '{program_name_arg}' not found in database")
