FROM node:20-alpine

WORKDIR /app

# 依存関係をインストール
COPY package.json ./
RUN npm install

# アプリケーションコードをコピー
COPY . .

EXPOSE 20002

CMD ["npm", "run", "dev", "--", "--host"]
