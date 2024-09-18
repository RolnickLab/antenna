# Node version should always match the version in `ui/.nvmrc`
FROM node:18

# Set the working directory in the container
WORKDIR /app

# Copy package.json and yarn.lock
COPY package.json yarn.lock ./

# Install dependencies
# RUN yarn install --frozen-lockfile
RUN yarn install

# Copy the rest of the application code
# Don't need this in the local env, we're mounting the code in the compose file
# COPY . .

# Verify that node_modules exists and has content
RUN ls -la /app/node_modules

# Configure git to trust the /app directory
RUN git config --global --add safe.directory /app

# Don't try to open a browser
ENV BROWSER=none

# Expose the port the app runs on
EXPOSE 4000

# Define the command to run the app
CMD ["yarn", "start", "--host", "0.0.0.0", "--port", "4000"]
