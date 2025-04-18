FROM zricethezav/gitleaks:latest AS final

ARG PYTHON_VERSION=3.12
ARG PYTHON_VERSION_MAJOR_MINOR=3.12

RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache \
        python3~=${PYTHON_VERSION} \
        py3-pip \
        libc-dev && \
        # Verify Python version immediately after install \
    ([ "$(python3 --version | awk '{print $2}' | awk -F'.' '{printf "%s.%s\n", $1, $2}')" = "$PYTHON_VERSION" ] && echo "Verified python version") || (echo "Not the expected python version" && exit 1) && \
    pip3 install --break-system-packages --no-cache-dir --upgrade pip

COPY requirements.txt /app/
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt && rm /app/requirements.txt
COPY *.py *.toml /app/

WORKDIR /work

# Set the entrypoint to run your Python script
# Using python3 explicitly is good practice
ENTRYPOINT ["python3", "/app/main.py", "--localgitleaks"]

# Default command (can be overridden at runtime)
CMD []


# Development stage (Optional: Based on final image)
FROM final AS dev
# Install development/testing tools
RUN apk add --no-cache git && \
    pip3 install --no-cache-dir pytest mock GitPython && \
    rm -rf /var/cache/apk/*
# Reset entrypoint/cmd if needed for development tasks
ENTRYPOINT []
CMD ["/bin/sh"]