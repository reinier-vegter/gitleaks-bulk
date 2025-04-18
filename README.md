# General
[![Build and Release](https://github.com/reinier-vegter/gitleaks-bulk/actions/workflows/build_release.yml/badge.svg)](https://github.com/reinier-vegter/gitleaks-bulk/actions/workflows/build_release.yml)

CLI tool to fetch project/repository data from several VCS backends like Bitbucket (Datacenter/Cloud)/Gitlab/Github
and (interactively) scan one/many with Gitleaks.

> [!NOTE]
> Don't share output reports with non-redacted secrets irresponsibly.
 
## Supported backends
* Bitbucket Datacenter
* Bitbucket Cloud
* Gitlab
* Github

## Acknowledgements
This project utilizes the fantastic [gitleaks](https://github.com/gitleaks/gitleaks) tool by Zachary Rice and contributors for detecting secrets in code. We are grateful for their work under the MIT License.

## Maintainers
This project is maintained by **Reinier Vegter**.

* **[Github](https://github.com/reinier-vegter)**
* **[LinkedIn](https://www.linkedin.com/in/reiniervegter/)**
* **[reiniervegter.dev](https://reiniervegter.dev)**

# Prerequisites
- docker up and working
- `.some_info` file with base URL's and / personal access tokens.
  See [.some_info.example](./.some_info.example).
- In case of endpoints with private CA signed certificates, put a `.crt` file like `my_ca.crt` in the working folder, it will automatically be appended to the global trust store.

# Run

## From docker image (simplest way)

Visit [gitleaks-bulk on Docker hub](https://hub.docker.com/r/rvegter/gitleaks-bulk) for details.

```shell
docker pull rvegter/gitleaks-bulk
alias gitleaks-bulk='docker run --rm -ti -v "$PWD":/work -u $(id -u ${USER}):$(id -g ${USER}) rvegter/gitleaks-bulk:latest'
gitleaks-bulk --help
```

> [!NOTE]
> Note this uses gitleaks-bulk and gitleaks in one image.

## Download the binary

- Download binary from [Ubuntu binary](./dist/ubuntu/gitleaks-bulk) (not implemented yet)
- chmod +x gitleaks-bulk
- `./gitleaks-bulk --help`

> [!NOTE]
> Note that by default this uses a docker image for gitleaks. 
> In case you need to fiddle with gitleaks itself, this might be the better way since it can print all gitleaks docker-command being used (use `--verbose` or `--interactive`).

## Examples

Interactive mode against Bitbucket/Bitbucket cloud/Gitlab/Github repo data:
```
./gitleaks-bulk \
   --bitbucket_dc \
   --bitbucket_cloud \
   --gitlab \
   --github \
   --interactive
```

or short flags
```
./gitleaks-bulk -BD -BC -GL -GH -i
```

Use `--groupfilter` to filter repo's on group name ("project" in Bitbucket or "group" in Gitlab etc):
```
./gitleaks-bulk \
  --gitlab \
  --groupfilter my-group \
  --force_scan
```

Same for `--repofilter`:
```
./gitleaks-bulk \
  --gitlab \
  --repofilter 'my-repo|your-repo' \
  --force_scan
```

Use `--group_repo_filter` or `-f` to filter repo's on both group and repo names (Gitlab and Bitbucket at once):
```
./gitleaks-bulk \
  -GL -BB \
  -f 'something|foo|bar' \
  --force_scan
```

Update existing dataset with fresh API data and use interactive mode:
```
./gitleaks-bulk \
   --bitbucket \
   --gitlab \
   --updateinfo \
   --interactive
```

Generate executive report for specific repo's/groups.  
Assumes scans were executed before.
```
./gitleaks-bulk \
  --executive_report \
  -f 'my-repo|my-group'
```

**Some remarks:**

- Repositories will be cloned in `output/repos/`.  
- Reports will be saved in `output/reports/`.
- For authentication, generate a personal access token for your backend.
- Repo data will only be fetched once from each backend, so remove `output/repos_*.yaml` to refresh it, or run with `--updateinfo`.  
  Note last branch and contact info will be refreshed anyway on every scan.
- Any `.crt` files in the working folder will be added to the truststore in runtime (use for custom signed TLS endpoints)

# Options

```
usage: gitleaks-bulk [-h] [--updateinfo] [--executive_report] [-r REPOFILTER] [-g GROUPFILTER] [-f GROUP_REPO_FILTER]
               [--rulesfilter RULESFILTER] [--noscan] [--defaultbranch] [-S] [--no_clone] [--no_clone_update] [-v] [-i]
               [--no_redacting] [--gitleaks_image GITLEAKS_IMAGE] [--localgitleaks] [--reports_format REPORTS_FORMAT]
               [--gitleaks_conf GITLEAKS_CONF] [-GL] [-BB] [-BC] [-GH]

A CLI tool to scan repositories with Gitleaks in bulk, supporting Bitbucket DC and Gitlab. Note if no data is present, it will
be fetched once. After that existing data will be used and not updated, unless removed from disk.

options:
  -h, --help            show this help message and exit
  --updateinfo          Update repo/branch information from all backends
  --executive_report    Do not clone/scan but generate an executive report (optional)
  -r REPOFILTER, --repofilter REPOFILTER
                        Repository name filter (python regex). Used after groupfilter if enabled. (optional)
  -g GROUPFILTER, --groupfilter GROUPFILTER
                        Group name filter (python regex). Used prior to repofilter. (optional)
  -f GROUP_REPO_FILTER, --group_repo_filter GROUP_REPO_FILTER
                        Group/repo name filter (python regex). Cannot be used in conjunction with --repofilter or
                        --groupfilter (optional)
  --rulesfilter RULESFILTER
                        Gitleaks rules filter (python regex, rule ID in toml config) (optional)
  --noscan              Do not scan projects with gitleaks (optional)
  --defaultbranch       Scan default branch instead of most recently committed branch. (optional)
  -S, --force_scan      Scan projects with gitleaks, even if already scanned (optional)
  --no_clone            Do not clone git repos (optional)
  --no_clone_update     Do not update every git repo to it's latest state (optional)
  -v, --verbose         Verbose output, no progress bars (optional)
  -i, --interactive     Interactively pick a project to clone/scan (optional)
  --no_redacting        Turn off gitleaks secret redacting in reports (optional)
  --gitleaks_image GITLEAKS_IMAGE
                        Gitleaks docker image to use. Default: [zricethezav/gitleaks:latest] (optional)
  --localgitleaks       Use local gitleaks command instead of through docker (optional)
  --reports_format REPORTS_FORMAT
                        Gitleaks report format (output format (json, csv, junit, sarif) (default "csv")) (optional)
  --gitleaks_conf GITLEAKS_CONF
                        Gitleaks config file (.toml) to use. Default: [gitleaks-custom.toml] (optional)
  -GL, --gitlab         Use backend backend (optional)
  -BB, --bitbucket_dc   Use backend backend (optional)
  -BC, --bitbucket_cloud
                        Use backend backend (optional)
  -GH, --github         Use backend backend (optional)
```

# Gitleaks rules
- Note gitleaks.toml is mutated pretty often. Found that some versions don't work as well.
- Current version of `gitleaks-orig.toml` from https://github.com/gitleaks/gitleaks/blob/bae6f759d94812fd06a3e041e2af349768dee7f6/config/gitleaks.toml .
- Custom rules/changes to be created in `gitleaks-vi.toml`

# Process hint

Steps to take:
1. Perform scans on projects most recent branches: `./gitleaks-bulk -BB -GH -f 'FILTER1|FILTER2'`
2. Generate executive report for prio and contact details: `./gitleaks-bulk -f 'FILTER1|FILTER2' --executive_report`.
3. Create tickets for each affected repo, inform the teams/contacts and provide `csv` reports from the scan.
4. Have the team remove the secrets from the repository.
    1. In case of prod secrets, consider them COMPROMISED, secrets must be rotated.
    2. In case of secrets that cannot be rotated, cleanup git history (see below).
5. Perform rescan in bulk, or in interactive (`--interactive`) mode to validate fix.
6. Optionally regenerate the executive report to get latest overview

## Cleanup history

> [!NOTE]
> This overwrites Git history. Be punctual and use at your own risk.

Get `git-filter-repo` package:
```shell
env/bin/pip install git-filter-repo
```

Replace JWT tokens in git history (example):  
```shell
env/bin/git-filter-repo \
  --path "output/repos/SOME REPO" \
  --replace-text <(echo 'regex:(eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+)=>REDACTED')
```

Replace (password) string in git history (example):  
```shell
env/bin/git-filter-repo \
  --path "output/repos/SOME REPO" \
  --replace-text <(echo 'password=>REDACTED')
```

Push history back to repo:  
| THIS OVERWRITES WHOLE GIT HISTORY (which is the idea), ALIGN WITH TEAM AND HAVE A BACKUP AT HAND
```shell
git push origin --force
```
