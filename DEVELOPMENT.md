# Runtime/interpreter for local testing/debugging

Note this project is built for Python 3.12+.

## Docker image

```
docker build --target base -t gitleaks-bulk-local:latest .
```

Or to run tests with:
```
docker build --target dev -t gitleaks-bulk-local:dev .
```

For sake of ease, set an alias for future commands:

```
alias imagerun='docker run -it --rm -v "${PWD}:/opt/project" -u $(id -u ${USER}):$(id -g ${USER}) -w /opt/project --entrypoint= gitleaks-bulk-local:dev'
```

## Local python

Setup `pyenv` and install the right interpreter (in case you want the non-docker interpreter for PyCharm and others), like so

```
pyenv install 3.12.9
```

# Tests

This project uses pytest tests, see `tests/`.

## Setup and Running Tests

### Installation
Build image `gitleaks-bulk-local:dev` , see above. 

### Running Tests

Run all tests:

```bash
imagerun pytest
```

or use `pytest` from the local system.

## Adding New Tests

When adding new tests, follow these patterns:

1. Use the appropriate mock data generator for the backend being tested
2. Use the mock client fixtures for API interactions
3. Properly patch external dependencies
4. Add fixtures to `tests/conftest.py` if they're used across multiple test files