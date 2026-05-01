import os
import subprocess
import sys
import time

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    print("\033[94m" + "="*50)
    print("      JEWEL ELITE MASTER BOT - LAUNCHER")
    print("="*50 + "\033[0m")

def show_menu():
    print("\033[96mPlease select your strategy mode:\033[0m")
    print("\n[1] \033[93mJEWEL_ELITE\033[0m (SMC Patterns Only - Fast & Aggressive)")
    print("[2] \033[93mGOD_MODE\033[0m    (14-Factor Indicators - Confirmed & Stable)")
    print("[3] \033[92mHYBRID\033[0m      (Integrated Sync - Safest & Most Professional)")
    print("\n[Q] Quit Launcher")
    print("\033[94m" + "="*50 + "\033[0m")

def main():
    while True:
        clear_screen()
        print_banner()
        show_menu()
        
        choice = input("\nEnter your choice (1-3): ").strip().upper()
        
        mode = ""
        if choice == '1':
            mode = "JEWEL_ELITE"
        elif choice == '2':
            mode = "GOD_MODE"
        elif choice == '3':
            mode = "HYBRID"
        elif choice == 'Q':
            print("Exiting Launcher...")
            break
        else:
            print("\033[91mInvalid choice! Please try again.\033[0m")
            time.sleep(1.5)
            continue
            
        print(f"\n\033[92m[OK] Launching Master Bot in {mode} mode...\033[0m")
        print("\033[90m(Close this window to stop the bot)\033[0m\n")
        
        # Launch the bot as a separate process
        try:
            cmd = [sys.executable, "f:/TradeBot/JewelElite_MasterBot_MT5.py", mode]
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n\033[93mBot stopped by user. Returning to menu...\033[0m")
            time.sleep(2)
        except Exception as e:
            print(f"\033[91mError launching bot: {e}\033[0m")
            time.sleep(3)

if __name__ == "__main__":
    main()
