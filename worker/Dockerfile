FROM docker.m.daocloud.io/library/golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN go mod tidy
RUN CGO_ENABLED=0 go build -o /out/jiaozi-worker .

FROM docker.m.daocloud.io/library/debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/jiaozi-worker /usr/local/bin/jiaozi-worker
RUN mkdir -p /data/outputs
ENTRYPOINT ["/usr/local/bin/jiaozi-worker"]
