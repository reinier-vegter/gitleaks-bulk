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
# DOCKERHUB_IMAGE_NAME: Docker Hub image name (e.g., "yourusername/yourimage")

# --- Validate Inputs ---
if [[ -z "$GITHUB_REPOSITORY" || -z "$DOCKERFILE_PATH" || -z "$DEFAULT_BRANCH" || -z "$README_TEMPLATE_PATH" || -z "$VERSION_TAG_PATTERN" || -z "$README_OUTPUT" || -z "$FULL_VERSION" || -z "$DOCKERHUB_IMAGE_NAME" ]]; then
  echo "Error: Missing required environment variables."
  echo "Need: GITHUB_REPOSITORY, DOCKERFILE_PATH, DEFAULT_BRANCH, README_TEMPLATE_PATH, VERSION_TAG_PATTERN, README_OUTPUT, DOCKERHUB_IMAGE_NAME"
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
echo "DockerHub Image Name: ${DOCKERHUB_IMAGE_NAME}"
echo "---------------------"

if [[ ! -f "$FULL_README_PATH" ]]; then
  echo "Error: README template file not found at ${FULL_README_PATH}"
  exit 1
fi

# --- Fetch Docker Hub Tags and Digests ---
echo "Fetching Docker Hub tags for ${DOCKERHUB_IMAGE_NAME}..."
DOCKER_TAGS=$(docker run --rm --entrypoint /bin/sh alpine:latest -c "apk add --no-cache curl && curl -s https://hub.docker.com/v2/repositories/${DOCKERHUB_IMAGE_NAME}/tags | jq -r '.results[].name'")
if [[ -z "$DOCKER_TAGS" ]]; then
    echo "Warning: No tags found on Docker Hub for ${DOCKERHUB_IMAGE_NAME}."
    DOCKER_TAGS=""
fi


# --- Process Docker Hub Tags matching the pattern ---
echo "Processing Docker Hub tags matching pattern '${VERSION_TAG_PATTERN}'..."
MAJORS=()
MAJOR_MINORS=()
MARKDOWN_LIST=""
for tag in $DOCKER_TAGS; do
  if [[ "$tag" =~ $VERSION_TAG_PATTERN || "$tag" == "latest" ]]; then
    echo "  Tag found: ${tag}"
    # The digest can be fetched by running a container with the tag
    digest=$(docker run --rm --entrypoint /bin/sh "${DOCKERHUB_IMAGE_NAME}:${tag}" -c "echo $(cat /etc/hostname)" 2>&1)

    if [[ -n "$digest" && "$digest" != "Unable to find image" ]]; then
      github_link="${REPO_URL}/blob/${digest}/${FULL_DOCKERFILE_REPO_PATH}"
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
      fi
      if ! printf '%s\n' "${MAJORS[@]}" | grep -q -F -x -- "$major"; then
        MAJORS+=($major)
        version_string="[\`${major}\`](${github_link}), ${version_string}"
      fi

      if [[ "$tag" == "latest" ]]; then
        echo "This is the *latest* tag"
        version_string="${version_string}, [\`latest\`](${github_link})"
        version_string="${version_string}, [\`${FULL_VERSION}\`](${github_link})"
      fi
      MARKDOWN_LIST+="*   ${version_string}\n"
    else
      echo "  Warning: Could not determine digest for tag ${tag}."
    fi
  fi
done

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