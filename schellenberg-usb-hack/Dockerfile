# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM

########## FRONTEND
FROM node:20-alpine AS builder
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /build
COPY schellenberg-nuxt .
RUN pnpm install
RUN pnpm run build
FROM node:20-alpine AS production
WORKDIR /opt/schellenberg-nuxt

########## HOME ASSISTANT ADDON
FROM $BUILD_FROM

# Execute during the build of the image
ARG TEMPIO_VERSION BUILD_ARCH
RUN \
curl -sSLf -o /usr/bin/tempio \
"https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${BUILD_ARCH}"

RUN apk add --no-cache nginx uv nodejs

####### BACKEND
COPY schellenberghack_api /tmp/schellenberghack_api
WORKDIR /tmp/schellenberghack_api
RUN uv pip install --system --upgrade /tmp/schellenberghack_api
WORKDIR /

COPY rootfs /

COPY --from=builder /build/.output /opt/schellenberg-nuxt/.output

ENTRYPOINT [ "/init" ]