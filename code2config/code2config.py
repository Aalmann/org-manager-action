import sys 
import os
sys.path.append(os.environ.get("ACTION_REPO_ROOT", ".."))

from orgman import apply_teams

if os.path.exists("../.env"):
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path="../.env")
    except Exception as e:
        print("Unable to load the found '.env' file. Please install 'python-dotenv' package.")

if __name__ == "__main__":
    apply_teams()