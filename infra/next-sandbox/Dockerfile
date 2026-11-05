FROM node@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c
WORKDIR /opt/runtime
COPY scaffold/package.json scaffold/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY browser/package.json browser/package-lock.json /opt/browser/
RUN cd /opt/browser && npm ci --ignore-scripts --no-audit --no-fund
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
RUN node /opt/browser/node_modules/playwright/cli.js install --with-deps --only-shell chromium \
    && chmod -R a+rX /opt/browser /opt/browsers \
    && rm -rf /var/lib/apt/lists/*
ENV TMPDIR=/work/tmp
COPY scaffold /opt/runner/scaffold
COPY run.mjs read-html.mjs browser-checks.mjs /opt/runner/
USER 65532:65532
WORKDIR /work
CMD ["node", "/opt/runner/run.mjs"]
