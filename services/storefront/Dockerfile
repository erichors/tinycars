FROM node:22-slim
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev && npm cache clean --force
COPY server.js .
COPY public ./public
EXPOSE 8080
CMD ["node", "server.js"]
