# Lab 06: Build, scan and publish with Harness Open Source

**Goal:** Build, test, scan and publish the three BagTrack images with a Harness Open Source pipeline that runs on every push.

**Lecture:** L9

**Start:** Lab 05 finished, or run `~/containerization-fundamentals/scripts/catch-up.sh 06` on a fresh VM.

## Part 1: Start Harness Open Source

1. Go to your working folder.

   ```bash
   cd ~/bagtrack
   ```

   <!-- test
   t_running registry
   t_running portainer
   for r in bag-api scanner board; do t_tag_in_registry "$r" 1.0; done
   grep -q 'nginx-unprivileged:1.27.0-alpine' ~/bagtrack/board/Dockerfile
   -->

2. Start Harness Open Source on the `lab` network.

   ```bash
   docker run -d --name harness --restart always --network lab \
     -p 3000:3000 -p 3022:3022 \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v harness-data:/data \
     -e GITNESS_URL_CONTAINER=http://harness:3000 \
     -e GITNESS_CI_CONTAINER_NETWORKS=lab \
     -e GITNESS_PRINCIPAL_ADMIN_EMAIL=admin@example.com \
     -e GITNESS_PRINCIPAL_ADMIN_PASSWORD=Harness-Lab-2026 \
     -e GITNESS_METRIC_ENABLED=false \
     harness/harness:3.3.0
   ```

   <!-- test
   for i in $(seq 1 90); do curl -fs localhost:3000/api/v1/system/health >/dev/null && exit 0; sleep 2; done
   echo "check failed: Harness does not answer on port 3000" >&2; docker logs --tail 20 harness >&2; exit 1
   -->

3. Open http://localhost:3000 in the browser, enter `admin` as the username and `Harness-Lab-2026` as the password, and click **Sign In**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0046-harness_login-1.png" alt="Sign in to Harness, step 1 of 3" width="800">

   <img src="img/06-harness-ci/0046-harness_login-2.png" alt="Sign in to Harness, step 2 of 3" width="800">

   <img src="img/06-harness-ci/0046-harness_login-3.png" alt="Sign in to Harness, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: harness_login -->

## Part 2: A project, a repository and a token

1. In Harness, click **Select project here**, then **New Project**, enter `bagtrack` as the name and click **Create Project**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0052-create_project-1.png" alt="Create the project, step 1 of 5" width="800">

   <img src="img/06-harness-ci/0052-create_project-2.png" alt="Create the project, step 2 of 5" width="800">

   <img src="img/06-harness-ci/0052-create_project-3.png" alt="Create the project, step 3 of 5" width="800">

   <img src="img/06-harness-ci/0052-create_project-4.png" alt="Create the project, step 4 of 5" width="800">

   <img src="img/06-harness-ci/0052-create_project-5.png" alt="Create the project, step 5 of 5" width="800">

   <!-- shots:end -->

   <!-- ui: create_project bagtrack -->

2. In the `bagtrack` project, click **New Repository**, enter `bagtrack` as the name, leave the README option unchecked and click **Create Repository**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0056-create_repo-1.png" alt="Create the repository, step 1 of 4" width="800">

   <img src="img/06-harness-ci/0056-create_repo-2.png" alt="Create the repository, step 2 of 4" width="800">

   <img src="img/06-harness-ci/0056-create_repo-3.png" alt="Create the repository, step 3 of 4" width="800">

   <img src="img/06-harness-ci/0056-create_repo-4.png" alt="Create the repository, step 4 of 4" width="800">

   <!-- shots:end -->

   <!-- ui: create_repo bagtrack bagtrack -->

   <!-- test
   h_api GET "/api/v1/repos/$(h_ref bagtrack/bagtrack)" | jq -e '.path == "bagtrack/bagtrack"' >/dev/null
   -->

3. Open http://localhost:3000/profile, click **New Token**, enter `git` as the name, choose an expiration of 30 days, click **Generate Token** and leave the dialog with the token open.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0064-create_token-1.png" alt="Create a token, step 1 of 6" width="800">

   <img src="img/06-harness-ci/0064-create_token-2.png" alt="Create a token, step 2 of 6" width="800">

   <img src="img/06-harness-ci/0064-create_token-3.png" alt="Create a token, step 3 of 6" width="800">

   <img src="img/06-harness-ci/0064-create_token-4.png" alt="Create a token, step 4 of 6" width="800">

   <img src="img/06-harness-ci/0064-create_token-5.png" alt="Create a token, step 5 of 6" width="800">

   <img src="img/06-harness-ci/0064-create_token-6.png" alt="Create a token, step 6 of 6" width="800">

   <!-- shots:end -->

   <!-- ui: create_token git -->

4. Tell git to store the token after the first push that uses it.

   ```bash
   git config --global credential.helper store
   ```

## Part 3: Push BagTrack to Harness

1. Set the name and email of your git commits.

   ```bash
   git config --global user.name "BagTrack Student"
   git config --global user.email student@example.com
   ```

2. Make `~/bagtrack` a git repository with the branch `main`.

   ```bash
   git init -b main
   ```

3. Create `~/bagtrack/.gitignore` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/.gitignore -->
   ```text
   __pycache__/
   *.pyc
   .pytest_cache/
   .venv/
   bag-api-sbom.json
   ```

4. Stage all files and list them.

   ```bash
   git add .
   git status --short
   ```

   No line names `bag-api-sbom.json`.

5. Commit the files.

   ```bash
   git commit -m "BagTrack services, Dockerfiles, Compose and ECS files"
   ```

6. Add the Harness repository as the remote `origin`.

   ```bash
   git remote add origin http://localhost:3000/git/bagtrack/bagtrack.git
   ```

7. Push the `main` branch, and when git asks, enter `admin` as the username and paste the token from the Harness dialog as the password.

   ```bash
   git push -u origin main
   ```

   The last line is `branch 'main' set up to track 'origin/main'.`

   <!-- test
   cd ~/bagtrack
   t_eq "$(git ls-remote origin refs/heads/main | cut -f1)" "$(git rev-parse HEAD)" "main on Harness"
   -->

8. Open http://localhost:3000/bagtrack/bagtrack to see the files in Harness.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0134-harness_view-1.png" alt="Harness" width="800">

   <!-- shots:end -->

   <!-- ui: harness_view /bagtrack/bagtrack -->

## Part 4: The pipeline and its trigger

1. Create `~/bagtrack/.harness/images.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/.harness/images.yaml -->
   ```yaml
   # Build, test, scan and publish the three BagTrack images.
   kind: pipeline
   spec:
     stages:
     - name: images
       type: ci
       spec:
         volumes:
         - name: docker-socket
           type: host
           spec:
             path: /var/run/docker.sock
         steps:
         - name: lint
           type: run
           spec:
             container: ghcr.io/hadolint/hadolint:v2.15.1-debian
             script: |
               hadolint --failure-threshold warning bag-api/Dockerfile scanner/Dockerfile board/Dockerfile
         - name: test-api
           type: run
           spec:
             container: public.ecr.aws/docker/library/python:3.13-slim
             script: |
               cd bag-api
               pip install --quiet --no-cache-dir -r requirements-dev.txt
               python -m pytest -q
         - name: test-scanner
           type: run
           spec:
             container: public.ecr.aws/docker/library/golang:1.26
             script: |
               cd scanner
               go vet ./...
               go test ./...
         - name: build
           type: run
           spec:
             container: public.ecr.aws/docker/library/docker:29-cli
             mount:
             - name: docker-socket
               path: /var/run/docker.sock
             script: |
               for svc in bag-api scanner board; do
                 docker build --build-arg APP_VERSION=1.0.${{ build.number }} -t localhost:5000/$svc:1.0.${{ build.number }} ./$svc
               done
         - name: scan
           type: run
           spec:
             container: public.ecr.aws/aquasecurity/trivy:0.76.1
             mount:
             - name: docker-socket
               path: /var/run/docker.sock
             script: |
               for svc in bag-api scanner board; do
                 trivy image --image-src docker --no-progress --severity CRITICAL --ignore-unfixed --exit-code 1 localhost:5000/$svc:1.0.${{ build.number }}
               done
         - name: publish
           type: run
           spec:
             container: public.ecr.aws/docker/library/docker:29-cli
             mount:
             - name: docker-socket
               path: /var/run/docker.sock
             script: |
               for svc in bag-api scanner board; do
                 docker push localhost:5000/$svc:1.0.${{ build.number }}
               done
   ```

   The `build`, `scan` and `publish` steps use the Docker engine of this machine through its socket, which gives the pipeline full control of that engine.

2. Commit the pipeline file.

   ```bash
   git add .harness/images.yaml
   git commit -m "Add the images pipeline"
   ```

3. Push the commit.

   ```bash
   git push
   ```

   <!-- test
   cd ~/bagtrack
   t_eq "$(git ls-remote origin refs/heads/main | cut -f1)" "$(git rev-parse HEAD)" "main on Harness"
   -->

4. Open http://localhost:3000/bagtrack/bagtrack/pipelines, click **New Pipeline**, enter `images` as the name and `.harness/images.yaml` as the YAML path, and click **Create**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0234-create_pipeline-1.png" alt="Create the pipeline, step 1 of 5" width="800">

   <img src="img/06-harness-ci/0234-create_pipeline-2.png" alt="Create the pipeline, step 2 of 5" width="800">

   <img src="img/06-harness-ci/0234-create_pipeline-3.png" alt="Create the pipeline, step 3 of 5" width="800">

   <img src="img/06-harness-ci/0234-create_pipeline-4.png" alt="Create the pipeline, step 4 of 5" width="800">

   <img src="img/06-harness-ci/0234-create_pipeline-5.png" alt="Create the pipeline, step 5 of 5" width="800">

   <!-- shots:end -->

   <!-- ui: create_pipeline bagtrack/bagtrack images .harness/images.yaml -->

5. Open http://localhost:3000/bagtrack/bagtrack/pipelines/images, click **Pipeline Settings**, **Triggers** and **New Trigger**, enter `on-push` as the name, select only **Branch Updated** and click **Create**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0238-add_trigger-1.png" alt="Add the trigger, step 1 of 6" width="800">

   <img src="img/06-harness-ci/0238-add_trigger-2.png" alt="Add the trigger, step 2 of 6" width="800">

   <img src="img/06-harness-ci/0238-add_trigger-3.png" alt="Add the trigger, step 3 of 6" width="800">

   <img src="img/06-harness-ci/0238-add_trigger-4.png" alt="Add the trigger, step 4 of 6" width="800">

   <img src="img/06-harness-ci/0238-add_trigger-5.png" alt="Add the trigger, step 5 of 6" width="800">

   <img src="img/06-harness-ci/0238-add_trigger-6.png" alt="Add the trigger, step 6 of 6" width="800">

   <!-- shots:end -->

   <!-- ui: add_trigger bagtrack/bagtrack images on-push branch_updated -->

## Part 5: Run the pipeline

1. Open http://localhost:3000/bagtrack/bagtrack/pipelines/images, click **Run**, then **Run pipeline**.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0244-run_pipeline-1.png" alt="Run the pipeline, step 1 of 3" width="800">

   <img src="img/06-harness-ci/0244-run_pipeline-2.png" alt="Run the pipeline, step 2 of 3" width="800">

   <img src="img/06-harness-ci/0244-run_pipeline-3.png" alt="Run the pipeline, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: run_pipeline bagtrack/bagtrack images -->

   The run fails at the `scan` step.

   <!-- test
   cd ~/bagtrack
   h_wait bagtrack/bagtrack images failure
   h_log bagtrack/bagtrack images scan | t_contains "localhost:5000/board:1.0."
   -->

2. When the run has stopped, click the **scan** step to read its log.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0256-view_execution-1.png" alt="The pipeline run, step 1 of 3" width="800">

   <img src="img/06-harness-ci/0256-view_execution-2.png" alt="The pipeline run, step 2 of 3" width="800">

   <img src="img/06-harness-ci/0256-view_execution-3.png" alt="The pipeline run, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: view_execution bagtrack/bagtrack images -->

   The log lists CRITICAL vulnerabilities with a fixed version in the image `localhost:5000/board:1.0.<n>`, where `<n>` is the run number.

3. List the board tags in the registry.

   ```bash
   curl -s localhost:5000/v2/board/tags/list
   ```

   The output is `{"name":"board","tags":["1.0"]}`, because `publish` did not run after the failed scan.

   <!-- test
   if curl -fsS localhost:5000/v2/board/tags/list | jq -e '[.tags[] | select(startswith("1.0."))] | length > 0' >/dev/null; then
     echo "check failed: the registry has a board 1.0.<n> tag although the scan failed" >&2; exit 1
   fi
   -->

## Part 6: Fix the board image

1. Replace `~/bagtrack/board/Dockerfile` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/board/Dockerfile -->
   ```dockerfile
   FROM public.ecr.aws/nginx/nginx-unprivileged:1.29-alpine
   USER 0
   RUN apk upgrade --no-cache
   USER 101
   COPY html/ /usr/share/nginx/html/
   COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
   ENV BAG_API_URL=http://bag-api:8000
   EXPOSE 8080
   ```

   The file moves to the current base tag `1.29-alpine` and installs the fixed Alpine packages with `apk upgrade` as root (`USER 0`), then switches back to the nginx user (`USER 101`).

2. Commit the change.

   ```bash
   git add board/Dockerfile
   git commit -m "Board: current base image and upgraded packages"
   ```

3. Push the commit, which starts a new run through the trigger.

   ```bash
   git push
   ```

   <!-- test
   cd ~/bagtrack
   h_wait bagtrack/bagtrack images success
   -->

4. Open http://localhost:3000/bagtrack/bagtrack/pipelines/images and click the newest run.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0312-view_execution-1.png" alt="The pipeline run, step 1 of 3" width="800">

   <img src="img/06-harness-ci/0312-view_execution-2.png" alt="The pipeline run, step 2 of 3" width="800">

   <img src="img/06-harness-ci/0312-view_execution-3.png" alt="The pipeline run, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: view_execution bagtrack/bagtrack images -->

   Every step passed, including `scan` and `publish`.

## Part 7: The published images

1. List the tags of the three repositories in the registry.

   ```bash
   for repo in bag-api scanner board; do curl -s localhost:5000/v2/$repo/tags/list | jq -c .; done
   ```

   Each list now has a `1.0.<n>` tag, where `<n>` is the number of the run that passed.

   <!-- test
   for r in bag-api scanner board; do
     curl -fsS "localhost:5000/v2/$r/tags/list" | jq -e '[.tags[] | select(test("^1\\.0\\.[0-9]+$"))] | length > 0' >/dev/null \
       || { echo "check failed: no 1.0.<n> tag for $r" >&2; exit 1; }
   done
   -->

2. Keep the newest pipeline tag of the board in the variable `TAG`.

   ```bash
   TAG=$(curl -s localhost:5000/v2/board/tags/list | jq -r '.tags[]' | grep '^1\.0\.' | sort -V | tail -1)
   echo "$TAG"
   ```

3. Pull the board image that the pipeline published.

   ```bash
   docker pull localhost:5000/board:$TAG
   ```

4. Run the image once to print its nginx version.

   ```bash
   docker run --rm localhost:5000/board:$TAG nginx -v
   ```

   The last line starts with `nginx version: nginx/1.29.`

   <!-- test
   docker run --rm "localhost:5000/board:$TAG" nginx -v 2>&1 | t_contains "nginx/1.29."
   -->

## Check your work

1. Check that Harness runs.

   ```bash
   docker ps --filter name=harness --format '{{.Names}} {{.Status}}'
   ```

   The output starts with `harness Up`.

2. Check that your working folder matches the repository in Harness.

   ```bash
   git status -sb
   ```

   The output is `## main...origin/main`.

3. Open http://localhost:3000/bagtrack/bagtrack/pipelines/images.

   <!-- shots:begin -->
   <img src="img/06-harness-ci/0378-harness_view-1.png" alt="Harness" width="800">

   <!-- shots:end -->

   <!-- ui: harness_view /bagtrack/bagtrack/pipelines/images -->

   The newest run passed.

<!-- test
t_running harness
cd ~/bagtrack
t_eq "$(git ls-remote origin refs/heads/main | cut -f1)" "$(git rev-parse HEAD)" "main on Harness"
t_eq "$(git status --porcelain | wc -l)" "0" "uncommitted changes in ~/bagtrack"
for r in bag-api scanner board; do
  curl -fsS "localhost:5000/v2/$r/tags/list" | jq -e '[.tags[] | select(test("^1\\.0\\.[0-9]+$"))] | length > 0' >/dev/null \
    || { echo "check failed: no 1.0.<n> tag for $r" >&2; exit 1; }
done
h_wait bagtrack/bagtrack images success
-->

<!-- runner: stop -->

## Troubleshooting

| Problem | Fix |
|---|---|
| http://localhost:3000 does not load | Harness is still starting. Reload the page after a few seconds. |
| You closed the token dialog before the first push | Create a new token on http://localhost:3000/profile. |
| `fatal: Authentication failed for 'http://localhost:3000/git/bagtrack/bagtrack.git/'` | The token was wrong. Create a new token, run `git push -u origin main` again and paste the new token. |
| `git push` is rejected with `(fetch first)` | The repository was created with a README. Run `git pull --rebase origin main`, then push again. |
| The run fails at the `clone` step | Harness was started without `GITNESS_URL_CONTAINER` or `GITNESS_CI_CONTAINER_NETWORKS`. Run `docker rm -f harness`, then the command of Part 1 again; the `harness-data` volume keeps your project. |
| `scan` fails on `bag-api` or `scanner` | A base image has a new fixable vulnerability. Pull it again with `docker pull public.ecr.aws/docker/library/python:3.13-slim` or `docker pull public.ecr.aws/docker/library/golang:1.26`, then run the pipeline again. |
| A push does not start a run | Open **Pipeline Settings**, then **Triggers**, and check that `on-push` has **Branch Updated** selected. |

## Going further (optional)

- Make one assertion in `bag-api/tests/test_checkpoints.py` fail, push, read the log of `test-api`, then undo the change and push again.
- Add `HIGH` to the `--severity` option of the `scan` step, push, see which image fails, then undo the change and push again.
