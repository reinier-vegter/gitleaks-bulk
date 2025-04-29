#!/usr/bin/env python3

import os
import sys
import re
import requests
import argparse


def main():
    parser = argparse.ArgumentParser(description='Generate Docker tag list for README')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of tag groups to display')
    args = parser.parse_args()

    verbose = args.verbose
    max_tag_groups = args.limit

    # Get required environment variables with defaults
    env = {
        'GITHUB_REPOSITORY': os.environ.get('GITHUB_REPOSITORY'),
        'DOCKERFILE_PATH': os.environ.get('DOCKERFILE_PATH', 'Dockerfile'),
        'DEFAULT_BRANCH': os.environ.get('DEFAULT_BRANCH', 'master'),
        'README_TEMPLATE_PATH': os.environ.get('README_TEMPLATE_PATH', 'README.dockerhub_template.md'),
        'README_OUTPUT': os.environ.get('README_OUTPUT', 'README.dockerhub.md'),
        'VERSION_TAG_PATTERN': os.environ.get('VERSION_TAG_PATTERN', '^[0-9]+\\.[0-9]+\\.[0-9]+.*'),
        'FULL_VERSION': os.environ.get('FULL_VERSION'),
        'LATEST_IMAGE_DIGEST': os.environ.get('LATEST_IMAGE_DIGEST'),
        'DOCKERHUB_USERNAME': os.environ.get('DOCKERHUB_USERNAME')
    }

    # Check required variables
    required = ['GITHUB_REPOSITORY', 'FULL_VERSION', 'DOCKERHUB_USERNAME']
    missing = [k for k in required if not env[k]]
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Configuration
    repo_url = f"https://github.com/{env['GITHUB_REPOSITORY']}"
    full_readme_path = env['README_TEMPLATE_PATH']
    readme_output_path = env['README_OUTPUT']
    dockerhub_repo = f"{env['DOCKERHUB_USERNAME']}/gitleaks-bulk"

    print(f"Processing Docker tags for {dockerhub_repo} version {env['FULL_VERSION']}")

    # Extract version components
    version_parts = re.search(r'^(\d+)\.(\d+)\.(\d+)', env['FULL_VERSION'])
    if not version_parts:
        print(f"Error: Could not parse version from {env['FULL_VERSION']}")
        sys.exit(1)

    major, minor, patch = version_parts.groups()
    numerical_version = f"{major}.{minor}.{patch}"
    full_version = env['FULL_VERSION']  # With gitleaks version suffix

    # Define our tag hierarchy for the latest version
    latest_tags = [
        "latest",
        major,
        f"{major}.{minor}",
        numerical_version,
        full_version
    ]

    # Create two tag groups: latest and historical
    tag_groups = {
        'latest': {
            'version': numerical_version,
            'tags': set(latest_tags),
            'link': f"{repo_url}/blob/{numerical_version}/{env['DOCKERFILE_PATH']}"
        }
    }

    # Fetch historical tags from Docker Hub
    try:
        # Get tags from Docker Hub API
        api_url = f"https://hub.docker.com/v2/repositories/{dockerhub_repo}/tags?page_size=100"
        version_data = {}  # Store versions with their tags

        while api_url:
            response = requests.get(api_url)
            if response.status_code != 200:
                print(f"Warning: Error fetching tags: {response.status_code}")
                break

            data = response.json()

            # Extract tag names and versions
            for tag_data in data['results']:
                tag = tag_data['name']

                # Skip invalid or our latest tags
                if not tag or tag in latest_tags:
                    continue

                # Extract version information
                version_match = re.search(r'^(\d+\.\d+\.\d+)', tag)
                if version_match:
                    version = version_match.group(1)

                    # Skip if this matches our current version
                    if version == numerical_version:
                        continue

                    # Add tag to its version group
                    if version not in version_data:
                        version_data[version] = []
                    version_data[version].append(tag)

            # Check for next page
            api_url = data.get('next')

        # Sort versions by newest first and limit to max_tag_groups-1 (to leave room for latest)
        sorted_versions = sorted(version_data.keys(),
                                 key=lambda v: [int(p) for p in v.split('.')],
                                 reverse=True)

        # Take only the most recent versions (leaving room for latest)
        historical_versions = sorted_versions[:max_tag_groups - 1]

        # Process each historical version
        for version in historical_versions:
            ver_parts = version.split('.')
            major_ver = ver_parts[0]
            minor_ver = f"{major_ver}.{ver_parts[1]}"

            # Create version tags set
            version_tags = set(version_data[version])

            # Add major/minor versions only if they don't clash with latest
            if major_ver != major and major_ver not in latest_tags:
                version_tags.add(major_ver)

            if minor_ver != f"{major}.{minor}" and minor_ver not in latest_tags:
                version_tags.add(minor_ver)

            # Add to tag groups
            tag_groups[version] = {
                'version': version,
                'tags': version_tags,
                'link': f"{repo_url}/blob/{version}/{env['DOCKERFILE_PATH']}"
            }

    except Exception as e:
        print(f"Warning: Error fetching tags from Docker Hub: {str(e)}")

    # Generate Markdown list
    markdown_list = []

    # Sort version groups - latest first, then by version number
    sorted_groups = sorted(tag_groups.keys(),
                           key=lambda v: [0 if v == 'latest' else 1,
                                          [-int(p) for p in v.split('.')] if v != 'latest' else [0]])

    # Process each version group
    for version_key in sorted_groups:
        group = tag_groups[version_key]

        # Skip empty groups
        if not group['tags']:
            continue

        # Categorize tags
        has_latest = 'latest' in group['tags']
        majors = []
        major_minors = []
        patches = []
        full_versions = []

        for tag in group['tags']:
            if tag == 'latest':
                continue
            elif re.match(r'^\d+$', tag):
                majors.append(tag)
            elif re.match(r'^\d+\.\d+$', tag):
                major_minors.append(tag)
            elif re.match(r'^\d+\.\d+\.\d+$', tag):
                patches.append(tag)
            elif re.match(r'^\d+\.\d+\.\d+', tag):
                full_versions.append(tag)

        # Sort each category
        majors.sort(key=int)
        major_minors.sort(key=lambda x: [int(p) for p in x.split('.')])
        patches.sort(key=lambda x: [int(p) for p in x.split('.')])
        full_versions.sort(key=lambda x: x.split('-')[0])

        # Build markdown tags in order
        markdown_parts = []

        # Latest first
        if has_latest:
            markdown_parts.append(f"[`latest`]({group['link']})")

        # Major versions
        for tag in majors:
            markdown_parts.append(f"[`{tag}`]({group['link']})")

        # Major.minor versions
        for tag in major_minors:
            markdown_parts.append(f"[`{tag}`]({group['link']})")

        # Patch versions
        for tag in patches:
            markdown_parts.append(f"[`{tag}`]({group['link']})")

        # Full versions
        for tag in full_versions:
            markdown_parts.append(f"[`{tag}`]({group['link']})")

        # Add to list
        if markdown_parts:
            markdown_list.append(f"* {', '.join(markdown_parts)}")

    # Join the markdown list with newlines
    markdown_content = '\n'.join(markdown_list)

    if not markdown_content:
        print("Warning: No tags found or processed. Generated list is empty.")
        markdown_content = "* No tags available."

    if verbose:
        print(f"Output: \n{markdown_content}")

    # Update the README with the new tag section
    try:
        with open(full_readme_path, 'r') as f:
            readme_content = f.read()

        # Replace the tags section
        pattern = r'(<!-- TAGS_START -->).*(<!-- TAGS_END -->)'
        replacement = f"\\1\n{markdown_content}\n\\2"
        updated_content = re.sub(pattern, replacement, readme_content, flags=re.DOTALL)

        with open(readme_output_path, 'w') as f:
            f.write(updated_content)

        print(f"Successfully updated {readme_output_path} with {len(markdown_list)} tag groups")
    except Exception as e:
        print(f"Error updating README: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()