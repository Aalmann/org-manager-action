#!/usr/bin/python3
# encoding: utf-8
'''
orgman -- A GitHub organisation manager script.

@author:     Alexander Hanl
@copyright:  Copyright (c) Alexander Hanl 2021. All rights reserved.
@license:    MIT
'''
import requests
import os
import yaml
import glob

if os.path.exists(".env"):
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception as e:
        print("Unable to load the found '.env' file. Please install 'python-dotenv' package.", flush=True)

def _get_env_or_raise(key):
    val = os.environ.get(key)
    if None == val:
        raise Exception(f"The variable {key} is not set in environment but required")
    else:
        return val

def _get_env_vars():
    vars = {}
    vars['api_url']         = _get_env_or_raise("GITHUB_API_URL")
    vars['token']           = _get_env_or_raise("GITHUB_TOKEN")
    vars['org']             = _get_env_or_raise("GITHUB_ORG")
    vars['repo']            = _get_env_or_raise("GITHUB_REPO")
    vars['repo_dir']        = _get_env_or_raise("GITHUB_REPO_DIR")
    vars['teams_dir']       = os.environ.get("TEAMS_DIR") or vars.get('repo_dir') + '/teams'
    vars['codeowners_dir']  = os.environ.get("CODEOWNERS_DIR") or vars.get('repo_dir') + '/.github'
    vars['branch']          = os.environ.get('GITHUB_BRANCH', "sync2code")
    vars['https_proxy']     = os.environ.get('HTTPS_PROXY')
    vars['http_proxy']      = os.environ.get('HTTP_PROXY')
    vars['verify']          = os.environ.get('VERIFY', "True").lower() in ('true', '1', 't')

    return vars

def _gh_api_call(type, endpoint, params=None, data=None, json=None):
    vars = _get_env_vars()
    api_url = vars.get('api_url')
    token = vars.get('token')
    verify = vars.get('verify')
    proxies = None
    if vars.get('http_proxy') and vars.get('https_proxy'):
        proxies =   {
                        'http_proxy': vars.get('http_proxy'),
                        'https_proxy': vars.get('https_proxy'),
                    }

    headers = {}
    headers['Accept'] = 'application/vnd.github.v3+json'
    headers['Authorization'] = 'token ' +  token

    url = endpoint if (api_url in endpoint) else api_url + endpoint

    if hasattr(requests,type) and callable(getattr(requests, type)):
        m = getattr(requests, type)
        print("API call: " + type + " " + url, flush=True)
        print(data if data else params if params else json, flush=True)
        result = m(url, data=data, params=params, json=json, headers=headers, verify=verify, proxies=proxies)
        if result.status_code in [200, 201]:
            ret = result.json()
            page = 2
            while 'next' in result.links.keys():
                total = result.links['last']['url'].split('?')[-1].split('&')[-1].replace('page=', '')
                print(f"Paginated result, trying to get next {page}/{total}", flush=True)
                result = m(result.links['next']['url'], headers=headers, verify=verify, proxies=proxies)
                page = page + 1
                ret.extend(result.json())
            return ret
        elif result.status_code == 204:
            print("Status code 204, no content", flush=True)
            return
        elif result.status_code == 404:
            print("Status code 404", flush=True)
            return 404
        else:
            print("Error occured:", flush=True)
            print(result, flush=True)
    else:
        raise Exception("Unknown method")

def get_org_members():
    vars = _get_env_vars()
    org  = vars.get("org")
    org_members = []
    org_maintainers = []
    
    members = _gh_api_call('get', f"/orgs/{org}/members", params={'per_page': 100})
    org_members.extend(i.get('login') for i in members)
      
    
    return org_members

def get_existing_teams():
    vars = _get_env_vars()
    org  = vars.get("org")
    all_teams = []
    
    teams = _gh_api_call('get', f"/orgs/{org}/teams", params={'per_page': 100})
    all_teams.extend(teams)
    
    return all_teams

def get_members_of_team(slug):
    vars = _get_env_vars()
    org  = vars.get("org")
    members = _gh_api_call('get', f"/orgs/{org}/teams/{slug}/members", params={'role': 'member', 'per_page': 100})
    maintainers = _gh_api_call('get', f"/orgs/{org}/teams/{slug}/members", params={'role': 'maintainer', 'per_page': 100})

    mem_list = []
    maint_list = []
    for m in maintainers:
        maint_list.append(m.get('login'))
    for m in members:
        mem = m.get('login')
        if not mem in maint_list:
            mem_list.append(mem)

    return { '2_members' : mem_list, '3_maintainers' : maint_list }

def get_repos_for_team(slug):
    vars = _get_env_vars()
    org  = vars.get("org")
    repos = _gh_api_call('get', f"/orgs/{org}/teams/{slug}/repos")

    rep_list = []
    for r in repos:
        rep = {}
        rep['full_name'] = r.get('full_name')
        rep['name'] = r.get('name')
        p = r.get('permissions')
        rep['permission'] = "admin" if p['admin'] else "maintain" if p['maintain'] else "push" if p['push'] else 'triage' if p['triage'] else 'pull'
        
        rep_list.append(rep)
    return rep_list

def get_teams_data(team_names):

    if None == team_names:
        team_names = get_existing_teams()
    
    teams_data = {}

    for team in team_names:
        t = {}
        t['0_name'] = team.get('name')
        t['1_description'] = team.get('description')
        t.update(get_members_of_team(team.get('slug')))
        t['4_repositories'] = get_repos_for_team(team.get('slug'))
        t['5_slug'] = team.get('slug')
        t['6_privacy'] = team.get('privacy')
        teams_data[team.get('slug')] = t
    
    return teams_data

def dump_existing_teams(teams):
    vars = _get_env_vars()
    teams_dir = vars.get("teams_dir")

    if not os.path.exists(teams_dir):
        os.mkdir(teams_dir)
    
    for k, team in teams.items():
        f_name = teams_dir + os.path.sep + team.get('5_slug') + '.yaml'
        
        with open(f_name, 'w+') as ymlfile:
            yaml.dump(team, ymlfile, default_flow_style=False)
            print(f"File {f_name} written", flush=True)

def dump_no_team_members(org_members, teams):
    vars = _get_env_vars()
    teams_dir = vars.get("teams_dir")

    if not os.path.exists(teams_dir):
        os.mkdir(teams_dir)
        
    no_teams_members = list(org_members)
    for _, team in teams.items():
        for member in team.get('2_members'):
            if member in no_teams_members:
                no_teams_members.remove(member) 
        for maintainer in team.get('3_maintainers'):
            if maintainer in no_teams_members:
                no_teams_members.remove(maintainer) 
    
    f_name = teams_dir + os.path.sep + '_no_teams_member.yaml'
    
    with open(f_name, 'w+') as ymlfile:
        yaml.dump(no_teams_members, ymlfile, default_flow_style=False)
        print(f"File {f_name} written", flush=True)

def dump_codeowners(teams):
    vars = _get_env_vars()
    teams_dir = vars.get('teams_dir').replace(vars.get('repo_dir'), '')
    codeowners = vars.get('codeowners_dir') + os.path.sep + 'CODEOWNERS'
    
    if not os.path.exists(vars.get('codeowners_dir')):
        os.mkdir(vars.get('codeowners_dir'))
    
    with open(codeowners, 'w+') as f:
        f.write("##############################################################\n")
        f.write("# CODEOWNERS file use for automated pull_request assignments #\n")
        f.write("##############################################################\n\n")
        for name, team in teams.items():
            f.write(f"# These CODEOWNERS are the maintainer of team '{name}' and must review each pull_request for team changes\n")
            f.write(teams_dir + '/' + name + ".yaml @" + " @".join(team.get('3_maintainers')) + "\n\n")
        print(f"File {codeowners} written", flush=True)


def apply_teams():
    vars = _get_env_vars()
    org  = vars.get("org")
    teams_dir = vars.get("teams_dir")

    for f in glob.glob(teams_dir + os.path.sep + "*.yaml"):
        if '_no_teams_member.yaml' in f:
            # skip no teams member file
            continue
        with open(f, "r") as ymlfile:
            team = yaml.safe_load(ymlfile)
        t = {}
        t['name'] = team.get('0_name')
        t['description'] = team.get('1_description')
        t['privacy'] = team.get('6_privacy')
        slug = team.get('5_slug')
        
        # try to path the team
        if 404 == _gh_api_call("patch", f"/orgs/{org}/teams/{slug}", data=t):
            # seems to be a new team is needed
            new_team = _gh_api_call("post", f"/orgs/{org}/teams", data=t)
            team['6_slug'] = new_team.get('slug')
        
        
        for repo in team.get('4_repositories'):
            full_name = repo.get('full_name')
            _gh_api_call("put", f"/orgs/{org}/teams/{slug}/repos/{full_name}",data={'permission': repo.get('permission')})
        
        for member in team.get('2_members'):
            _gh_api_call('put', f"/orgs/{org}/teams/{slug}/memberships/{member}", data={"role": 'member'})

        for maintainer in team.get('3_maintainers'):
            _gh_api_call('put', f"/orgs/{org}/teams/{slug}/memberships/{maintainer}", data={"role": 'maintainer'})
                    
def commit_and_pr():
    vars = _get_env_vars()
    repo = vars.get("repo")
    branch = vars.get("branch")

    print("Calling git to commit changes", flush=True)
    os.system("git config user.name github-actions")
    os.system("git config user.email github-actions@github.com")
    os.system("git add .")
    if 0 == os.system("git commit -m 'This commit was generated by GitHub Actions after calling sync2code'"):
        if 0 == os.system(f"git push origin {branch}"):
            print("Changes pushed to remote", flush=True)
            pr_found = _gh_api_call('get', f"/repos/{repo}/pulls", params=\
                    {
                        "state": "open",
                        "head": branch
                    })
            if len(pr_found):
                id = pr_found[0].get('number')
                data = {
                        "title": "autogenerated PR created by sync2commit",
                        "head": branch,
                        "base": "main",
                        "body": pr_found[0].get('body') + "\n\n * PR updated in the meantime by workflow run."
                        }
                pr = _gh_api_call('patch', f"/repos/{repo}/pulls/{id}", data=data) 
                pr=pr_found[0].get('url')
                print(f"::set-output name=pr-created::{pr}", flush=True)
            else:
                data = {
                        "title": "autogenerated PR created by sync2commit",
                        "head": branch,
                        "base": "main",
                        "body": "This PR was autogenerated by sync2commit and should contain all UI based changes made by the users."
                    }
                pr = _gh_api_call('post', f"/repos/{repo}/pulls", data=data)
                pr = pr.get('url')
                print(f"::set-output name=pr-created::{pr}", flush=True)


def switch_and_pull():
    vars = _get_env_vars()
    branch = vars.get("branch")
    
    os.system(f"git checkout -B {branch}")
    os.system(f"git pull origin {branch}")

if __name__ == "__main__":
    '''
    main
    '''
    print("####################################", flush=True)
    print("    GitHub organization manager     ", flush=True)
    print("####################################", flush=True)
    print(flush=True)

    org_members = get_org_members()
    team_names = get_existing_teams()
    teams = get_teams_data(team_names)
    dump_existing_teams(teams)
    dump_codeowners(teams)
    dump_no_team_members(org_members, teams)
    #apply_teams()
