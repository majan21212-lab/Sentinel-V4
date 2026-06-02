import os
import json
import subprocess
import sys
import time
import argparse

REGISTRY_PATH = "f:/TradeBot/bot_registry.json"
BOT_SCRIPT = "f:/TradeBot/JewelElite_MasterBot_MT5.py"

def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)

def run_bot(bot_id, config):
    print(f"[*] Launching Bot {bot_id} ({config['symbol']} | {config['strategy']})...")
    
    cmd = [
        sys.executable,
        BOT_SCRIPT,
        "--id", bot_id,
        "--symbol", config['symbol'],
        "--strategy", config['strategy']
    ]
    
    # Run as a background process
    # On Windows, we can use creationflags to start in a new console or hidden
    if os.name == 'nt':
        return subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        return subprocess.Popen(cmd)

def main():
    parser = argparse.ArgumentParser(description="Sentinel Multi-Bot Manager")
    parser.add_argument("action", choices=["run", "stop", "list"], help="Action to perform")
    parser.add_argument("bot_id", nargs="?", help="Bot ID (e.g. A, B, C) or 'all'")
    
    args = parser.parse_args()
    registry = load_registry()
    
    if args.action == "list":
        print("\n--- SENTINEL BOT REGISTRY ---")
        for bid, cfg in registry.items():
            status = "ENABLED" if cfg.get('enabled') else "DISABLED"
            print(f"[{bid}] {cfg['symbol']} - {cfg['strategy']} ({status})")
        print("-----------------------------\n")
        return

    if args.action == "run":
        if not args.bot_id:
            print("Error: Specify a Bot ID or 'all'")
            return
            
        if args.bot_id.lower() == "all":
            for bid, cfg in registry.items():
                if cfg.get('enabled'):
                    run_bot(bid, cfg)
                    time.sleep(2) # Stagger start
        else:
            bid = args.bot_id.upper()
            if bid in registry:
                run_bot(bid, registry[bid])
            else:
                print(f"Error: Bot {bid} not found in registry.")

if __name__ == "__main__":
    main()
