#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import json
import threading
import re
import ipaddress
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import config
from db import *

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

def detect_ip_info(ip_list):
    try:
        cdn_file_path = config().get("CDN")
        if not cdn_file_path or not os.path.exists(cdn_file_path):
            print(f"[{current_time()}] Warning: CDN file path not configured or file not found at {cdn_file_path}. Cannot detect CDN info.")
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
        print(f"[{current_time()}] Error in detect_ip_info: {e}")
    return "None"

def httpx_file(subdomain_info_pairs, domain):
    if not subdomain_info_pairs:
        return

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as temp_file:
        temp_file.write('\n'.join(sub for sub, _ in subdomain_info_pairs))
        temp_path = temp_file.name

    command = f"httpx -l {temp_path} -silent -json -favicon -fhr -tech-detect -irh -include-chain -timeout 10 -t 100 -retries 5 \
    -rl 200 -nf -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS 20180101 Firefox/108.0)' -H 'Referer: https://{subdomain}'"
    print(f"{colors.GRAY}Executing command: {command}{colors.RESET}")

    try:
        process = subprocess.Popen(
            ["zsh", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            bufsize=1
        )

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                json_obj = json.loads(line)
                subdomain = json_obj.get("input")
                if not subdomain:
                    continue

                matched_info = next((i for s, i in subdomain_info_pairs if s == subdomain), "None")

                upsert_http({
                    "subdomain": subdomain,
                    "scope": domain,
                    "ips": json_obj.get('a', ''),
                    "tech": json_obj.get('tech', ''),
                    "title": json_obj.get('title', ''),
                    "status_code": json_obj.get('status_code', ''),
                    "headers": json_obj.get('header', {}),
                    "url": json_obj.get('url', ''),
                    "final_url": json_obj.get('final_url', ''),
                    "favicon": json_obj.get('favicon', ''),
                    "info": matched_info
                })

            except json.JSONDecodeError:
                print(f"{colors.RESET}[{current_time()}] JSON decode error for line: {line}{colors.RESET}")
    except Exception as e:
        print(f"[{current_time()}] Error running command: {e}")
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    programs = Programs.objects().all()

    for program in programs:
        for domain in program.scopes:
            domain_regex = re.compile(fr"(.+\.)?{re.escape(domain)}$", re.IGNORECASE)
            subs_cursor = LiveSubdomains.objects(subdomain=domain_regex)
            subdomain_info_pairs = [(sub.subdomain, sub.info) for sub in subs_cursor]

            print(f"{current_time()} running httpx module for {domain}, total subdomains: {len(subdomain_info_pairs)}")

            if len(subdomain_info_pairs) > 5:
                parts = split_list(subdomain_info_pairs, 5)
                threads = []
                for part in parts:
                    t = threading.Thread(target=httpx_file, args=(part, domain))
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
            else:
                httpx_file(subdomain_info_pairs, domain)
