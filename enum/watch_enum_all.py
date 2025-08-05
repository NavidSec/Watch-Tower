#!/usr/bin/env python3
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from termcolor import colored
from math import ceil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import *
from config import config

MAX_COMMANDS_PER_SCOPE = 4
BATCH_SIZE = 5

PROVIDER_COLORS = {}
VIRUSTOTAL_RATE_LIMITED = False

def print_colored(msg, color='white'):
    try:
        print(colored(msg, color), end='\n\n\n')
    except:
        print(msg, end='\n\n\n')

def get_provider_info(command):
    try:
        parts = command.split()
        script_path_index = -1
        for i, part in enumerate(parts):
            if part.endswith('.py'):
                script_path_index = i
                break
        
        if script_path_index == -1:
            return 'General', 'white'

        script_name = parts[script_path_index]
        base_name = os.path.basename(script_name)
        provider_name = base_name.replace('watch_', '').replace('.py', '')
        
        color = PROVIDER_COLORS.get(provider_name, 'yellow')
        return provider_name, color
    except Exception:
        return 'General', 'white'

def run_command(command):
    provider, color = get_provider_info(command)

    print_colored(f"[{provider}] [Running] {command}", color)
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            if result.stdout.strip():
                print_colored(f"[{provider}] [Output] {result.stdout.strip()}", color)
            return "SUCCESS"
        else:
            stderr_output = result.stderr.strip() if result.stderr else ""
            print_colored(f"[{provider}] [Error] Command failed: {command}", color)
            if stderr_output:
                print_colored(f"[{provider}] [stderr] {stderr_output}", color)
            
            if provider == 'virustotal' and '429' in stderr_output:
                print_colored(f"[{provider}] [Rate Limit] VirusTotal API limit reached. Disabling for this session.", 'yellow')
                return "RATE_LIMITED"
            
            return "ERROR"
            
    except subprocess.TimeoutExpired:
        print_colored(f"[{provider}] [Timeout] {command}", color)
        return "ERROR"
    except Exception as e:
        print_colored(f"[{provider}] [Exception] {e} - Command: {command}", color)
        return "ERROR"

def process_scope(scope, providers, enum_path):
    global VIRUSTOTAL_RATE_LIMITED

    commands_to_run = []
    for provider in providers:
        if provider == 'virustotal' and VIRUSTOTAL_RATE_LIMITED:
            print_colored(f"[System] [Skipping] VirusTotal for '{scope}' due to previous rate limit.", 'blue')
            continue
        
        commands_to_run.append(
            f"python3 {os.path.join(enum_path, f'watch_{provider}.py')} {scope}"
        )

    if not commands_to_run:
        return

    with ThreadPoolExecutor(max_workers=MAX_COMMANDS_PER_SCOPE) as cmd_executor:
        futures = {cmd_executor.submit(run_command, cmd): cmd for cmd in commands_to_run}
        
        for future in as_completed(futures):
            status = future.result()
            if status == "RATE_LIMITED":
                VIRUSTOTAL_RATE_LIMITED = True

def batch_process_scopes(scopes, providers, enum_path):
    total = len(scopes)
    for i in range(0, total, BATCH_SIZE):
        current_batch = scopes[i:i+BATCH_SIZE]
        print_colored(f"[Batch] Processing scopes {i+1} to {i+len(current_batch)} of {total}", 'green')
        with ThreadPoolExecutor(max_workers=len(current_batch)) as scope_executor:
            futures = [scope_executor.submit(process_scope, scope, providers, enum_path) for scope in current_batch]
            wait(futures)

def main():
    global PROVIDER_COLORS
    
    enum_path = os.path.join(config().get('WATCH_DIR'), 'enum')
    
    all_programs = Programs.objects.all()
    unique_providers = set()
    for p in all_programs:
        if p.providers:
            unique_providers.update(p.providers)
    
    COLOR_PALETTE = ['cyan', 'green', 'magenta', 'red', 'blue']
    sorted_providers = sorted(list(unique_providers))
    
    for i, provider in enumerate(sorted_providers):
        PROVIDER_COLORS[provider] = COLOR_PALETTE[i % len(COLOR_PALETTE)]
    
    PROVIDER_COLORS['inventory'] = 'white'
    
    print_colored("[System] Provider color map initialized:", 'blue')
    for provider, color in PROVIDER_COLORS.items():
        print_colored(f"[System] - {provider}: {color}", color)

    for program in all_programs:
        run_command(f"python3 {os.path.join(enum_path, 'watch_inventory.py')} {program.program_name}")
        
        scopes = program.scopes or []
        providers = program.providers or []

        if not scopes or not providers:
            continue

        batch_process_scopes(scopes, providers, enum_path)

if __name__ == "__main__":
    main()