# compose/local/ui/Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app

# Install necessary packages
RUN apk add --no-cache python3 make g++ git

# Install a specific version of Yarn
# RUN npm install -g yarn@1.22.19

# Copy the entire project directory, including .git if it exists
COPY . .

# Install dependencies
RUN yarn install # --frozen-lockfile

# Build the project
RUN yarn build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# COPY ./compose/local/ui/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
