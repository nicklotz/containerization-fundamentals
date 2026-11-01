# scanner

scanner simulates the baggage scanners at the hub. It is a small Go program that uses only the standard library. It calls bag-api over HTTP.

## What it does

`scanner` or `scanner run` does one action every `SCAN_INTERVAL`. Each action starts with `GET /api/bags?limit=200`, which returns the 200 most recently updated bags. Then:

- If fewer than 8 bags are still moving (not claimed), it checks in a new bag with a random flight and passenger.
- Otherwise it checks in a new bag one time in seven. The other times it picks a random bag that is not claimed and scans it at its next checkpoint.

It logs one line per action:

```
2026/11/01 10:10:16 scanner sc-7f3a: starting version dev, API http://bag-api:8000, interval 3s, health on :8081
2026/11/01 10:10:19 scanner sc-7f3a: BT104233 sorted -> loaded
2026/11/01 10:10:22 scanner sc-7f3a: BT518920 checked in for FL303 to BOS
```

If bag-api cannot be reached, scanner logs the error and tries again at the next interval. It does not exit.

scanner stops on SIGTERM (sent by `docker stop` and Kubernetes) and on SIGINT (Ctrl+C). It logs a line before it exits.

`scanner report` prints the number of bags at each checkpoint and exits:

```
CHECKPOINT     BAGS
checked_in        2
security          2
sorted            3
loaded            2
unloaded          1
claimed           2
total            12
```

It exits with code 1 and an error message if bag-api cannot be reached.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `API_URL` | `http://bag-api:8000` | Address of bag-api. |
| `SCAN_INTERVAL` | `3s` | Time between two actions, as a Go duration such as `500ms`, `3s` or `1m`. |
| `SCANNER_ID` | the hostname | Name in the log lines and in the scan records. In a container the hostname is the container ID. In Kubernetes it is the pod name. |
| `APP_VERSION` | `dev` | Version in the start line. |
| `HEALTH_ADDR` | `:8081` | Address of `GET /healthz`, which answers `ok`. |

`/healthz` does not call bag-api. If bag-api is down, restarting the scanner would not fix anything.

## Build and test

You need Go 1.24 or later.

```bash
go vet ./...
go test ./...
CGO_ENABLED=0 go build -o scanner .
```

With `CGO_ENABLED=0` the binary is statically linked and does not need a C library or a shell. It only uses plain HTTP, so it does not need CA certificates either. It can run in an image built `FROM scratch`.

## Run it on your machine

With bag-api listening on port 8000:

```bash
API_URL=http://localhost:8000 SCAN_INTERVAL=1s go run .
API_URL=http://localhost:8000 go run . report
```

## Connection reuse

Go's HTTP client keeps its connection to bag-api open between requests. With several bag-api replicas behind one address, each scanner usually keeps talking to the same replica.
