#!/usr/bin/env python3
import os,sys,subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import *
from config import config
from datetime import datetime

class colors:
    GRAY = "\033[90m"
    RESET = "\033[0m"

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def run_command_in_zsh(command):
    try:
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error occurred running command: {command}")
            print(result.stderr)
            return False
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        print("Status: FAIL", exc.returncode, exc.output)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: watch_enum_program program_name")
        sys.exit(1)
    program_name = sys.argv[1]
    program = Programs.objects(program_name=program_name).first()
    if not program:
        print(f"[{current_time()}] Program '{program_name}' not found in database.")
        sys.exit(1)

    scopes = program.scopes 

    enum_path = os.path.join(config().get('WATCH_DIR'), 'enum')

    print(f"[{current_time()}] Starting enumeration for program '{program_name}'")

    for scope in scopes:
        print(f"[{current_time()}] Enumerating subdomains for domain: {scope}")
        
        print("subfinder is Running....")
        run_command_in_zsh(f"python3 {os.path.join(enum_path, 'watch_subfinder.py')} {scope}")

        print("crtsh is Running....")
        run_command_in_zsh(f"python3 {os.path.join(enum_path, 'watch_crtsh.py')} {scope}")

        # print("abuseipdb is Running....")
        # run_command_in_zsh(f"python3 {os.path.join(enum_path, 'watch_abuseipdb.py')} {scope}")

        print("waybackurl is Running....")
        run_command_in_zsh(f"python3 {os.path.join(enum_path, 'watch_waybackurl.py')} {scope}")

        print("virustotal is Running....")
        run_command_in_zsh(f"python3 {os.path.join(enum_path, 'watch_virustotal.py')} {scope}")

    print(f"[{current_time()}] Enumeration completed for program '{program_name}'")
