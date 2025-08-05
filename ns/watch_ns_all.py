#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
import json
from datetime import datetime
import ipaddress
import concurrent.futures

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import *
from config import config

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def chunk_list(lst, n):
    """تقسیم لیست lst به n بخش تقریبا مساوی"""
    k, m = divmod(len(lst), n)
    return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

def detect_ip_info(ip_list):
    try:
        cdn_file_path = config().get("CDN")
        if not cdn_file_path or not os.path.exists(cdn_file_path):
            sys.stderr.write(f"[{current_time()}] Warning: CDN file not found or not configured at {cdn_file_path}\n")
            return "None"

        with open(cdn_file_path) as f:
            cdn_data = json.load(f)

        cdn_ranges = {cdn: [ipaddress.ip_network(cidr) for cidr in ranges] for cdn, ranges in cdn_data.items()}

        for ip_str in ip_list:
            try:
                ip = ipaddress.ip_address(ip_str.strip())
                if ip.is_private:
                    return "Private"
                for provider, nets in cdn_ranges.items():
                    for net in nets:
                        if ip in net:
                            return f"CDN - {provider}"
            except ValueError:
                continue
    except Exception as e:
        sys.stderr.write(f"[{current_time()}] Error in detect_ip_info: {e}\n")
    return "None"
class colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

def dnsx_worker(subdomains_chunk, domain):
    if not subdomains_chunk:
        return

    subdomains_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as temp_file:
            for sub in subdomains_chunk:
                temp_file.write(f"{sub}\n")
            subdomains_file = temp_file.name

        command = [
            "dnsx",
            "-l", subdomains_file,
            "-silent",
            "-resp",
            "-json",
            "-retry", "3",
            "-r",  config().get("RESOLVERS")
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                host = obj.get("host")
                ips = obj.get("a", [])

                info = detect_ip_info(ips)

                upsert_lives({
                    "subdomain": host,
                    "domain": domain,
                    "ips": ips,
                    "info": info
                })

            except Exception:
                continue

        process.stdout.close()
        process.wait()
        process.stderr.close()

    finally:
        if subdomains_file and os.path.exists(subdomains_file):
            os.remove(subdomains_file)

def dnsx_parallel(subdomains_array, domain):
    if not subdomains_array:
        return

    max_workers = 4
    chunk_count = min(max_workers, len(subdomains_array))
    chunks = chunk_list(subdomains_array, chunk_count)

    print(f"{colors.GREEN}[{current_time()}] Running dnsx in parallel with {chunk_count} chunks for domain {domain}{colors.RESET}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(dnsx_worker, chunk, domain) for chunk in chunks]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                sys.stderr.write(f"[{current_time()}] Error in parallel dnsx worker: {e}\n")

if __name__ == "__main__":
    programs = Programs.objects().all()
    for program in programs:
        for scope in program.scopes:
            domain = scope
            subs = Subdomains.objects(scope=domain)  
            subdomains_array = [sub.subdomain for sub in subs]
            dnsx_parallel(subdomains_array, domain)
