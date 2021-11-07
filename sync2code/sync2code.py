import sys 
import os
sys.path.append(os.environ.get("ACTION_REPO_ROOT", ".."))

from orgman import dump_existing_teams, commit_and_pr, switch_and_pull

if os.path.exists("../.env"):
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path="../.env")
    except Exception as e:
        print("Unable to load the found '.env' file. Please install 'python-dotenv' package.")

if __name__ == "__main__":
    switch_and_pull()
    org_members = get_org_members()
    team_names = get_existing_teams()
    teams = get_teams_data(team_names)
    dump_existing_teams(teams)
    dump_codeowners(teams)
    dump_no_team_members(org_members, teams)
    commit_and_pr()