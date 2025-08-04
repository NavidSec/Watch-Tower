#!/usr/bin/env python3
import os, sys, subprocess, tempfile, json, ipaddress, re, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import config
from db import *

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_command(command):
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            print(f"Timeout: killing command -> {command}")
            process.kill()
            stdout, stderr = process.communicate()
            return None
        if process.returncode != 0:
            print(f"Error: {stderr}")
            return None
        return stdout.splitlines()
    except Exception as e:
        print(f"Exception: {e}")
        return None


def dnsgen_and_split(dynamic_main, domain, parts=15):
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_input:
        with open(dynamic_main, 'r') as f:
            for word in f:
                word = word.strip()
                if word:
                    temp_input.write(f"{word}.{domain}\n")
        input_path = temp_input.name

    output_path = input_path + "_dnsgen"
    command = f"dnsgen {input_path} > {output_path}"
    subprocess.run(command, shell=True)

    with open(output_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    chunk_size = math.ceil(len(lines) / parts)
    files = []

    for i in range(parts):
        part_lines = lines[i * chunk_size : (i + 1) * chunk_size]
        part_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=f'_part{i}.txt')
        part_file.write('\n'.join(part_lines))
        part_file.close()
        files.append(part_file.name)

    return files

def filter_subdomains(subs_list, domain):
    filtered = []
    for sub in subs_list:
        if not sub:
            continue
        if not sub.endswith(f".{domain}"):
            sub = f"{sub}.{domain}"
        if len(sub) > 50:
            continue
        if re.search(r"[^a-zA-Z0-9\-.]", sub):
            continue
        if sub.count('.') > 5:
            continue
        filtered.append(sub.lower())
    return list(set(filtered))

# def merge_and_filter(static_file, dynamic_file, domain):
#     print("Merging and filtering subdomains...")
#     subs_set = set()
#     for filename in [static_file, dynamic_file]:
#         with open(filename, "r") as f:
#             for line in f:
#                 line = line.strip()
#                 if not line:
#                     continue
#                 if not line.endswith(f".{domain}"):
#                     line = f"{line}.{domain}"
#                 subs_set.add(line)
#     filtered_subs = filter_subdomains(list(subs_set), domain)
#     temp = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt', dir=os.path.expanduser("~/tmp"))
#     for sub in sorted(filtered_subs):
#         temp.write(sub + "\n")
#     temp.close()
#     return temp.name

def run_shuffledns_parallel(domain, wordlist_paths):
    def run_single(file):
        command = f"shuffledns -d {domain} -t 1000 -l {file} -r {config().get('RESOLVERS')} -mode resolve -silent -json"
        print(f"[{current_time()}] Running shuffledns on: {file}")
        results = run_command(command)
        if results:
            for line in results:
                try:
                    obj = json.loads(line)
                    sub = obj.get("host")
                    ips = obj.get("a", [])
                    if ips:
                        ips = [ans.get("a") for ans in ips if ans.get("a")]
                    else:
                        ips = []

                    info = detect_ip_info(ips)
                    upsert_lives({"subdomain": sub, "domain": domain, "ips": ips, "info": info})
                    print(f"[{current_time()}] {sub} -> {ips} | Info: {info}")
                except Exception as e:
                    print(f"[{current_time()}] JSON parse error: {e}")

    with ThreadPoolExecutor(max_workers=15) as executor:
        executor.map(run_single, wordlist_paths)

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else None
    if not domain:
        print("usage: watch_ns domain")
        sys.exit(1)

    program = Programs.objects(scopes=domain)
    if program:
        print(f"{current_time()} running shuffledns module for {domain}")
        dynamic_main = config().get("DYNAMIC_WORDLIST")
        wordlist_parts = dnsgen_and_split(dynamic_main, domain, parts=15)

        start = datetime.now()
        run_shuffledns_parallel(domain, wordlist_parts)
        end = datetime.now()
        print(f"[{current_time()}] Duration: {end - start}")

    else:
        print(f"{current_time()} scope for {domain} not found")
