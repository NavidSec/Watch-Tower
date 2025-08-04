#!/usr/bin/env python3
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait
from termcolor import colored
from math import ceil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import *
from config import config

MAX_COMMANDS_PER_SCOPE = 4
BATCH_SIZE = 10 

def print_colored(msg, color):
    try:
        print(colored(msg, color))
    except:
        print(msg)

def run_command(command):
    print_colored(f"[Running] {command}", "yellow")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            if result.stdout.strip():
                print_colored(f"[Output] {result.stdout.strip()}", "green")
        else:
            print_colored(f"[Error] Command: {command}", "red")
            if result.stderr.strip():
                print_colored(f"[stderr] {result.stderr.strip()}", "red")
    except subprocess.TimeoutExpired:
        print_colored(f"[Timeout] {command}", "blue")
    except Exception as e:
        print_colored(f"[Exception] {e} - Command: {command}", "blue")

def process_scope(scope, providers, enum_path):
    commands = [
        f"python3 {os.path.join(enum_path, f'watch_{provider}.py')} {scope}"
        for provider in providers
    ]
    with ThreadPoolExecutor(max_workers=MAX_COMMANDS_PER_SCOPE) as cmd_executor:
        futures = [cmd_executor.submit(run_command, cmd) for cmd in commands]
        wait(futures)
        wait(futures)

def batch_process_scopes(scopes, providers, enum_path):
    total = len(scopes)
    for i in range(0, total, BATCH_SIZE):
        current_batch = scopes[i:i+BATCH_SIZE]
        print_colored(f"\n[Batch] Processing scopes {i+1} to {i+len(current_batch)} of {total}", "cyan")
        with ThreadPoolExecutor(max_workers=len(current_batch)) as scope_executor:
            futures = [scope_executor.submit(process_scope, scope, providers, enum_path) for scope in current_batch]
            wait(futures)

def main():
    enum_path = os.path.join(config().get('WATCH_DIR'), 'enum')

    programs = Programs.objects.all()
    for program in programs:
        run_command(f"python3 {os.path.join(enum_path, 'watch_inventory.py')} {program.program_name}")
        
        scopes = program.scopes or []
        providers = program.providers or []

        if not scopes or not providers:
            continue

        batch_process_scopes(scopes, providers, enum_path)

if __name__ == "__main__":
    main()
