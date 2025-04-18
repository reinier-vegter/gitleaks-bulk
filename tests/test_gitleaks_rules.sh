#!/bin/bash

# --- Configuration ---
GITLEAKS_CONFIG_FILE="gitleaks-custom.toml"
SAMPLES_DIR="tests/gitleaks_samples"
GITLEAKS_CMD="gitleaks" # Assumes gitleaks is in PATH

# Check if gitleaks command exists
if ! command -v $GITLEAKS_CMD &> /dev/null; then
    echo "ERROR: '$GITLEAKS_CMD' command not found. Please install gitleaks."
    exit 1
fi

# Check if config file exists
if [ ! -f "$GITLEAKS_CONFIG_FILE" ]; then
    echo "ERROR: Gitleaks config file not found at '$GITLEAKS_CONFIG_FILE'"
    exit 1
fi

# Check if samples directory exists
if [ ! -d "$SAMPLES_DIR" ]; then
    echo "ERROR: Samples directory not found at '$SAMPLES_DIR'"
    exit 1
fi

# --- Test Definitions ---
# Format: "rule_id" "sample_file_relative_path"
tests=(
    "gb-private-key"            "$SAMPLES_DIR/sample_gb-private-key.pem"
    "gb-script-py-password"     "$SAMPLES_DIR/sample_gb-script-py-password.py"
    "gb-dockerfile-password"    "$SAMPLES_DIR/sample_gb-dockerfile-password.Dockerfile"
    "gb-yaml-env-password"      "$SAMPLES_DIR/sample_gb-yaml-env-password.yaml"
    "gb-yaml-password"          "$SAMPLES_DIR/sample_gb-yaml-password.yml"
)

# --- Test Execution ---
failed_tests=0
total_tests=${#tests[@]}
test_count=0

echo "Starting Gitleaks custom rule tests..."
echo "Using config: $GITLEAKS_CONFIG_FILE"
echo "-------------------------------------"

for (( i=0; i<${#tests[@]}; i+=2 )); do
    rule_id="${tests[i]}"
    sample_file="${tests[i+1]}"
    test_count=$((test_count + 1))

    echo -n "[$test_count/$((total_tests/2))] Testing rule '$rule_id' against '$sample_file'... "

    if [ ! -f "$sample_file" ]; then
        echo "FAILED (Sample file not found!)"
        failed_tests=$((failed_tests + 1))
        continue
    fi

    # Run gitleaks targeting the specific rule and file
    # We expect a non-zero exit code (leak found)
    $GITLEAKS_CMD detect \
        --config "$GITLEAKS_CONFIG_FILE" \
        --source "$sample_file" \
        --enable-rule "$rule_id" \
        --no-git \
        --verbose \
        --log-level=error > /dev/null 2>&1 # Suppress normal output, only care about exit code

    exit_code=$?

    # Gitleaks exits with 1 (or other non-zero) if leaks are found by default.
    # If --exit-code is used in config or CLI, adjust accordingly.
    # Gitleaks v8.18+ uses exit code 1 for findings, 0 for no findings, 2 for error.
    # Let's assume exit code 1 means findings found (success for this test).
    if [ $exit_code -eq 1 ]; then
        echo "PASSED (Leak detected as expected)"
    elif [ $exit_code -eq 0 ]; then
        echo "FAILED (No leak detected!)"
        failed_tests=$((failed_tests + 1))
    else
        echo "FAILED (Gitleaks command error - exit code $exit_code)"
        failed_tests=$((failed_tests + 1))
    fi
done

echo "-------------------------------------"

# --- Summary ---
if [ $failed_tests -eq 0 ]; then
    echo "All tests PASSED!"
    exit 0
else
    echo "$failed_tests test(s) FAILED."
    exit 1
fi
