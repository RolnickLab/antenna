# Node version should always match the version in `ui/.nvmrc`
FROM node:18

# Set the working directory in the container
WORKDIR /app

# Configure git to trust the /app directory
RUN git config --global --add safe.directory /app

# Don't try to open a browser
ENV BROWSER=none

# Expose the port the app runs on
EXPOSE 4000

# Define the command to run the app
# CMD ["yarn", "start", "--host", "0.0.0.0", "--port", "4000"]

CMD ["sh", "-c", "yarn install && yarn start --host 0.0.0.0 --port 4000"]
