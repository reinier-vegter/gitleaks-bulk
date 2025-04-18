FROM ubuntu:latest

# This should trigger gb-dockerfile-password
ENV API_PASSWORD=DockerPasswordS3cr3t!
ARG SECRET_KEY=arg_secret_abcdef123456

# Should not trigger (placeholder)
# ENV PLACEHOLDER_PASSWORD=${PASSWORD_VAR}
