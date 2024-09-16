# Node version should always match the version in `ui/.nvmrc`
FROM node:18
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install
RUN ["git", "config", "--global", "--add", "safe.directory", "/app"]
ENV BROWSER=none
CMD ["yarn", "start", "--host", "0.0.0.0" , "--port", "4000"]
