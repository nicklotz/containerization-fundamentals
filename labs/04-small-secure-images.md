# Lab 04: Smaller, safer images

**Goal:** Build a small multi-stage image, run bag-api as a non-root user with fewer privileges, and scan images with Trivy.

**Lecture:** L6 and L7

**Start:** Lab 03 finished, or run `~/containerization-fundamentals/scripts/catch-up.sh 04` on a fresh VM.

## Part 1: Install Trivy

1. Open a terminal and go to the `/tmp` folder, where the downloads go.

   ```bash
   cd /tmp
   ```

   <!-- test
   for c in registry portainer bagtrack-db bag-api board; do t_running "$c"; done
   docker network inspect lab -f '{{range .Containers}}{{.Name}} {{end}}' | t_contains bag-api
   test -f ~/bagtrack/bag-api/Dockerfile
   -->

2. Download the Trivy 0.76.1 package and the checksum file of its release.

   ```bash
   curl -fsSLO https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.deb
   curl -fsSLO https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_checksums.txt
   ```

3. Check the package against its line in the checksum file.

   ```bash
   grep trivy_0.76.1_Linux-64bit.deb trivy_0.76.1_checksums.txt | sha256sum --check
   ```

   The output is `trivy_0.76.1_Linux-64bit.deb: OK`.

4. Update the package lists.

   ```bash
   sudo apt-get update
   ```

5. Install the package.

   ```bash
   sudo apt-get -o DPkg::Lock::Timeout=300 install -y ./trivy_0.76.1_Linux-64bit.deb
   ```

6. Check the version.

   ```bash
   trivy --version
   ```

   The first line is `Version: 0.76.1`.

   <!-- test
   trivy --version | t_contains "Version: 0.76.1"
   -->

## Part 2: A multi-stage build for the scanner

1. Go to your working folder.

   ```bash
   cd ~/bagtrack
   ```

2. Create `~/bagtrack/scanner/Dockerfile` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/scanner/Dockerfile -->
   ```dockerfile
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
   ```

3. Build the image.

   ```bash
   docker build -t scanner:1.0 scanner
   ```

4. Build only the first stage, under its own tag (`--target` stops the build after the named stage).

   ```bash
   docker build --target build -t scanner:build-stage scanner
   ```

5. Compare the sizes of the two images.

   ```bash
   docker image ls scanner
   ```

   `scanner:1.0` uses about 10 MB and `scanner:build-stage` more than 1 GB.

   <!-- test
   t_image scanner:build-stage
   size=$(docker image inspect -f '{{.Size}}' scanner:1.0)
   [ "$size" -lt 30000000 ] || { echo "check failed: scanner:1.0 is $size bytes" >&2; exit 1; }
   -->

6. Run the scanner on the `lab` network.

   ```bash
   docker run -d --name scanner --network lab -e API_URL=http://bag-api:8000 scanner:1.0
   ```

   <!-- test
   t_running scanner
   for i in $(seq 1 30); do docker logs scanner 2>&1 | grep -qE ' -> |checked in for' && exit 0; sleep 1; done
   echo "check failed: the scanner logged no scan" >&2; docker logs --tail 5 scanner >&2; exit 1
   -->

7. Read its last log lines.

   ```bash
   docker logs --tail 3 scanner
   ```

   The lines show bags that move to their next checkpoint, such as `sorted -> loaded`, and new bags that are checked in.

8. Open http://localhost:8080 in the browser.

   <!-- shots:begin -->
   <img src="img/04-small-secure-images/0141-browser_open-1.png" alt="The page at http://localhost:8080" width="800">

   <!-- shots:end -->

   <!-- ui: browser_open http://localhost:8080 -->

   The board shows the bags moving between checkpoints.

## Part 3: Base images compared

<!-- catchup: skip-start -->

1. Pull the full and the Alpine variants of the Python 3.13 image.

   ```bash
   docker pull public.ecr.aws/docker/library/python:3.13
   docker pull public.ecr.aws/docker/library/python:3.13-alpine
   ```

2. Compare the sizes of the three Python 3.13 images.

   ```bash
   docker image ls public.ecr.aws/docker/library/python
   ```

   `3.13` uses about 1.6 GB, `3.13-slim` about 180 MB and `3.13-alpine` about 70 MB.

   <!-- test
   t_image public.ecr.aws/docker/library/python:3.13
   t_image public.ecr.aws/docker/library/python:3.13-alpine
   -->

3. Count the HIGH and CRITICAL vulnerabilities in the full image.

   ```bash
   trivy image --quiet --severity HIGH,CRITICAL --format json \
     public.ecr.aws/docker/library/python:3.13 | jq '[.Results[]?.Vulnerabilities[]?] | length'
   ```

   The count is in the hundreds.

4. Count them in the slim image.

   ```bash
   trivy image --quiet --severity HIGH,CRITICAL --format json \
     public.ecr.aws/docker/library/python:3.13-slim | jq '[.Results[]?.Vulnerabilities[]?] | length'
   ```

   The slim image has far fewer.

5. In Portainer, click **Images**, type `python` in the search box, and compare the **Size** column of the three Python images.

   <!-- shots:begin -->
   <img src="img/04-small-secure-images/0198-portainer_view-1.png" alt="Portainer: images python, step 1 of 3" width="800">

   <img src="img/04-small-secure-images/0198-portainer_view-2.png" alt="Portainer: images python, step 2 of 3" width="800">

   <img src="img/04-small-secure-images/0198-portainer_view-3.png" alt="Portainer: images python, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: portainer_view images python -->

<!-- catchup: skip-end -->

## Part 4: A non-root bag-api

1. Replace `~/bagtrack/bag-api/Dockerfile` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/bag-api/Dockerfile -->
   ```dockerfile
   FROM public.ecr.aws/docker/library/python:3.13-slim
   RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin bagtrack
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY bagtrack ./bagtrack
   ARG APP_VERSION=1.0
   ENV APP_VERSION=$APP_VERSION PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
   USER 10001
   EXPOSE 8000
   HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
     CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
   CMD ["uvicorn", "bagtrack.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. Build version 1.0 of the image.

   ```bash
   docker build -t bag-api:1.0 bag-api
   ```

3. Compare it with version 0.1.

   ```bash
   docker image ls bag-api
   ```

   The two sizes are within a few MB of each other.

4. Check which user the image runs as.

   ```bash
   docker run --rm --entrypoint id bag-api:1.0
   ```

   The output is `uid=10001(bagtrack) gid=10001(bagtrack) groups=10001(bagtrack)`.

   <!-- test
   docker run --rm --entrypoint id bag-api:1.0 | t_contains "uid=10001(bagtrack)"
   -->

5. Remove the bag-api container from Lab 03.

   ```bash
   docker rm -f bag-api
   ```

6. Start bag-api 1.0 with a read-only file system, no Linux capabilities and no privilege escalation.

   ```bash
   docker run -d --name bag-api --network lab -p 8000:8000 --restart unless-stopped \
     --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
     -e DATABASE_URL=postgresql://bagtrack:bagtrack-dev-pw@bagtrack-db:5432/bagtrack \
     bag-api:1.0
   ```

7. Run this command until the status of bag-api ends with `(healthy)`.

   ```bash
   docker ps --filter name=bag-api
   ```

   <!-- test
   t_healthy bag-api 60
   t_get http://localhost:8000/api/info | jq -e '.version == "1.0"' >/dev/null
   -->

8. Restart the board so that it connects to the new bag-api container.

   ```bash
   docker restart board
   ```

   The footer of the board now shows version `1.0`.

   <!-- test
   t_get http://localhost:8080/api/info | jq -e '.version == "1.0"' >/dev/null
   -->

9. In Portainer, click **Containers**, then **bag-api**, then **Inspect**, and find `"ReadonlyRootfs": true` and `"CapDrop"`.

   <!-- shots:begin -->
   <img src="img/04-small-secure-images/0302-portainer_view-1.png" alt="Portainer: container-inspect bag-api, step 1 of 4" width="800">

   <img src="img/04-small-secure-images/0302-portainer_view-2.png" alt="Portainer: container-inspect bag-api, step 2 of 4" width="800">

   <img src="img/04-small-secure-images/0302-portainer_view-3.png" alt="Portainer: container-inspect bag-api, step 3 of 4" width="800">

   <img src="img/04-small-secure-images/0302-portainer_view-4.png" alt="Portainer: container-inspect bag-api, step 4 of 4" width="800">

   <!-- shots:end -->

   <!-- ui: portainer_view container-inspect bag-api -->

## Part 5: Why root in a container matters

1. Run an Alpine container that mounts the host's `/etc` folder and creates a file in it.

   ```bash
   docker run --rm -v /etc:/host-etc public.ecr.aws/docker/library/alpine:3.22 \
     sh -c 'id && touch /host-etc/written-by-a-container'
   ```

   The output starts with `uid=0(root) gid=0(root)`.

2. Look at the new file on the host.

   ```bash
   ls -l /etc/written-by-a-container
   ```

   The file belongs to `root`.

3. Delete the file.

   ```bash
   sudo rm /etc/written-by-a-container
   ```

4. Try the same as user 10001.

   <!-- expect-fail -->
   ```bash
   docker run --rm --user 10001 -v /etc:/host-etc public.ecr.aws/docker/library/alpine:3.22 \
     touch /host-etc/written-by-a-container
   ```

   The output is `touch: /host-etc/written-by-a-container: Permission denied`.

   <!-- test
   test ! -e /etc/written-by-a-container
   -->

## Part 6: Scan and SBOM

<!-- catchup: skip-start -->

1. Scan bag-api 1.0 for HIGH and CRITICAL vulnerabilities that have a fixed version.

   ```bash
   trivy image --severity HIGH,CRITICAL --ignore-unfixed bag-api:1.0
   ```

   The **Fixed Version** column names the package version that fixes each finding.

2. Write an SBOM of the image in CycloneDX format.

   ```bash
   trivy image --format cyclonedx --output ~/bagtrack/bag-api-sbom.json bag-api:1.0
   ```

3. Count the components in the SBOM.

   ```bash
   jq '.components | length' ~/bagtrack/bag-api-sbom.json
   ```

   The count is more than 100.

   <!-- test
   test "$(jq '.components | length' ~/bagtrack/bag-api-sbom.json)" -gt 100
   -->

<!-- catchup: skip-end -->

## Part 7: Code challenge

1. Copy the challenge to your home folder.

   ```bash
   cp -r ~/containerization-fundamentals/challenge ~/challenge
   ```

2. Open the challenge folder in VS Code and read the task in `README.md`.

   <!-- skip -->
   ```bash
   code ~/challenge
   ```

3. Write `~/challenge/gate-display/Dockerfile` and `~/challenge/gate-display/.dockerignore` so that the image meets every requirement in the README.

   <details>
   <summary>Show a solution</summary>

   <!-- file: ~/challenge/gate-display/Dockerfile -->
   ```dockerfile
   FROM public.ecr.aws/docker/library/python:3.13-slim
   RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin gates
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY app.py gates.json ./
   USER 10001
   EXPOSE 8000
   HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
     CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]
   CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--no-control-socket", "app:app"]
   ```

   <!-- file: ~/challenge/gate-display/.dockerignore -->
   ```text
   tests/
   .venv/
   __pycache__/
   *.pyc
   .pytest_cache/
   Dockerfile
   .dockerignore
   ```

   </details>

4. Build the image.

   <!-- catchup: skip -->
   ```bash
   docker build -t gate-display:challenge ~/challenge/gate-display
   ```

5. Grade the image.

   <!-- catchup: skip -->
   ```bash
   ~/challenge/check.sh
   ```

   The last line is `Summary: 8 passed, 0 failed, 0 skipped`.

## Part 8: Publish 1.0

1. Tag both images for the local registry.

   ```bash
   docker tag bag-api:1.0 localhost:5000/bag-api:1.0
   docker tag scanner:1.0 localhost:5000/scanner:1.0
   ```

2. Push both images.

   ```bash
   docker push localhost:5000/bag-api:1.0
   docker push localhost:5000/scanner:1.0
   ```

3. List the repositories in the registry.

   ```bash
   curl -s localhost:5000/v2/_catalog
   ```

   The output is `{"repositories":["bag-api","scanner"]}`.

   <!-- test
   t_tag_in_registry bag-api 1.0
   t_tag_in_registry scanner 1.0
   -->

## Check your work

1. List the running containers with their images and status.

   ```bash
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
   ```

   `bag-api` runs `bag-api:1.0` and is healthy, and `scanner`, `board`, `bagtrack-db`, `registry` and `portainer` are up.

2. Check the user and the security settings of bag-api.

   ```bash
   docker inspect -f '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}}' bag-api
   ```

   The output is `10001 true [ALL]`.

3. List the tags of bag-api in the registry.

   ```bash
   curl -s localhost:5000/v2/bag-api/tags/list
   ```

   The output is `{"name":"bag-api","tags":["0.1","1.0"]}`.

<!-- test
for c in bagtrack-db bag-api board scanner registry portainer; do t_running "$c"; done
t_healthy bag-api 60
t_eq "$(docker inspect -f '{{.Config.Image}}' bag-api)" "bag-api:1.0" "image of bag-api"
t_eq "$(docker inspect -f '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}}' bag-api)" "10001 true [ALL]" "settings of bag-api"
for c in bagtrack-db bag-api board scanner; do
  docker inspect -f '{{json .NetworkSettings.Networks}}' "$c" | jq -e 'has("lab")' >/dev/null \
    || { echo "check failed: $c is not on the lab network" >&2; exit 1; }
done
t_tag_in_registry bag-api 1.0
t_tag_in_registry scanner 1.0
command -v trivy >/dev/null
test -d ~/challenge/gate-display
-->

<!-- runner: stop -->

## Troubleshooting

| Problem | Fix |
|---|---|
| `sha256sum` prints `FAILED` and `WARNING: 1 computed checksum did NOT match` | The download is damaged. Delete `/tmp/trivy_0.76.1_Linux-64bit.deb` and download it again. |
| The scanner log shows `dial tcp: lookup bag-api` and `no such host` | The scanner is not on the `lab` network. Run `docker rm -f scanner`, then start it again with `--network lab`. |
| `Conflict. The container name "/bag-api" is already in use` | Remove the old container with `docker rm -f bag-api`, then run the command again. |
| bag-api stays at `(health: starting)` or turns `(unhealthy)` | Read the health check results with `docker inspect -f '{{json .State.Health}}' bag-api \| jq` and the log with `docker logs bag-api`. |
| The board shows **API unreachable** | Restart it with `docker restart board`. |
| `check.sh` prints `FAIL  no tests in the image` | Add `tests/` to `~/challenge/gate-display/.dockerignore` and build the image again. |
| `check.sh` prints `FAIL  health status: "starting"` | Give the `HEALTHCHECK` a shorter interval, for example `--interval=10s`, and build the image again. |

## Going further (optional)

- Scan `public.ecr.aws/docker/library/python:3.13-alpine` the same way as in Part 3 and compare the count with the slim image.
- Run `docker exec bag-api touch /app/test` and read the error.
- Run `docker run --rm --network lab scanner:1.0 report` to print the number of bags at each checkpoint.
- List the package names in the SBOM with `jq -r '.components[].name' ~/bagtrack/bag-api-sbom.json | sort | head -20`.
