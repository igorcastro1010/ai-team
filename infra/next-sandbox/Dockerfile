FROM node@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c
WORKDIR /opt/runtime
COPY scaffold/package.json scaffold/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY scaffold /opt/runner/scaffold
COPY run.mjs /opt/runner/run.mjs
USER 65532:65532
WORKDIR /work
CMD ["node", "/opt/runner/run.mjs"]
