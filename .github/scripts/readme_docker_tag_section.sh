#!/bin/bash

# --- Configuration (Read from Environment Variables) ---
# Provided by GitHub Actions automatically:
# GITHUB_REPOSITORY: owner/repo
# GITHUB_SERVER_URL: e.g. https://github.com (needed for GHE)
# GITHUB_WORKSPACE: Path where the repo is checked out
# User-defined Environment Variables in Workflow:
# DOCKERFILE_PATH: Relative path to the Dockerfile (e.g., "Dockerfile" or "build/Dockerfile")
# DEFAULT_BRANCH: Name of the default branch (e.g., "main")
# README_TEMPLATE_PATH: Relative path to the README template (e.g., "README.dockerhub.md")
# VERSION_TAG_PATTERN: Glob pattern for version tags (e.g., "v*.*.*" or "[0-9]*.*.*")

# --- Validate Inputs ---
if [[ -z "$GITHUB_REPOSITORY" || -z "$DOCKERFILE_PATH" || -z "$DEFAULT_BRANCH" || -z "$README_TEMPLATE_PATH" || -z "$VERSION_TAG_PATTERN" || -z "$README_OUTPUT" || -z "$FULL_VERSION" ]]; then
  echo "Error: Missing required environment variables."
  echo "Need: GITHUB_REPOSITORY, DOCKERFILE_PATH, DEFAULT_BRANCH, README_TEMPLATE_PATH, VERSION_TAG_PATTERN, README_OUTPUT"
  exit 1
fi

REPO_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}"
FULL_README_PATH="${GITHUB_WORKSPACE}/${README_TEMPLATE_PATH}"
README_OUTPUT_PATH="${GITHUB_WORKSPACE}/${README_OUTPUT}"
FULL_DOCKERFILE_REPO_PATH="${DOCKERFILE_PATH}" # Path relative to repo root

echo "--- Configuration ---"
echo "Repo URL: ${REPO_URL}"
echo "Dockerfile Path in Repo: ${FULL_DOCKERFILE_REPO_PATH}"
echo "Default Branch: ${DEFAULT_BRANCH}"
echo "README Template: ${FULL_README_PATH}"
echo "Version Tag Pattern: ${VERSION_TAG_PATTERN}"
echo "Full version: ${FULL_VERSION}"
echo "---------------------"

if [[ ! -f "$FULL_README_PATH" ]]; then
    echo "Error: README template file not found at ${FULL_README_PATH}"
    exit 1
fi

DEFAULT_BRANCH_SHA=$(git rev-parse "${DEFAULT_BRANCH}" 2>/dev/null)
echo "latest sha: ${DEFAULT_BRANCH_SHA}"

# --- Process Git Tags matching the pattern ---
echo "Processing Git tags matching pattern '${VERSION_TAG_PATTERN}'..."
# Use "git tag --list" which is safer for scripting than just "git tag"
# Sort tags using version sort initially (helps determine representative tag later)

MAJORS=()
MAJOR_MINORS=()
PATCH_COUNTS=()
MARKDOWN_LIST=""
while IFS= read -r tag; do
  # Get commit SHA for the tag (handle annotated vs lightweight)
  tag_sha=$(git rev-parse "${tag}^{commit}" 2>/dev/null || git rev-parse "$tag" 2>/dev/null)

  if [[ -n "$tag_sha" ]]; then
    echo "  Tag: ${tag} -> SHA: ${tag_sha}"

    github_link="${REPO_URL}/blob/${tag_sha}/${FULL_DOCKERFILE_REPO_PATH}"

    numerical=$(echo "$tag" | grep -o -P '^[0-9]+\.[0-9]+\.[0-9]+')
    major=$(echo "$numerical" | awk -F'.' '{print $1}')
    major_minor=$(echo "$numerical" | awk -F'.' '{printf "%s.%s\n", $1, $2}')


    # Build markdown strings
    version_string="[\`${numerical}\`](${github_link})"
    if [ "${numerical}" != "${tag}" ]; then
      version_string="${version_string}, [\`${tag}\`](${github_link})"
    fi

    if ! printf '%s\n' "${MAJOR_MINORS[@]}" | grep -q -F -x -- "$major_minor"; then
      MAJOR_MINORS+=($major_minor)
      version_string="[\`${major_minor}\`](${github_link}), ${version_string}"
      PATCH_COUNTS+=("$major_minor:0")
    fi
    if ! printf '%s\n' "${MAJORS[@]}" | grep -q -F -x -- "$major"; then
      MAJORS+=($major)
      version_string="[\`${major}\`](${github_link}), ${version_string}"
    fi
    if [ "$tag_sha" = "${DEFAULT_BRANCH_SHA}" ]; then
      echo "This is the *latest* tag"
      version_string="${version_string}, [\`latest\`](${github_link})"

      # Also add full version including gitleaks tag.
      version_string="${version_string}, [\`${FULL_VERSION}\`](${github_link})"
    fi

    # Check if we've already listed 3 patch versions for this major.minor, otherwise skip.
    patch_count_index=$(printf '%s\n' "${PATCH_COUNTS[@]}" | grep -n "^${major_minor}:" | cut -d: -f1)
    if [[ -n "$patch_count_index" ]]; then
      current_count=$(echo "${PATCH_COUNTS[$((patch_count_index - 1))]}" | cut -d: -f2)
      if (( current_count < 3 )); then
        ((current_count++))
        PATCH_COUNTS[$((patch_count_index - 1))]="${major_minor}:${current_count}"
      else
        echo "Skipping tag ${tag} because 3 patch versions for ${major_minor} have already been listed."
        continue
      fi
    fi

    MARKDOWN_LIST+="*   ${version_string}\n"
  else
    echo "  Warning: Could not determine SHA for tag ${tag}."
  fi
done < <(git tag --list --sort=-v:refname | grep -E "$VERSION_TAG_PATTERN") # Sort highest version first


# --- Inject the list into the README template ---
if [[ -z "$MARKDOWN_LIST" ]]; then
    echo "Warning: No tags found or processed. Generated list is empty."
    MARKDOWN_LIST="*   No tags available.\n"
fi

echo "Injecting generated list into ${FULL_README_PATH}..."

# Use awk for safe multi-line replacement between markers
awk -v list="$MARKDOWN_LIST" '
BEGIN { printing=1 }
/<!-- TAGS_START -->/ { print; print list; printing=0 }
/<!-- TAGS_END -->/ { printing=1 }
printing { print }
' "${FULL_README_PATH}" > "${FULL_README_PATH}.tmp"

# Check if awk succeeded before moving
if [ $? -eq 0 ]; then
  mv "${FULL_README_PATH}.tmp" "${README_OUTPUT_PATH}"
  echo "Successfully saved ${README_OUTPUT_PATH}"
else
  echo "Error: awk command failed to process the README template."
  rm -f "${FULL_README_PATH}.tmp" # Clean up temp file
  exit 1
fi

echo "Script finished."