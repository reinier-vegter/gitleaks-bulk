# gitleaks-bulk Docker Image

[![Build and Release](https://github.com/reinier-vegter/gitleaks-bulk/actions/workflows/build_release.yml/badge.svg)](https://github.com/reinier-vegter/gitleaks-bulk/actions/workflows/build_release.yml) 
[![Docker Pulls](https://img.shields.io/docker/pulls/rvegter/gitleaks-bulk.svg)](https://hub.docker.com/r/rvegter/gitleaks-bulk)
[![GitHub Repo](https://img.shields.io/badge/github-repo-blue.svg)](https://github.com/rvegter/gitleaks-bulk)

This is the official Docker image for `gitleaks-bulk`, a CLI tool to fetch repository data from various VCS backends and scan them using Gitleaks.

> [!NOTE]
> For full documentation, usage examples, options, and contribution guidelines, please see the [README on Github](https://github.com/reinier-vegter/gitleaks-bulk/blob/master/README.md).

> [!NOTE]
> Don't share output reports with non-redacted secrets irresponsibly.

## Supported backends
* Bitbucket Datacenter
* Bitbucket Cloud
* Gitlab
* Github

## Tags
<!-- TAGS_START -->
* [`latest`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.21/Dockerfile), [`1`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.21/Dockerfile), [`1.0`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.21/Dockerfile), [`1.0.21`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.21/Dockerfile), [`1.0.21-v8.24.3`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.21/Dockerfile)
* [`1.0.20`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.20/Dockerfile), [`1.0.20-v8.24.3`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.20/Dockerfile)
* [`1.0.19`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.19/Dockerfile), [`1.0.19-v8.24.3`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.19/Dockerfile)
* [`1.0.17-v8.24.3`](https://github.com/reinier-vegter/gitleaks-bulk/blob/1.0.17/Dockerfile)

<!-- TAGS_END -->

## Prerequisites
- docker up and working
- `.some_info` file with base URL's and / personal access tokens.
  See [.some_info.example](https://github.com/reinier-vegter/gitleaks-bulk/blob/master/.some_info.example).
- In case of endpoints with private CA signed certificates, put a `.crt` file like `my_ca.crt` in the working folder, it will automatically be appended to the global trust store.

## Quick Start
```shell
docker pull rvegter/gitleaks-bulk
alias gitleaks-bulk='docker run --rm -ti -v "$PWD":/work -u $(id -u ${USER}):$(id -g ${USER}) rvegter/gitleaks-bulk:latest'
gitleaks-bulk --help
```
