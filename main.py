import argparse
import yaml
from datetime import datetime
import re
import subprocess
import os
import git
import tomllib
from InquirerPy import inquirer
from progress.bar import Bar
from dotenv import dotenv_values
from typing import List, Tuple, Dict
import csv
import pathlib
import certifi
import sys
import shutil
import tempfile
import glob
from data_types import VcsBackend, ConnectionInput, Repo
from _backend_gitlab import GitlabBackend
from _backend_bitbucket import BitbucketBackend
from _backend_bitbucket_cloud import BitbucketCloudBackend
from _backend_github import GithubBackend
import inspect

config: Dict = {
    "data_version": 1,
    "backends": Dict[str, VcsBackend],
    "backends_chosen": [],  # bitbucket / gitlab
    "updateinfo": False,
    "executive_report": False,
    "gitlab_url": None,
    "gitlab_token": None,
    "bitbucket_url": None,
    "bitbucket_token": None,
    "groupfilter": None,
    "repofilter": None,
    "grouprepofilter": None,
    "rulesfilter": None,
    "interactive": False,
    "scan_gitleaks": True,
    "force_scan": False,
    "no_clone": False,
    "verbose": False,
    "output_folder": "output",
    "gitleaks_image": "zricethezav/gitleaks:latest",
    "localgitleaks": False,
    "no_redacting": False,
    "no_contact_last_branch": False,
    "scan_last_branch": False,
    "update_repos": True,
    "reports_format": "csv",
    "gitleaksTomlFile": False,
    "gitleaksTomlFileCustomDefault": "gitleaks-custom.toml",
    "gitleaksTomlFileOriginalDefault": "gitleaks.toml",
}
cache = {}

def getRepoFileName(backend: VcsBackend):
    return f'{config["output_folder"]}/repos_{backend.name()}.yaml'


def main():
    try:
        getinfo()
        checkSetup()

        if config["executive_report"]:
            print(generateExecutiveReport())
            sys.exit(0)

        repos: Dict[int, Repo] = getData()
        if len(repos) == 0:
            raise Exception("No repo data fetched, something wrong")

        cache['repos']: Dict[int, Repo] = repos # Used later to update single repo's and persist.

        # Interactive clone/scan.
        if config["interactive"]:
            repo, branch = interactive_pick_enriched_repo(repos)
            if not repo or not branch:
                print("No repo selected, exiting")
                sys.exit(0)
            cloneRepo(repo, branch)
            repo = gitleaksScanRepo(repo, verbose=True, branch=branch)
            persistRepoData(repo)
            sys.exit(0)

        # Batched clone/scan.
        if config["scan_gitleaks"] and not config["force_scan"]: print("\nNOTE: ONLY SCANNING UNSCANNED REPOS! Use --force_scan to scan everything.\n")
        repos_filtered = repos_in_filterset(repos)
        bar = Bar('Cloning/scanning', max=len(repos_filtered)
                  ) if not config["verbose"] else None

        # Ask user to proceed processing.
        if not config["interactive"]:
            user_input = input(
                f"Do you want to continue processing {len(repos_filtered)} repositories?\nNote you can stop/resume this any time: (Y/n): ")
            if user_input.lower() in ["yes", "y", ""]:
                print("Continuing...")
            else:
                print("Exiting...")
                sys.exit(0)

        batches = repos_to_batches(repos_filtered, config["batch_size"])
        dirty_repos: Dict[int, Repo] = {}
        batch_counter = 1
        for batch in batches:
            if len(batches) > 1 and config["verbose"]: print(f"Processing batch {batch_counter}/{len(batches)}")
            process_batch(batch, dirty_repos, bar=bar, verbose=config["verbose"])
            batch_counter+=1

        if bar: bar.finish()
        print(f"Found secrets in {len(dirty_repos)} repositories.")
        print(
            f'Reports stored in [{config["output_folder"]}/reports].')
        if len(dirty_repos):
            sys.exit(3)
        sys.exit(0)
    except Exception as e:
        print(e)
        sys.exit(1)

def process_batch(batch: Dict[int, Repo], dirty_repos: Dict[int, Repo], verbose: bool = False, bar: Bar = None):
    for repo in batch.values():
        repo = enrichRepoData(repo)
        try:
            # Clone/update clone
            if not config["no_clone"]: cloneRepo(repo, verbose=verbose)

            # Scan with gitleaks
            if config["scan_gitleaks"] or config["force_scan"]:
                # Only scan if repo has branches (not empty):
                if not repo.get("default_branch", None) and verbose: print(f"Repo [{repo['group']}/{repo['name']}] does not have a default branch, skipping")

                target_branch = repo["latest_branch"] if config["scan_last_branch"] else repo["default_branch"]

                if config["force_scan"] or "scanned" not in repo or repo["scanned"] != target_branch:
                    repo = gitleaksScanRepo(
                        repo, verbose=verbose, dirty_repos=dirty_repos, branch=target_branch)
                else:
                    if verbose: print(f"Skipping [{repo["group"]}/{repo["name"]}], already scanned branch [{target_branch}]")

            persistRepoData(repo)
        except Exception as e:
            print(f"Problem: {e}")
            if bar: bar.next()
            continue
        if bar: bar.next()

def repos_to_batches(repos: Dict[int, Repo], size: int):
    if size == 0: return [repos]
    batches = []
    batch: Dict[int, Repo] = {}
    for repo_id, repo_object in repos.items():
        batch[repo_id] = repo_object
        if len(batch) == size:
            batches.append(batch)
            batch = {}

    if len(batch):
        batches.append(batch)
    return batches

def discover_backends() -> Dict[str, VcsBackend]:
    backends: Dict[str, VcsBackend] = {}
    for _, obj in globals().items():
        if inspect.isclass(obj) and issubclass(
                obj, VcsBackend) and obj is not VcsBackend:
            instance = obj()  # Instantiate
            backends[instance.name()] = instance

    if not len(backends):
        raise Exception("No VCS backends found, something wrong")
    return backends


def getData():
    repos: Dict[int, Repo] = {}

    for backend_type in config["backends_chosen"]:
        backend: VcsBackend = config["backends"][backend_type]
        repo_file = getRepoFileName(backend)
        data: Dict[str, Repo] = {}
        # Read cached data or fetch from API
        try:
            if not os.path.exists(config["output_folder"]):
                os.mkdir(config["output_folder"])
            data = readFile(repo_file)
        except Exception:
            print(
                f"Cannot load [{backend.name()}] data from disk, assuming no cache and will fetch fresh data from API.")

        if data is not None and len(data) > 0:
            print(f"Found data in [{repo_file}], I'll use that. If you want to start over, remove {config["output_folder"]}/ and restart, or use the --updateinfo flag to update.")

        if data is None or len(data) == 0 or config["updateinfo"]:
            if config["updateinfo"]:
                print("Updating existing data")
            new_data = backend.fetchAllRepos(True, config["verbose"])
            if config["updateinfo"]:
                data = updateRepoInfo(data, new_data)
            else:
                data = new_data

            writeFile(data, repo_file)
        repos.update(data)
    return repos


def updateRepoInfo(current: Dict[int, Repo]
                   = None, new: Dict[int, Repo] = None):
    if new is None:
        raise Exception("New data of type None")
    if current is None or len(current) == 0:
        return new

    for repo_id in new.keys():
        if repo_id not in current:
            current[repo_id] = new[repo_id]
        else:  # merge
            for field in new[repo_id].keys():
                if field not in ["folder", "scanned",
                                 "secrets_found", "report_path"]:
                    current[repo_id][field] = new[repo_id][field]
    return current


def getinfo():
    global config

    # Discover available backends
    config["backends"] = discover_backends()
    print("Available VCS Backends:", list(config["backends"].keys()))

    # Create an argument parser object
    parser = argparse.ArgumentParser(
        description="""A CLI tool to scan repositories with Gitleaks in bulk, supporting Bitbucket DC and Gitlab.
        Note if no data is present, it will be fetched once. After that existing data will be used and not updated, unless removed from disk."""
    )

    # Add arguments
    # Note capital flags are reserved for backends (--gitlab/-G).
    parser.add_argument(
        "--updateinfo",
        action='store_true',
        required=False,
        help="Update repo/branch information from all backends"
    )
    parser.add_argument(
        "--executive_report",
        action='store_true',
        required=False,
        help="Do not clone/scan but generate an executive report (optional)"
    )
    parser.add_argument(
        "-r", "--repofilter",
        type=str,
        required=False,
        help="Repository name filter (python regex). Used after groupfilter if enabled. (optional)"
    )
    parser.add_argument(
        "-g", "--groupfilter",
        type=str,
        required=False,
        help="Group name filter (python regex). Used prior to repofilter. (optional)"
    )
    parser.add_argument(
        "-f", "--group_repo_filter",
        type=str,
        required=False,
        help="Group/repo name filter (python regex). Cannot be used in conjunction with --repofilter or --groupfilter (optional)"
    )
    parser.add_argument(
        "--rulesfilter",
        type=str,
        required=False,
        help="Gitleaks rules filter (python regex, rule ID in toml config) (optional)"
    )
    parser.add_argument(
        "--noscan",
        action='store_true',
        required=False,
        help="Do not scan projects with gitleaks (optional)"
    )
    parser.add_argument(
        "--defaultbranch",
        action='store_true',
        required=False,
        help="Scan default branch instead of most recently committed branch. (optional)"
    )
    parser.add_argument(
        "-S", "--force_scan",
        action='store_true',
        required=False,
        help="Scan projects with gitleaks, even if already scanned (optional)"
    )
    parser.add_argument(
        "--no_clone",
        action='store_true',
        required=False,
        help="Do not clone git repos (optional)"
    )
    parser.add_argument(
        "--no_clone_update",
        action='store_true',
        required=False,
        help="Do not update every git repo to it's latest state (optional)"
    )
    parser.add_argument(
        "--keep_clones",
        action='store_true',
        required=False,
        help="Do not remove cloned repo's after scanning. Useful for triaging. Clones are never removed in interactive mode. (optional)"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=20,
        required=False,
        help="Batch size for cloning/scanning. Put 0 to disable batching. Default: 20 (optional)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action='store_true',
        required=False,
        help="Verbose output, no progress bars (optional)"
    )
    parser.add_argument(
        "-i", "--interactive",
        action='store_true',
        required=False,
        help="Interactively pick a project to clone/scan (optional)"
    )
    parser.add_argument(
        "--no_redacting",
        action='store_true',
        required=False,
        help="Turn off gitleaks secret redacting in reports (optional)"
    )
    parser.add_argument(
        "--gitleaks_image",
        type=str,
        required=False,
        help="Gitleaks docker image to use. Default: [zricethezav/gitleaks:latest] (optional)"
    )
    parser.add_argument(
        "--localgitleaks",
        action='store_true',
        required=False,
        help="Use local gitleaks command instead of through docker (optional)"
    )
    parser.add_argument(
        "--reports_format",
        type=str,
        required=False,
        help="Gitleaks report format (output format (json, csv, junit, sarif) (default \"csv\")) (optional)"
    )
    parser.add_argument(
        "--gitleaks_conf",
        type=str,
        required=False,
        help="Gitleaks config file (.toml) to use. Default: [gitleaks-custom.toml] (optional)"
    )

    for backend in config["backends"].values():
        parser.add_argument(
            f"-{backend.shortname().upper()}", f"--{backend.name()}",
            action='store_true',
            required=False,
            help="Use backend backend (optional)"
        )

    # Parse the arguments
    args = parser.parse_args()

    config["updateinfo"] = args.updateinfo
    config["executive_report"] = args.executive_report
    config["repofilter"] = args.repofilter
    config["groupfilter"] = args.groupfilter
    config["grouprepofilter"] = args.group_repo_filter
    config["scan_gitleaks"] = True if not args.noscan else False
    config["no_clone"] = args.no_clone
    config["remove_clones"] = not args.keep_clones
    config["batch_size"] = args.batch_size if args.batch_size > 0 else 0
    config["rulesfilter"] = args.rulesfilter
    config["force_scan"] = args.force_scan
    config["verbose"] = args.verbose
    config["interactive"] = args.interactive
    config["update_repos"] = not args.no_clone_update
    config["scan_last_branch"] = not args.defaultbranch
    config["gitleaks_image"] = config["gitleaks_image"] if args.gitleaks_image is None else args.gitleaks_image
    config["localgitleaks"] = args.localgitleaks
    config["no_redacting"] = args.no_redacting
    config["reports_format"] = config["reports_format"] if args.reports_format is None else args.reports_format
    config["gitleaksTomlFile"] = args.gitleaks_conf if args.gitleaks_conf is not None else False

    for backend in config["backends"].keys():
        if getattr(args, backend, False):
            config["backends_chosen"].append(backend)
    backendSetupData()

    # Validate
    if not config["executive_report"]:
        if len(config["backends_chosen"]) == 0:
            print("Pick at least one backend to use. Use -h for help info.")
            sys.exit(1)
        if config["grouprepofilter"] and (
                config["repofilter"] or config["groupfilter"]):
            print(
                "Cannot use --group_repo_filter at the same time as --repofilter/--groupfilter.")
            sys.exit(1)
        if config["interactive"] and not config["force_scan"]:
            print("Interactive mode, assuming --force_scan")
            config["force_scan"] = True

    resolveGitleaksConfigs()


def backendSetupData():
    global cache
    config_env = dotenv_values(".some_info")
    for backend in config["backends_chosen"]:
        backend_url_key = f"{backend.upper()}_URL"
        backend_token_key = f"{backend.upper()}_TOKEN"

        url = "bogus" if backend == "bitbucket_cloud" else os.getenv(backend_url_key).rstrip("/") if os.getenv(
            backend_url_key) else config_env[backend_url_key].rstrip("/") if backend_url_key in config_env else None
        token = os.getenv(backend_token_key) if os.getenv(
            backend_token_key) else config_env[backend_token_key] if backend_token_key in config_env else None
        if url is None or token is None:
            print(
                f"Provide {backend_url_key}/{backend_token_key} in .some_info or as environmental variable.")
            sys.exit(1)

        config["backends"][backend].setup(
            ConnectionInput(base_url=url, token=token))


def persistRepoData(repo: Repo):
    if not 'repos' in cache: raise Exception("No repos in cache, something wrong")
    repos = cache['repos']
    cache['repos'][repo["id"]] = repo
    persistState(repos, repo["type"])


def persistState(repos: Dict[int, Repo], backend_type: str):
    data = {k: v for k, v in repos.items() if v["type"] == backend_type}
    writeFile(data, getRepoFileName(config["backends"][backend_type]))

def remove_repo_clones(repos: Dict[int, Repo]):
    for repo in repos.values():
        if "folder" in repo and os.path.exists(repo["folder"]):
            if os.path.realpath(repo["folder"]).startswith(os.path.realpath(os.getcwd()) + "/output/repos/"):
                if config["verbose"]: print(f"Removing clone [{repo["folder"]}]")
                shutil.rmtree(repo["folder"])

def writeFile(object, path):
    data = {
        "data_version": config["data_version"],
        "data": object
    }

    with open(path, "w") as outfile:
        yaml.dump(data, outfile)
        if config["verbose"]:
            print(f"Wrote data to {path}.")


def readFile(path) -> Dict[int, Repo]:
    if config["verbose"]:
        print(f"Reading yaml file [{path}]")
    with open(path, "r") as outfile:
        data = yaml.safe_load(outfile)
        if "data_version" in data and data["data_version"] == config["data_version"]:
            return data["data"]
        else:
            print(f"Data format in [{path}] outdated, cannot use")
            return None


def enrichRepoData(repo: Repo):
    repos_folder = config["output_folder"] + "/repos"
    repo["folder"] = f"{repos_folder}/{repo["type"]}/{repo["group"]}/{repo["name"]}"

    if config["verbose"]:
        print(f"Fetching latest branch/contact details for project [{repo["group"]}/{repo["name"]}]")
    backend: VcsBackend = config["backends"][repo["type"]]

    try:
        return backend.enrichRepo(repo)
    except Exception as e:
        print(f"Unable to enrich data for [{repo["group"]}/{repo["name"]}]: [${e.args[0]}]")
        return repo

def repos_in_filterset(repos: Dict[int, Repo]) -> Dict[int, Repo]:
    result: Dict[int, Repo] = {
        repo_id: repo_object
        for repo_id, repo_object in repos.items()
        if checkRepoInFilterSet(repo_object)
    }
    return result

def checkRepoInFilterSet(repo: Repo):
    if config["grouprepofilter"] is None and config["repofilter"] is None and config["groupfilter"] is None:
        return True

    if config["grouprepofilter"]:
        if re.search(config["grouprepofilter"], repo["group"], re.IGNORECASE) or re.search(
                config["grouprepofilter"], repo["name"], re.IGNORECASE):
            return True

    elif config["groupfilter"] is None or re.search(config["groupfilter"], repo["group"], re.IGNORECASE):
        if config["repofilter"] is None or re.search(
                config["repofilter"], repo["name"], re.IGNORECASE):
            return True

    return False


def create_askpass_script(username, token):
    fd, path = tempfile.mkstemp(suffix='.sh')
    os.chmod(path, 0o700)
    with os.fdopen(fd, 'w') as f:
        f.write(f"""#!/bin/sh
if echo "$1" | grep -q "Username for"; then
  echo "{username}"
else
  echo "{token}"
fi
""")
    return path

def cloneRepo(enriched_repo: Repo, branch: str = None, verbose: bool = False):
    backend: VcsBackend = config["backends"][enriched_repo["type"]]
    username, token = backend.get_git_username_password()
    askpass_script = create_askpass_script(username, token)
    git_env = {
        'GIT_TERMINAL_PROMPT': '0',
        'GIT_ASKPASS': askpass_script
    }
    try:
        # Only clone if repo has branches (not empty)
        if not enriched_repo.get("default_branch", None): raise Exception(f"Not cloning repo [{enriched_repo["group"]}/{enriched_repo["name"]}], no default branch")
        target_branch = branch if branch else enriched_repo[
            "latest_branch"] if config["scan_last_branch"] else enriched_repo["default_branch"]

        #  Existing folder ? Switch to target branch latest state.
        if os.path.exists(enriched_repo["folder"]):
            if not os.path.exists(f"{enriched_repo["folder"]}/.git"):
                raise Exception(
                    f"Found repo-folder while it does not contain git info, aborting.\nRemove it to proceed in next run: [{enriched_repo["folder"]}].")

            # Only update if necessary.
            gitrepo = git.Repo(enriched_repo["folder"])
            if not config["update_repos"] and gitrepo.active_branch and gitrepo.active_branch.name == target_branch:
                return True

            if verbose:
                print(f"Updating git state for [{enriched_repo["group"]}/{enriched_repo["name"]}], branch [{target_branch}]")

            origin = gitrepo.remotes.origin
            origin_url = origin.url
            if origin_url != enriched_repo["http_link"]:
                raise Exception(
                    f"Found repo-folder with unexpected origin url, aborting.\nRemove it to proceed in next run: [{enriched_repo["folder"]}].")

            try:
                with gitrepo.git.custom_environment(**git_env):
                    # Use gitrepo.git.execute instead of origin.fetch
                    gitrepo.git.execute(['git', 'fetch', 'origin',
                                         f'+refs/heads/{target_branch}:refs/remotes/origin/{target_branch}',
                                         '--depth=1'])
            except Exception as e:
                print(f"\nWARNING: unable to fetch branch [{target_branch}] in [{enriched_repo['folder']}], not changing state")
                raise e

            try:
                with gitrepo.git.custom_environment(**git_env):
                    if target_branch in gitrepo.heads:
                        gitrepo.git.checkout(target_branch)
                    else:
                        # 🔹 Create the local branch tracking origin/TARGET_BRANCH
                        gitrepo.git.checkout(
                            "-B", target_branch, f"origin/{target_branch}")
                    gitrepo.git.reset(
                        "--hard", f"origin/{target_branch}")
            except Exception as e:
                print(f"\nWARNING: unable to reset state for [{target_branch}] in [{enriched_repo['folder']}].")
                raise e

        else:
            if verbose:
                print(f"Cloning repo [{enriched_repo["group"]}/{enriched_repo["name"]}], branch [{target_branch}]")

            try:
                # Create the directory if it doesn't exist
                os.makedirs(enriched_repo["folder"], exist_ok=True)

                # Initialize a new Git repository
                gitrepo = git.Repo.init(enriched_repo["folder"])
                with gitrepo.git.custom_environment(**git_env):

                    gitrepo.git.execute([
                        'git', 'remote', 'add', 'origin', enriched_repo["http_link"]
                    ])

                    gitrepo.git.execute([
                        'git', 'fetch', 'origin',
                        f'{target_branch}:refs/remotes/origin/{target_branch}',
                        '--depth=1',
                        '--filter=blob:limit=100k',
                        '--no-tags'
                    ])

                    gitrepo.git.execute([
                        'git', 'checkout', '-b', target_branch,
                        f'origin/{target_branch}'
                    ])
            except Exception as e:
                print(
                    f"Unable to clone repo [{enriched_repo["group"]}/{enriched_repo["name"]}], branch [{target_branch}]: \n{e.stderr}")

                raise e
                # if e.status in [128]:
                #     raise e  # Break on auth issues.
                # return False
    finally:
        # Clean up the temporary script
        if os.path.exists(askpass_script):
            os.unlink(askpass_script)

def interactive_pick_enriched_repo(repos: Dict[int, Repo]) -> Tuple[Repo, str]:
    answer_repo = inquirer.fuzzy(
        message="Please select a repository:",
        choices=[(f"{repo["group"]}/{repo['name']}", repo["id"]) for repo in repos.values()],
        multiselect=False,
        max_height="80%",
    ).execute()

    if not answer_repo:
        return None

    repo = enrichRepoData(repos[answer_repo[1]])

    branch = repo["default_branch"]
    if answer_repo and repos[answer_repo[1]
                             ]["latest_branch"] != repo["default_branch"]:
        answer_branch = inquirer.fuzzy(
            message="Please select a branch:",
            choices=[repo["latest_branch"], repo["default_branch"]],
            multiselect=False,
            max_height="80%",
        ).execute()
        branch = answer_branch if answer_branch else branch

    return repo, branch

def isWindows():
    return os.name == 'nt'


def checkSetup():
    global config
    if config["localgitleaks"]:  # Only linux supported
        out = os.system("which gitleaks > /dev/null 2>&1")
        if out != 0:
            raise Exception("gitleaks command not available")
    else:
        out = os.system("where docker > nul 2>&1") if isWindows(
        ) else os.system("which docker > /dev/null 2>&1")
        if out != 0:
            raise Exception("docker command not available")

    if os.environ.get('REQUESTS_CA_BUNDLE'):
        print("""
              ============================================================================================
              WARNING: Custom CA bundle set (REQUESTS_CA_BUNDLE). Might fail TLS requests to public API's.
              Note I will automatically add .crt files in the working folder to the truststore.
              ============================================================================================
              """)
    else:
        crt_files = glob.glob("*.crt")
        if crt_files:
            print("Found .crt files in folder, appending them to the global truststore")
            # Build truststore
            DEFAULT_TRUSTSTORE = certifi.where()  # System truststore (Certifi's bundle)
            # Final merged file
            MERGED_TRUSTSTORE = f"{tempfile.gettempdir()}/.gitleaks-bulk.crt"

            # Copy the system truststore first
            shutil.copyfile(DEFAULT_TRUSTSTORE, MERGED_TRUSTSTORE)

            # Append custom certificates
            for crtfile in crt_files:
                if os.path.exists(crtfile):
                    with open(MERGED_TRUSTSTORE, "a") as merged, open(crtfile, "r") as custom:
                        merged.write(custom.read())

            # Set environment variable to use it globally
            os.environ["REQUESTS_CA_BUNDLE"] = os.path.abspath(
                MERGED_TRUSTSTORE)

def gitleaksScan(
        repos: Dict[int, Repo], picked_repo: Tuple[Repo, str] = None) -> Dict[int, Repo]:
    localVerbose = True if picked_repo is not None else False
    print(f"Starting to scan projects with gitleaks.{" I can resume any time." if picked_repo is None else ""}")
    repos_folder = config["output_folder"] + "/repos"
    if not os.path.exists(repos_folder):
        raise Exception("No /repos folder")

    reports_folder = f"{config["output_folder"]}/reports"
    if not os.path.exists(reports_folder):
        os.mkdir(reports_folder)

    repos_to_scan = [repo for repo in repos.values() if checkRepoInFilterSet(
        repo)] if picked_repo is None else [picked_repo[0]]
    bar = Bar('Scanning', max=len(repos_to_scan)
              ) if not config["verbose"] and picked_repo is None else None
    repos_dirty: Dict[int, Repo] = {}
    for repo in repos_to_scan:
        # Only scan if repo has branches (not empty):
        if repo["default_branch"]:
            # If batch and folder somehow doesn't exist, continue.
            if not os.path.exists(repo["folder"]) and picked_repo is None:
                print(
                    f"\nWARNING: unable to scan [{repo['group']}/{repo['name']}] in [{repo['folder']}], not available")
                if bar:
                    bar.next()
                continue

            target_branch = picked_repo[1] if picked_repo else repo[
                "latest_branch"] if config["scan_last_branch"] else repo["default_branch"]

            if config["force_scan"] or "scanned" not in repo or repo["scanned"] != target_branch:
                stdout, stderr, returncode, num_findings, report_path = gitleaksScanRepo(
                    repo, localVerbose=localVerbose)
                if returncode != 0 and returncode != 3:
                    if bar:
                        bar.finish()
                    raise Exception(
                        f"Problem running gitleaks in docker (exit code {returncode}):\n---- stderr: ----\n{stderr}\n---- stdout: ----\n{stdout}")

                if returncode == 3:
                    repo["secrets_found"] = num_findings
                    repo["report_path"] = report_path
                    repos_dirty[repo["id"]] = repo
                else:
                    repo["secrets_found"] = 0
                    repo["report_path"] = None
                repo["scanned"] = target_branch

                persistRepoData(repo)

            else:
                if config["verbose"] or picked_repo:
                    print(f"Skipping [{repo["group"]}/{repo["name"]}], already scanned branch [{target_branch}]")
        elif localVerbose:
            print(
                f"Repo [{repo['group']}/{repo['name']}] does not have a default branch, skipping")
        if bar:
            bar.next()
    if bar:
        bar.finish()
    return repos_dirty


def copyDefaultGitleaksConfigsToFile():
    me_folder = os.path.dirname(os.path.realpath(__file__))
    default_file = config["gitleaksTomlFileOriginalDefault"]
    default_file_template = f"{me_folder}/template_{config["gitleaksTomlFileOriginalDefault"]}"
    custom_file = config["gitleaksTomlFileCustomDefault"]
    custom_file_template = f"{me_folder}/template_{config["gitleaksTomlFileCustomDefault"]}"

    if not os.path.exists(default_file):
        shutil.copyfile(default_file_template, default_file)
    if not os.path.exists(custom_file):
        shutil.copyfile(custom_file_template, custom_file)


def resolveGitleaksConfigs():
    global cache
    if "gitleaks_configs" in cache:
        return cache["gitleaks_configs"]
    files = []
    if config["gitleaksTomlFile"]:
        if not os.path.exists(config["gitleaksTomlFile"]):
            raise Exception(f"Gitleaks config file [{config["gitleaksTomlFile"]}] does not exist")
        files.append(config["gitleaksTomlFile"])
    else:
        copyDefaultGitleaksConfigsToFile()
        files.append(config["gitleaksTomlFileOriginalDefault"])
        files.append(config["gitleaksTomlFileCustomDefault"])
    cache["gitleaks_configs"] = files
    return cache["gitleaks_configs"]


def prepareRules():
    global cache
    if config["rulesfilter"]:
        if 'allowed_rule_ids' in cache:
            return cache['allowed_rule_ids']
        else:
            rule_ids = []
            disabled_rules = []
            for file in resolveGitleaksConfigs():
                with open(file, "rb") as f:
                    data = tomllib.load(f)
                    for rule in data['rules']:
                        if re.search(config["rulesfilter"], rule['id']):
                            rule_ids.append(rule['id'])

                    if "extend" in data and "disabledRules" in data['extend']:
                        disabled_rules.extend(data['extend']['disabledRules'])

            # Filter out disabled rules.
            cache['allowed_rule_ids'] = [
                id for id in rule_ids if id not in disabled_rules]
            return cache['allowed_rule_ids']
    return None


def gitleaksScanRepo(repo: Repo, removeEmptyReport=True, branch: str = None, verbose=False, dirty_repos: Dict[int, Repo] = None) -> Repo:
    if not os.path.exists(repo["folder"]): raise Exception(f"Cannot scan, folder [{repo["folder"]}] does not exist")
    report_name = f"{repo["group"]}/{repo["name"]}".replace("/", "__")
    report_path = f"{config["output_folder"]}/reports/{repo['type']}.{report_name}.{config["reports_format"]}"
    if not os.path.exists(repo["folder"]):
        raise Exception(f"Repository not available locally, expected [{repo["folder"]}]")

    gitleaks_config = config["gitleaksTomlFile"] if config["gitleaksTomlFile"] else config["gitleaksTomlFileCustomDefault"]

    # Make sure to use double quotes (") for windows and linux compatibility.
    cwd = pathlib.PureWindowsPath(os.getcwd()).as_posix()
    opts = []
    repo_path = f'{cwd}/{repo["folder"]}'
    gitleaks_path_arg = repo_path
    gitleaks_report_path_arg = f'{cwd}/{report_path}'

    if config["localgitleaks"]:
        opts.extend(["gitleaks"])
    else:
        gitleaks_path_arg = "/repo"
        gitleaks_report_path_arg = f'/app/{report_path}'
        opts.extend([
            'docker run --rm',
            '-w /app',
            f'--mount type=bind,src="{cwd}/{repo["folder"]}",dst="{gitleaks_path_arg}",ro',
            f'-v "{cwd}:/app" "{config["gitleaks_image"]}"',
        ])

    opts.extend([
        f'dir "{gitleaks_path_arg}"',
        '--max-target-megabytes 1',
        f'--config "{gitleaks_config}"',
        '--exit-code 3',
        f'--report-path "{gitleaks_report_path_arg}"',
        f'--report-format "{config["reports_format"]}"'
    ])

    if not config["no_redacting"]:
        opts.append("--redact=60")

    allowed_rule_ids = prepareRules()
    if allowed_rule_ids:
        for rule_id in allowed_rule_ids:
            opts.append('--enable-rule')
            opts.append(f'"{rule_id}"')

    cmd = " ".join(opts)

    if verbose:
        print(f"Scanning project [{repo["group"]}/{repo["name"]}]")
        print(f"Command: [{cmd}]")

    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)

    if removeEmptyReport and result.returncode == 0:
        if verbose:
            print("Removing report, no findings")
        os.remove(report_path)

    num_findings = 0
    if result.returncode == 3:
        match = re.search(r"leaks found: (\d+)", result.stderr)
        if match:
            num_findings = int(match.group(1))

        if verbose:
            print(
                f"Found [{num_findings}] findings in project, report: [{report_path}]")

    if result.returncode != 0 and result.returncode != 3:
        raise Exception(
            f"Problem running gitleaks (exit code {result.returncode}):\n---- stderr: ----\n{result.stderr}\n---- stdout: ----\n{result.stdout}")

    if result.returncode == 3:
        repo["secrets_found"] = num_findings
        repo["report_path"] = report_path
        if dirty_repos is not None:
            dirty_repos[repo["id"]] = repo
    else:
        repo["secrets_found"] = 0
        repo["report_path"] = None
    repo["scanned"] = branch
    return repo

def generateExecutiveReport():
    repos: Dict[int, Repo] = {}
    for backend in config["backends"].values():
        repo_file = getRepoFileName(backend)
        reposl: Dict[int, Repo] = {}
        if os.path.exists(repo_file):
            reposl = readFile(repo_file)
            repos.update(reposl)

    repos_in_filterset = [
        repo for repo in repos.values() if checkRepoInFilterSet(repo)]
    if not repos_in_filterset:
        print("No repositories left for report, might be due to filters set.")
        sys.exit(0)

    # Filter dirty repos
    repos_for_report: List[Repo] = []
    for repo in repos_in_filterset:
        if "secrets_found" in repo and repo["secrets_found"] is not None and repo["secrets_found"] >= 0:
            repos_for_report.append(repo)

    repos_for_report = sorted(
        repos_for_report,
        key=lambda x: x["secrets_found"],
        reverse=True)

    datetime_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{config['output_folder']}/executive_report_{datetime_suffix}.csv"
    with open(csv_filename, mode="w", newline="") as file:
        # Create a CSV DictWriter
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "name",
                "group",
                "type",
                "branch",
                "secrets_found",
                "report",
                "contact",
                "mail"])

        # Write the header (field names)
        writer.writeheader()

        # Write the rows of data
        for repo in repos_for_report:
            writer.writerow({
                "name": repo["name"],
                "group": repo["group"],
                "type": repo["type"],
                "branch": repo["scanned"],
                "secrets_found": repo["secrets_found"],
                "report": repo["report_path"],
                "contact": repo["contact_name"],
                "mail": repo["contact_mail"],
            })
    print(f"Wrote CSV file [{csv_filename}]")


if __name__ == "__main__":
    main()
