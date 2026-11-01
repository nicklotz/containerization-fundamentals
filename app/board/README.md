# board

The board is a web page that lists the bags at the hub, like a baggage claim screen. It is plain HTML, CSS and JavaScript. nginx serves it.

## What the page does

- Every 3 seconds it requests `/api/bags?limit=25` and `/api/info` from the web server that served the page.
- It shows the 25 most recently updated bags, newest first.
- The footer shows which bag-api copy answered `/api/info`: its hostname, version and storage kind. With several bag-api replicas the hostname changes between requests. During a rolling update the version changes.
- If a request fails, a red banner says "API unreachable" and the table is dimmed. The page keeps trying every 3 seconds.

## Files

| File | Content |
|---|---|
| `html/index.html`, `html/board.js`, `html/board.css` | The page. It loads nothing from other sites. |
| `nginx/default.conf.template` | The nginx server configuration, with a placeholder for the bag-api address. |

## nginx configuration

The template is written for the `nginxinc/nginx-unprivileged` image. That image runs nginx as a non-root user and listens on port 8080.

- The files from `html/` belong in `/usr/share/nginx/html`.
- `nginx/default.conf.template` belongs in `/etc/nginx/templates/`.
- The environment variable `BAG_API_URL` holds the bag-api address, for example `http://bag-api:8000`.

When the container starts, the image runs `envsubst` on every `*.template` file in `/etc/nginx/templates/`. It replaces `${BAG_API_URL}` with the value of the environment variable and writes the result to `/etc/nginx/conf.d/default.conf`.

The server answers these paths:

| Path | Answer |
|---|---|
| `/` | The board page. |
| `/api/...` | Forwarded to bag-api with the same path and query string. |
| `/healthz` | `ok`, without calling bag-api. Use it for liveness and readiness probes. |

## Things to know

- Write `BAG_API_URL` without a trailing slash and without a path. With `http://bag-api:8000/`, nginx removes `/api/` from the path, and bag-api answers 404.
- If `BAG_API_URL` is not set, nginx does not start. The log shows `unknown "bag_api_url" variable`.
- nginx looks up the bag-api host name once, when it starts. If the name cannot be resolved at that moment, nginx exits with `host not found in upstream`. Start bag-api, or create its Kubernetes Service, before the board.
- The image only replaces variables that are set in the container environment. nginx variables such as `$host` therefore stay as they are. To replace only `BAG_API_URL`, also set `NGINX_ENVSUBST_FILTER=BAG_API_URL`.
