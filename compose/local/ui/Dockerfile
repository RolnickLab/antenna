# Node version should always match the version in `ui/.nvmrc`
FROM node:18

# Set the working directory in the container
WORKDIR /app

COPY ./ /app

# Configure git to trust the /app directory
# Not necessary for default, but needed for frontend compose override to have proper
# build number
RUN git config --global --add safe.directory /app

# Don't try to open a browser
ENV BROWSER=none

# Build the ui
RUN yarn install \
    && yarn build

# Expose the port the app runs on
EXPOSE 4000

CMD ["sh", "-c", "yarn preview --debug --host 0.0.0.0 --port 4000"]
