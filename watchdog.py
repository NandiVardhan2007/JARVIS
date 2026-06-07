import subprocess
import time
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - WATCHDOG - %(message)s")

def main():
    consecutive_crashes = 0
    
    while True:
        logging.info("Starting JARVIS Launcher...")
        
        # Launch JARVIS
        proc = subprocess.Popen([sys.executable, "jarvis_launcher.py"])
        
        # Wait for it to finish
        exit_code = proc.wait()
        
        if exit_code == 0:
            logging.info("JARVIS shut down cleanly. Watchdog exiting.")
            break
        else:
            consecutive_crashes += 1
            logging.error(f"JARVIS crashed with exit code {exit_code} (Crash #{consecutive_crashes})")
            
            if consecutive_crashes >= 5:
                logging.error("Too many consecutive crashes. Watchdog giving up.")
                break
                
            logging.info("Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
