FROM public.ecr.aws/docker/library/golang:1.26 AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/scanner .

FROM scratch
ARG APP_VERSION=1.0
ENV APP_VERSION=$APP_VERSION
COPY --from=build /out/scanner /scanner
USER 65532:65532
ENTRYPOINT ["/scanner"]
