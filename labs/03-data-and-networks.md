# Lab 03: Data, networks and health

**Goal:** Run bag-api with Postgres and the board on one Docker network, keep the data in a volume, and find faults in containers.

**Lecture:** L5

**Start:** Lab 02 finished, or run `~/containerization-fundamentals/scripts/catch-up.sh 03` on a fresh VM.

## Part 1: A user-defined network

1. Go to your working folder.

   ```bash
   cd ~/bagtrack
   ```

   <!-- test
   t_running registry
   t_running portainer
   t_image bag-api:0.1
   -->

2. Create a network named `lab`.

   ```bash
   docker network create lab
   ```

3. Connect the running registry to `lab`.

   ```bash
   docker network connect lab registry
   ```

4. List the networks.

   ```bash
   docker network ls
   ```

   `lab` is listed with the driver `bridge`.

   <!-- test
   docker network inspect lab -f '{{range .Containers}}{{.Name}} {{end}}' | t_contains registry
   -->

5. In Portainer, click **Networks**, then **lab**.

   <!-- shots:begin -->
   <img src="img/03-data-and-networks/0060-portainer_view-1.png" alt="Portainer: network lab, step 1 of 3" width="800">

   <img src="img/03-data-and-networks/0060-portainer_view-2.png" alt="Portainer: network lab, step 2 of 3" width="800">

   <img src="img/03-data-and-networks/0060-portainer_view-3.png" alt="Portainer: network lab, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: portainer_view network lab -->

   The container `registry` is connected to the network.

## Part 2: Postgres with a named volume

1. Create a volume for the database.

   ```bash
   docker volume create bagtrack-db
   ```

2. Start Postgres on `lab`, with the volume and a health check.

   ```bash
   docker run -d --name bagtrack-db --network lab --restart unless-stopped \
     -e POSTGRES_USER=bagtrack -e POSTGRES_PASSWORD=bagtrack-dev-pw -e POSTGRES_DB=bagtrack \
     -v bagtrack-db:/var/lib/postgresql/data \
     --health-cmd "pg_isready -U bagtrack -d bagtrack" --health-interval 5s \
     public.ecr.aws/docker/library/postgres:17
   ```

3. Run `docker ps` until the status of `bagtrack-db` ends with `(healthy)`.

   ```bash
   docker ps
   ```

   <!-- test
   t_healthy bagtrack-db 120
   -->

## Part 3: bag-api talks to Postgres by name

1. Start bag-api on `lab`, with the address of the database in `DATABASE_URL`.

   ```bash
   docker run -d --name bag-api --network lab -p 8000:8000 --restart unless-stopped \
     -e DATABASE_URL=postgresql://bagtrack:bagtrack-dev-pw@bagtrack-db:5432/bagtrack \
     bag-api:0.1
   ```

   <!-- test
   t_get http://localhost:8000/readyz | t_contains '"storage":"postgres"'
   -->

2. Ask bag-api whether it can reach its storage.

   ```bash
   curl -s localhost:8000/readyz | jq .
   ```

   ```text
   {
     "status": "ready",
     "storage": "postgres"
   }
   ```

3. Check in one bag, and keep its tag in the variable `TAG`.

   ```bash
   TAG=$(curl -s -X POST localhost:8000/api/bags -H 'Content-Type: application/json' \
     -d '{"flight":"FL101","passenger":"Rivera","destination":"SFO"}' | jq -r .tag)
   echo $TAG
   ```

   The tag looks like `BT962161`.

   <!-- test
   [[ "$TAG" =~ ^BT[0-9]{6}$ ]]
   -->

## Part 4: The data outlives the container

1. Remove the database container.

   ```bash
   docker rm -f bagtrack-db
   ```

2. Start Postgres again with the same command.

   ```bash
   docker run -d --name bagtrack-db --network lab --restart unless-stopped \
     -e POSTGRES_USER=bagtrack -e POSTGRES_PASSWORD=bagtrack-dev-pw -e POSTGRES_DB=bagtrack \
     -v bagtrack-db:/var/lib/postgresql/data \
     --health-cmd "pg_isready -U bagtrack -d bagtrack" --health-interval 5s \
     public.ecr.aws/docker/library/postgres:17
   ```

3. Run `docker ps` until `bagtrack-db` shows `(healthy)` again.

   ```bash
   docker ps
   ```

   <!-- test
   t_healthy bagtrack-db 120
   -->

4. Read the bag that you checked in.

   ```bash
   curl -s localhost:8000/api/bags/$TAG | jq .
   ```

   The bag of `Rivera` on `FL101` is still there.

   <!-- test
   t_get "http://localhost:8000/api/bags/$TAG" | t_contains Rivera
   -->

5. In Portainer, click **Volumes**, then **bagtrack-db**.

   <!-- shots:begin -->
   <img src="img/03-data-and-networks/0186-portainer_view-1.png" alt="Portainer: volume bagtrack-db, step 1 of 3" width="800">

   <img src="img/03-data-and-networks/0186-portainer_view-2.png" alt="Portainer: volume bagtrack-db, step 2 of 3" width="800">

   <img src="img/03-data-and-networks/0186-portainer_view-3.png" alt="Portainer: volume bagtrack-db, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: portainer_view volume bagtrack-db -->

## Part 5: Names on a user-defined network

1. Show the DNS settings of a container on `lab`.

   ```bash
   docker run --rm --network lab public.ecr.aws/docker/library/alpine:3.22 cat /etc/resolv.conf
   ```

   The name server is `127.0.0.11`, the DNS server that Docker runs for the network.

   <!-- test
   docker run --rm --network lab public.ecr.aws/docker/library/alpine:3.22 cat /etc/resolv.conf | t_contains 'nameserver 127.0.0.11'
   -->

2. Look up `bag-api` from a container on `lab`.

   ```bash
   docker run --rm --network lab public.ecr.aws/docker/library/alpine:3.22 getent hosts bag-api
   ```

   The answer is the IP address of bag-api, followed by its name.

   <!-- test
   ip=$(docker inspect -f '{{(index .NetworkSettings.Networks "lab").IPAddress}}' bag-api)
   docker run --rm --network lab public.ecr.aws/docker/library/alpine:3.22 getent hosts bag-api | t_contains "$ip"
   -->

3. Look up `bag-api` from a container on the default network.

   <!-- expect-fail -->
   ```bash
   docker run --rm public.ecr.aws/docker/library/alpine:3.22 getent hosts bag-api
   ```

   This time there is no answer.

## Part 6: The board with bind mounts

1. Start the board on `lab`, with its page and its nginx template mounted read-only from `~/bagtrack/board`.

   ```bash
   docker run -d --name board --network lab -p 8080:8080 \
     -e BAG_API_URL=http://bag-api:8000 \
     -v ~/bagtrack/board/html:/usr/share/nginx/html:ro \
     -v ~/bagtrack/board/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro \
     public.ecr.aws/nginx/nginx-unprivileged:1.29-alpine
   ```

   <!-- test
   t_get http://localhost:8080/healthz | t_contains ok
   t_get http://localhost:8080/api/info | t_contains '"storage":"postgres"'
   -->

2. Open http://localhost:8080 in the browser.

   <!-- shots:begin -->
   <img src="img/03-data-and-networks/0248-browser_open-1.png" alt="The page at http://localhost:8080" width="800">

   <!-- shots:end -->

   <!-- ui: browser_open http://localhost:8080 -->

   The board lists the bags, and its footer ends with `storage postgres`.

3. Change the heading of the page in the folder on the host.

   ```bash
   sed -i 's/<h1>Baggage claim/<h1>Baggage claim, carousel 3/' board/html/index.html
   ```

   <!-- test
   t_get http://localhost:8080/ | t_contains 'carousel 3'
   -->

4. Reload the board in the browser.

   <!-- shots:begin -->
   <img src="img/03-data-and-networks/0269-browser_open-1.png" alt="The page at http://localhost:8080" width="800">

   <!-- shots:end -->

   <!-- ui: browser_open http://localhost:8080 -->

   The heading now starts with `Baggage claim, carousel 3`, without a rebuild or a restart.

5. Undo the change.

   ```bash
   cp ~/containerization-fundamentals/app/board/html/index.html board/html/index.html
   ```

   <!-- test
   cmp board/html/index.html ~/containerization-fundamentals/app/board/html/index.html
   -->

## Part 7: Restart policies

1. Stop the main process of bag-api from inside the container.

   ```bash
   docker exec bag-api sh -c 'kill 1'
   ```

   <!-- test
   for i in $(seq 1 30); do [ "$(docker inspect -f '{{.RestartCount}}' bag-api)" -ge 1 ] && break; sleep 1; done
   t_eq "$(docker inspect -f '{{.RestartCount}}' bag-api)" 1 "restart count of bag-api"
   t_get http://localhost:8000/readyz >/dev/null
   -->

2. Read how many times Docker restarted the container.

   ```bash
   docker inspect -f '{{.RestartCount}}' bag-api
   ```

   The answer is `1` (run the command again if it still says `0`).

3. List the running containers.

   ```bash
   docker ps
   ```

   `bag-api` is `Up` again, for a shorter time than the other containers.

   <!-- test
   t_running bag-api
   t_get http://localhost:8080/api/info | t_contains '"storage":"postgres"'
   -->

## Part 8: Troubleshooting drill

1. List the last events of `bag-api`.

   ```bash
   docker events --since 30m --until 0s --filter container=bag-api | tail -5
   ```

   The last lines include `container die` and `container start`, from the restart in Part 7.

2. Start a second bag-api, `bag-api-bad`, with a wrong database password on host port 8001.

   ```bash
   docker run -d --name bag-api-bad --network lab -p 8001:8000 \
     -e DATABASE_URL=postgresql://bagtrack:wrong-pw@bagtrack-db:5432/bagtrack \
     bag-api:0.1
   ```

   <!-- test
   for i in $(seq 1 30); do code=$(curl -s -o /dev/null -w '%{http_code}' localhost:8001/readyz || true); [ "$code" = 503 ] && break; sleep 2; done
   t_eq "$code" 503 "readyz of bag-api-bad"
   -->

3. Ask `bag-api-bad` whether it is ready.

   ```bash
   curl -si localhost:8001/readyz
   ```

   The first line is `HTTP/1.1 503 Service Unavailable`, and the error says `password authentication failed`.

4. Ask `bag-api-bad` whether it is alive.

   ```bash
   curl -si localhost:8001/healthz | head -1
   ```

   The answer is `HTTP/1.1 200 OK`.

   <!-- test
   t_eq "$(curl -s -o /dev/null -w '%{http_code}' localhost:8001/healthz)" 200 "healthz of bag-api-bad"
   -->

5. Read the end of its log.

   ```bash
   docker logs bag-api-bad 2>&1 | tail
   ```

   A `WARNING` line says `password authentication failed`.

   <!-- test
   docker logs bag-api-bad 2>&1 | t_contains 'password authentication failed'
   -->

6. Show the environment of the container.

   ```bash
   docker inspect -f '{{json .Config.Env}}' bag-api-bad | jq .
   ```

   `DATABASE_URL` holds the wrong password, `wrong-pw`.

7. Remove the faulty container.

   ```bash
   docker rm -f bag-api-bad
   ```

8. Try to start another bag-api on host port 8000, which `bag-api` already uses.

   <!-- expect-fail -->
   ```bash
   docker run -d --rm --name bag-api-2 -p 8000:8000 bag-api:0.1
   ```

   Docker refuses with `port is already allocated`.

   <!-- test
   for i in 1 2 3 4 5; do docker inspect bag-api-2 >/dev/null 2>&1 || break; sleep 1; done
   if docker inspect bag-api-2 >/dev/null 2>&1; then echo "bag-api-2 still exists" >&2; exit 1; fi
   if docker inspect bag-api-bad >/dev/null 2>&1; then echo "bag-api-bad still exists" >&2; exit 1; fi
   t_running bag-api
   -->

## Check your work

1. List the containers on the network `lab`.

   ```bash
   docker network inspect lab -f '{{range .Containers}}{{.Name}} {{end}}'
   ```

   The names are `registry`, `bagtrack-db`, `bag-api` and `board`, in any order.

2. List the running containers with their status.

   ```bash
   docker ps --format '{{.Names}}: {{.Status}}'
   ```

   `bagtrack-db` is `(healthy)`, and `portainer` runs as well.

3. Ask the board which storage bag-api uses.

   ```bash
   curl -s localhost:8080/api/info | jq -r .storage
   ```

   The answer is `postgres`.

   <!-- test
   for c in registry bagtrack-db bag-api board; do
     docker network inspect lab -f '{{range .Containers}}{{.Name}} {{end}}' | t_contains "$c"
     t_running "$c"
   done
   t_running portainer
   t_healthy bagtrack-db 60
   t_eq "$(docker inspect -f '{{range .Mounts}}{{.Name}}{{end}}' bagtrack-db)" bagtrack-db "volume of bagtrack-db"
   t_eq "$(docker inspect -f '{{.Config.Image}}' bag-api)" bag-api:0.1 "image of bag-api"
   t_eq "$(docker port bag-api 8000/tcp | head -1)" 0.0.0.0:8000 "host port of bag-api"
   t_eq "$(docker inspect -f '{{len .Mounts}}' board)" 2 "bind mounts of board"
   t_eq "$(curl -fsS localhost:8080/api/info | jq -r .storage)" postgres "storage behind the board"
   -->

<!-- runner: stop -->

## Troubleshooting

| Problem | Fix |
|---|---|
| `network lab not found` | Create the network with `docker network create lab`. |
| `/readyz` answers `"not ready"` | Check with `docker ps` that `bagtrack-db` is `(healthy)`, then read `docker logs bag-api 2>&1 \| tail`. |
| `board` stops, and `docker logs board` shows `host not found in upstream "bag-api"` | Start `bag-api` on the network `lab` first, then run `docker start board`. |
| `docker logs board` shows `unknown "bag_api_url" variable` | Remove the board with `docker rm -f board`, and start it again with `-e BAG_API_URL=http://bag-api:8000`. |
| The board says `API unreachable` after bag-api restarted | Run `docker restart board`. nginx looks up the address of `bag-api` only when it starts. |
| `exec: "kill": executable file not found in $PATH` | The image has no `kill` program. Use `docker exec bag-api sh -c 'kill 1'`. |
| The bag from Part 3 is gone after Part 4 | Postgres started without the volume. Check that the command has `-v bagtrack-db:/var/lib/postgresql/data`. |
| `curl` for `/api/bags/$TAG` prints nothing | `TAG` is empty, for example in a new terminal. Find the tag of the bag of Rivera with `curl -s 'localhost:8000/api/bags?flight=FL101' \| jq .`, then set `TAG` to it. |

## Going further (optional)

- Run `docker exec -it bagtrack-db psql -U bagtrack -d bagtrack -c 'select tag, status from bags'` and find your bag.
- Start a second bag-api on `lab` with host port 8002 and the same `DATABASE_URL`, and check that both list the same bags.
- Run `docker volume inspect bagtrack-db`, then list its `Mountpoint` folder with `sudo ls`.
- Start an Alpine container with `--restart on-failure:3` that runs `sh -c 'exit 1'`, and read its `RestartCount`.
