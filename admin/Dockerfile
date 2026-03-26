FROM node:20-alpine AS base

WORKDIR /app
COPY package*.json ./

RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

EXPOSE 3001
CMD ["npm", "start", "--", "-p", "3001"]