FROM node:18
WORKDIR /app
USER node
COPY package.json yarn.lock ./
RUN yarn install
COPY . .
RUN ["git", "config", "--global", "--add", "safe.directory", "/app"]
ENV BROWSER=none
CMD ["yarn", "start", "--host", "0.0.0.0" , "--port", "4000"]
