#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
import json
from datetime import datetime
import ipaddress

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import *
from config import config

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def run_command_in_zsh(command):
    try:
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        print(f"[{current_time()}] Error executing command: {command}")
        print(f"[{current_time()}] Status: FAIL, Return Code: {exc.returncode}, Error: {exc.stderr.strip()}")
        return None

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

def dnsx(subdomains_array, domain):
    print(domain)
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as temp_file:
            for sub in subdomains_array:
                temp_file.write(f"{sub}\n")
            temp_file_path = temp_file.name

        print(f"[{current_time()}] Created temporary subdomain list: {temp_file_path}")
        
        command = f"dnsx -l {temp_file_path} -silent -resp -json -retry 3 -r {config().get("RESOLVERS")}"
        print(f"[{current_time()}] Executing command: {command}")

        results = run_command_in_zsh(command)
        if results:
            for line in results:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        print(f"[{current_time()}] Warning: JSON is not a dict: {line}")
                        continue
                    
                    host = obj.get("host")
                    ips = obj.get("a", [])
                    if isinstance(ips, list) and all(isinstance(ip, dict) for ip in ips):
                        ips = [ans.get("a") for ans in ips if ans.get("a")]

                    info = detect_ip_info(ips)

                    upsert_lives({
                        "subdomain": host,
                        "domain": domain,
                        "ips": ips,
                        "info": info
                    })
                except json.JSONDecodeError:
                    print(f"[{current_time()}] Could not parse DNSX JSON output: {line}")
                except Exception as e:
                    print(f"[{current_time()}] Unexpected error: {e} — line was: {line}")
        else:
            print(f"[{current_time()}] dnsx command returned no results or failed.")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: script.py <program_name>")
        sys.exit(1)

    program_name = sys.argv[1]
    program = Programs.objects(program_name=program_name).first()

    if not program:
        print(f"[!] Program '{program_name}' not found in database.")
        sys.exit(1)

    print(f"[{current_time()}] Starting processing for program: {program_name}")

    for domain in program.scopes:
        print(f"[{current_time()}] Processing domain: {domain}")

        subs = Subdomains.objects(scope=domain)
        subdomains_array = [sub.subdomain for sub in subs if sub.subdomain]

        if not subdomains_array:
            print(f"[{current_time()}] No subdomains found for domain: {domain}")
            continue

        dnsx(subdomains_array, domain)

    print(f"[{current_time()}] Finished processing program: {program_name}")
