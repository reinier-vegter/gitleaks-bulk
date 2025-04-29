#!/bin/bash

# --- Configuration (Read from Environment Variables) ---
[[ "$1" == "--verbose" ]] && VERBOSE=true || VERBOSE=

# --- Validate Inputs ---
if [[ -z "$GITHUB_REPOSITORY" || -z "$DOCKERFILE_PATH" || -z "$DEFAULT_BRANCH" ||
      -z "$README_TEMPLATE_PATH" || -z "$VERSION_TAG_PATTERN" || -z "$README_OUTPUT" ||
      -z "$FULL_VERSION" || -z "$DOCKER_TAGS" || -z "$LATEST_IMAGE_DIGEST" ]]; then
  echo "Error: Missing required environment variables."
  echo "Need: GITHUB_REPOSITORY, DOCKERFILE_PATH, DEFAULT_BRANCH, README_TEMPLATE_PATH, VERSION_TAG_PATTERN, README_OUTPUT, DOCKER_TAGS, LATEST_IMAGE_DIGEST"
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
echo "Latest image digest: ${LATEST_IMAGE_DIGEST}"
echo "Docker Tags (truncated): ${DOCKER_TAGS:0:50}..." # Show a truncated view
echo "---------------------"

if [[ ! -f "$FULL_README_PATH" ]]; then
  echo "Error: README template file not found at ${FULL_README_PATH}"
  exit 1
fi

# --- Process tags and create a proper hierarchy ---
echo "Processing Docker tags..."

# Store digest-tag mapping
declare -A DIGEST_TAGS
declare -A DIGEST_SEMVER

# First pass: organize tags by digest
for tag_digest in $DOCKER_TAGS; do
  # Split tag:digest format
  tag=$(echo "$tag_digest" | cut -d':' -f1)
  digest=$(echo "$tag_digest" | cut -d':' -f2-)

  # Skip empty or invalid tags
  if [[ -z "$tag" || "$tag" == "." || "$tag" == "" ]]; then
    continue
  fi

  # Store this tag with its digest
  if [[ -n "$digest" ]]; then
    # Add to the digest's list of tags
    DIGEST_TAGS["$digest"]="${DIGEST_TAGS["$digest"]} $tag"

    # If it's a semantic version, store it
    if [[ "$tag" =~ $VERSION_TAG_PATTERN ]]; then
      numerical=$(echo "$tag" | grep -o -P '^[0-9]+\.[0-9]+\.[0-9]+' || echo "")
      if [[ -n "$numerical" ]]; then
        DIGEST_SEMVER["$digest"]="$numerical"
      fi
    fi
  fi
done

# --- Find the digest that should be associated with "latest" ---
latest_digest=""
# Extract a shorter version of the digest for comparison
shortened_latest_digest=$(echo "$LATEST_IMAGE_DIGEST" | cut -d':' -f2 | cut -c1-12)
echo "Looking for digest containing: $shortened_latest_digest"

# Look for a matching digest
for digest in "${!DIGEST_TAGS[@]}"; do
  if [[ "$digest" == *"$shortened_latest_digest"* ]]; then
    latest_digest="$digest"
    echo "Found digest for latest: $latest_digest"
    break
  fi
done

# If we found the latest digest, ensure it includes the "latest" tag
if [[ -n "$latest_digest" ]]; then
  # Add "latest" to the tags for this digest if not already there
  if [[ ! "${DIGEST_TAGS[$latest_digest]}" == *"latest"* ]]; then
    echo "Adding 'latest' tag to digest: $latest_digest"
    DIGEST_TAGS["$latest_digest"]="${DIGEST_TAGS[$latest_digest]} latest"
  fi

  # For any other digest, remove "latest" if it exists
  for digest in "${!DIGEST_TAGS[@]}"; do
    if [[ "$digest" != "$latest_digest" && "${DIGEST_TAGS[$digest]}" == *"latest"* ]]; then
      echo "Removing 'latest' tag from digest: $digest"
      DIGEST_TAGS["$digest"]=$(echo "${DIGEST_TAGS[$digest]}" | sed 's/latest//g' | sed 's/  / /g' | sed 's/^ //g' | sed 's/ $//g')
    fi
  done
fi

# --- Generate Markdown list ---
MARKDOWN_LIST=""

# Sort digests by their semver (newest first) using a temp file
temp_file=$(mktemp)
for digest in "${!DIGEST_SEMVER[@]}"; do
  echo "${DIGEST_SEMVER[$digest]} $digest" >> "$temp_file"
done

# Sort by semver in descending order
sorted_digests=$(sort -rV "$temp_file" | awk '{print $2}')
rm "$temp_file"

# If we have a latest digest, make sure it comes first
if [[ -n "$latest_digest" ]]; then
  # Remove latest_digest from sorted_digests if it exists
  sorted_digests=$(echo "$sorted_digests" | sed "s|$latest_digest||" | tr -s ' ')
  # Add it to the front
  sorted_digests="$latest_digest $sorted_digests"
fi

# Process each digest and create the markdown
for digest in $sorted_digests; do
  [ $VERBOSE ] && echo "Processing digest: $digest"
  tag_list=${DIGEST_TAGS["$digest"]}

  # Skip if no tags found
  if [[ -z "$tag_list" ]]; then
    continue
  fi

  # Extract the numerical version for GitHub link
  numerical_version=""
  for tag in $tag_list; do
    if [[ "$tag" =~ $VERSION_TAG_PATTERN ]]; then
      numerical=$(echo "$tag" | grep -o -P '^[0-9]+\.[0-9]+\.[0-9]+' || echo "")
      if [[ -n "$numerical" ]]; then
        numerical_version="$numerical"
        break
      fi
    fi
  done

  # Use the correct tag for the GitHub link (default branch if no numerical version found)
  tag_for_link="${numerical_version:-$DEFAULT_BRANCH}"
  github_link="${REPO_URL}/blob/${tag_for_link}/${FULL_DOCKERFILE_REPO_PATH}"

  # Create arrays for the different tag types
  has_latest=false
  declare -a majors=()
  declare -a major_minors=()
  declare -a patches=()
  declare -a full_versions=()

  # Categorize tags
  for tag in $tag_list; do
    # Skip empty tags
    if [[ -z "$tag" || "$tag" == "." || "$tag" == "" ]]; then
      continue
    fi

    if [[ "$tag" == "latest" ]]; then
      has_latest=true
    elif [[ "$tag" =~ ^[0-9]+$ ]]; then
      majors+=("$tag")
    elif [[ "$tag" =~ ^[0-9]+\.[0-9]+$ ]]; then
      major_minors+=("$tag")
    elif [[ "$tag" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      patches+=("$tag")
    elif [[ "$tag" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]]; then
      full_versions+=("$tag")
    fi
  done

  # Build the formatted tag list in the correct order
  markdown_tags=""

  # 1. Latest first
  if [[ "$has_latest" == true ]]; then
    markdown_tags="[\`latest\`](${github_link})"
  fi

  # 2. Major versions (e.g., 1)
  for tag in $(printf '%s\n' "${majors[@]}" | sort -V); do
    if [[ -n "$markdown_tags" ]]; then
      markdown_tags="${markdown_tags}, "
    fi
    markdown_tags="${markdown_tags}[\`${tag}\`](${github_link})"
  done

  # 3. Major.minor versions (e.g., 1.0)
  for tag in $(printf '%s\n' "${major_minors[@]}" | sort -V); do
    if [[ -n "$markdown_tags" ]]; then
      markdown_tags="${markdown_tags}, "
    fi
    markdown_tags="${markdown_tags}[\`${tag}\`](${github_link})"
  done

  # 4. Major.minor.patch versions (e.g., 1.0.20)
  for tag in $(printf '%s\n' "${patches[@]}" | sort -V); do
    if [[ -n "$markdown_tags" ]]; then
      markdown_tags="${markdown_tags}, "
    fi
    markdown_tags="${markdown_tags}[\`${tag}\`](${github_link})"
  done

  # 5. Full versions with suffixes (e.g., 1.0.20-v8.24.3)
  for tag in $(printf '%s\n' "${full_versions[@]}" | sort -V); do
    if [[ -n "$markdown_tags" ]]; then
      markdown_tags="${markdown_tags}, "
    fi
    markdown_tags="${markdown_tags}[\`${tag}\`](${github_link})"
  done

  # Add to markdown list
  if [[ -n "$markdown_tags" ]]; then
    MARKDOWN_LIST+="* ${markdown_tags}\n"
  fi
done

# --- Inject the list into the README template ---
if [[ -z "$MARKDOWN_LIST" ]]; then
  echo "Warning: No tags found or processed. Generated list is empty."
  MARKDOWN_LIST="* No tags available.\n"
fi

[ $VERBOSE ] && echo -e "Output: \n===\n${MARKDOWN_LIST}\n==="

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