# Lab 07: A cluster and its first Pods

**Goal:** Create a three-node Kubernetes cluster and run bag-api in a Pod with probes, a ConfigMap and a Secret.

**Lecture:** L10 and L11

**Start:** Lab 06 finished, or run `~/containerization-fundamentals/scripts/catch-up.sh 07` on a fresh VM.

## Part 1: Install the tools

1. Go to your working folder.

   ```bash
   cd ~/bagtrack
   ```

2. Add the keyring of the Kubernetes package repository.

   ```bash
   curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key \
     | sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
   ```

3. Add the package repository for kubectl 1.36.

   ```bash
   echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.36/deb/ /' \
     | sudo tee /etc/apt/sources.list.d/kubernetes.list
   ```

4. Install kubectl.

   ```bash
   sudo apt-get update
   sudo apt-get -o DPkg::Lock::Timeout=300 install -y kubectl
   ```

5. Check the kubectl version.

   ```bash
   kubectl version --client
   ```

   The first line starts with `Client Version: v1.36`.

   <!-- test
   kubectl version --client | t_contains "Client Version: v1.36." "kubectl version"
   -->

6. Install the k3d 5.9.0 binary in `/usr/local/bin`.

   ```bash
   curl -fsSLo /tmp/k3d https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64
   sudo install -m 0755 /tmp/k3d /usr/local/bin/k3d
   ```

7. Check the k3d version.

   ```bash
   k3d version
   ```

   The first line is `k3d version v5.9.0`.

   <!-- test
   k3d version | t_contains "k3d version v5.9.0" "k3d version"
   -->

8. Download the Headlamp 0.46.0 package.

   ```bash
   curl -fsSLo /tmp/headlamp_0.46.0-1_amd64.deb \
     https://github.com/kubernetes-sigs/headlamp/releases/download/v0.46.0/headlamp_0.46.0-1_amd64.deb
   ```

9. Install Headlamp and the sound library that it needs.

   ```bash
   sudo apt-get -o DPkg::Lock::Timeout=300 install -y /tmp/headlamp_0.46.0-1_amd64.deb libasound2t64
   ```

   The output includes `Setting up headlamp (0.46.0-1)`.

   <!-- test
   dpkg -s headlamp | t_contains "Version: 0.46.0" "Headlamp package"
   -->

## Part 2: Create the cluster

1. Create the folder for the Kubernetes files.

   ```bash
   mkdir -p k8s
   ```

2. Create `~/bagtrack/k8s/registries.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/registries.yaml -->
   ```yaml
   mirrors:
     "localhost:5000":
       endpoint:
         - http://registry:5000
   ```

   With this file, the cluster nodes pull `localhost:5000/...` images from the `registry` container.

3. Create the cluster `hub`, with one server node and two agent nodes on the `lab` network.

   ```bash
   k3d cluster create hub --image rancher/k3s:v1.36.5-k3s1 \
     --network lab --agents 2 --api-port 6550 \
     -p "8081:80@loadbalancer" -p "30080:30080@loadbalancer" \
     --k3s-arg "--disable=traefik@server:0" \
     --registry-config ~/bagtrack/k8s/registries.yaml
   ```

   Near the end, the output says `Cluster 'hub' created successfully!`.

   <!-- test
   kubectl wait --for=condition=Ready node --all --timeout=180s
   t_eq "$(kubectl get nodes --no-headers | wc -l)" 3 "number of nodes"
   t_eq "$(kubectl config current-context)" k3d-hub "kubectl context"
   -->

4. List the nodes.

   ```bash
   kubectl get nodes
   ```

   `k3d-hub-server-0`, `k3d-hub-agent-0` and `k3d-hub-agent-1` show `Ready` (run the command again if one shows `NotReady`).

5. Start **Headlamp** from the applications menu, or run this command in a second terminal.

   <!-- skip -->

   ```bash
   headlamp &
   ```

6. In Headlamp, click **k3d-hub** in the list of clusters.

   <!-- shots:begin -->
   <img src="img/07-pods/0144-headlamp_view-1.png" alt="Headlamp: cluster" width="800">

   <!-- shots:end -->

   <!-- ui: headlamp_view cluster -->

   The overview of the cluster opens. Its **Events** list can show warnings from the first seconds of the new cluster, such as `FailedCreatePodSandBox` and `InvalidDiskCapacity`. Kubernetes retries those Pods by itself, and the warnings do not come back.

7. In the sidebar, click **Cluster**, then **Nodes**.

   <!-- shots:begin -->
   <img src="img/07-pods/0150-headlamp_view-1.png" alt="Headlamp: nodes" width="800">

   <!-- shots:end -->

   <!-- ui: headlamp_view nodes -->

   Headlamp lists the same three nodes.

## Part 3: Explore the cluster and its API

1. List the Pods of the cluster's own components.

   ```bash
   kubectl -n kube-system get pods
   ```

   `coredns`, `local-path-provisioner` and `metrics-server` show `Running` (run the command again if one does not).

   <!-- test
   kubectl -n kube-system wait --for=condition=Ready pod -l k8s-app=kube-dns --timeout=180s
   -->

2. List the first resource types that the API server offers.

   ```bash
   kubectl api-resources | head -15
   ```

3. Print the names of the namespaces from the raw JSON answer of the API.

   ```bash
   kubectl get --raw /api/v1/namespaces | jq -r '.items[].metadata.name'
   ```

   The output lists `default`, `kube-node-lease`, `kube-public` and `kube-system`.

4. Read the API documentation of the readiness probe.

   ```bash
   kubectl explain pod.spec.containers.readinessProbe | head -12
   ```

## Part 4: A Pod with probes

1. Create `~/bagtrack/k8s/namespace.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/namespace.yaml -->
   ```yaml
   apiVersion: v1
   kind: Namespace
   metadata:
     name: bagtrack
   ```

2. Create `~/bagtrack/k8s/bag-api-config.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/bag-api-config.yaml -->
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: bag-api-config
     namespace: bagtrack
   data:
     HUB: ORD
     SEED: "true"
   ```

3. Create `~/bagtrack/k8s/bag-api-pod.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/bag-api-pod.yaml -->
   ```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: bag-api
     namespace: bagtrack
     labels:
       app: bag-api
   spec:
     containers:
     - name: bag-api
       image: localhost:5000/bag-api:1.0
       ports:
       - containerPort: 8000
       envFrom:
       - configMapRef:
           name: bag-api-config
       livenessProbe:
         httpGet: {path: /healthz, port: 8000}
         periodSeconds: 10
       readinessProbe:
         httpGet: {path: /readyz, port: 8000}
         periodSeconds: 5
       resources:
         requests: {cpu: 50m, memory: 64Mi}
         limits: {memory: 256Mi}
   ```

4. Apply the three files.

   ```bash
   kubectl apply -f k8s/namespace.yaml -f k8s/bag-api-config.yaml -f k8s/bag-api-pod.yaml
   ```

   The output ends with `pod/bag-api created`.

   <!-- test
   kubectl -n bagtrack wait --for=condition=Ready pod/bag-api --timeout=180s
   -->

5. Show the Pod and the node that runs it.

   ```bash
   kubectl -n bagtrack get pod bag-api -o wide
   ```

   READY is `1/1` and STATUS is `Running` (run the command again if READY is `0/1`).

6. Show the details and the events of the Pod.

   ```bash
   kubectl -n bagtrack describe pod bag-api
   ```

   Find the `Liveness` and `Readiness` lines, the ConfigMap under `Environment Variables from`, and the `Events` at the end.

7. Show the log of the Pod.

   ```bash
   kubectl -n bagtrack logs bag-api
   ```

   Near the top, the log says `bag-api version 1.0 starting: hub ORD, storage memory`, and each probe adds a `GET /healthz` or `GET /readyz` line.

8. Call `/api/info` from inside the container.

   ```bash
   kubectl -n bagtrack exec bag-api -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/info').read().decode())"
   ```

   ```text
   {"service":"bag-api","version":"1.0","hostname":"bag-api","hub":"ORD","storage":"memory"}
   ```

   <!-- test
   kubectl -n bagtrack exec bag-api -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/info').read().decode())" \
     | jq -e '.hostname == "bag-api" and .hub == "ORD" and .storage == "memory"' >/dev/null
   -->

9. In Headlamp, click **Workloads**, then **Pods**, then **bag-api**, then the **Show Logs** icon at the top of the page.

   <!-- shots:begin -->
   <img src="img/07-pods/0298-headlamp_view-1.png" alt="Headlamp: pod-logs bagtrack bag-api, step 1 of 3" width="800">

   <img src="img/07-pods/0298-headlamp_view-2.png" alt="Headlamp: pod-logs bagtrack bag-api, step 2 of 3" width="800">

   <img src="img/07-pods/0298-headlamp_view-3.png" alt="Headlamp: pod-logs bagtrack bag-api, step 3 of 3" width="800">

   <!-- shots:end -->

   <!-- ui: headlamp_view pod-logs bagtrack bag-api -->

   Headlamp shows the same log as step 7. An `Unhealthy` warning under **Diagnostics** on the Pod page is from the seconds before bag-api answered its first readiness probe.

## Part 5: Readiness in action

1. Create a Secret that holds a database address for bag-api.

   ```bash
   kubectl -n bagtrack create secret generic bag-api-db \
     --from-literal=DATABASE_URL=postgresql://bagtrack:bagtrack-k8s-pw@bagtrack-db:5432/bagtrack
   ```

   The output is `secret/bag-api-db created`.

2. Show the Secret.

   ```bash
   kubectl -n bagtrack get secret bag-api-db -o yaml
   ```

   Under `data`, the value of `DATABASE_URL` is base64 text.

3. Decode the value.

   ```bash
   kubectl -n bagtrack get secret bag-api-db -o jsonpath='{.data.DATABASE_URL}' | base64 -d; echo
   ```

   The output is the address from step 1, with its password.

   <!-- test
   t_eq "$(kubectl -n bagtrack get secret bag-api-db -o jsonpath='{.data.DATABASE_URL}' | base64 -d)" \
     "postgresql://bagtrack:bagtrack-k8s-pw@bagtrack-db:5432/bagtrack" "decoded Secret"
   -->

4. Create `~/bagtrack/k8s/bag-api-db-test-pod.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/bag-api-db-test-pod.yaml -->
   ```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: bag-api-db-test
     namespace: bagtrack
   spec:
     containers:
     - name: bag-api
       image: localhost:5000/bag-api:1.0
       envFrom:
       - configMapRef:
           name: bag-api-config
       - secretRef:
           name: bag-api-db
       livenessProbe:
         httpGet: {path: /healthz, port: 8000}
         periodSeconds: 10
       readinessProbe:
         httpGet: {path: /readyz, port: 8000}
         periodSeconds: 5
   ```

5. Apply it.

   ```bash
   kubectl apply -f k8s/bag-api-db-test-pod.yaml
   ```

6. Show the new Pod.

   ```bash
   kubectl -n bagtrack get pod bag-api-db-test
   ```

   STATUS becomes `Running`, while READY stays `0/1` and RESTARTS stays `0`.

   <!-- test
   kubectl -n bagtrack wait --for=jsonpath='{.status.phase}'=Running pod/bag-api-db-test --timeout=180s
   for i in $(seq 1 30); do
     kubectl -n bagtrack describe pod bag-api-db-test | grep -q 'Readiness probe failed' && break
     sleep 2
   done
   t_eq "$(kubectl -n bagtrack get pod bag-api-db-test -o jsonpath='{.status.containerStatuses[0].ready}')" false "bag-api-db-test ready"
   t_eq "$(kubectl -n bagtrack get pod bag-api-db-test -o jsonpath='{.status.containerStatuses[0].restartCount}')" 0 "bag-api-db-test restarts"
   -->

7. Find the failed readiness checks in the events of the Pod.

   ```bash
   kubectl -n bagtrack describe pod bag-api-db-test | grep 'Readiness probe failed'
   ```

   The line ends with `HTTP probe failed with statuscode: 503`, because the database `bagtrack-db` does not exist yet.

8. Delete the test Pod.

   ```bash
   kubectl -n bagtrack delete pod bag-api-db-test
   ```

## Part 6: Two containers in one Pod

1. Create `~/bagtrack/k8s/pair-pod.yaml` in VS Code with this content and save it.

   <!-- file: ~/bagtrack/k8s/pair-pod.yaml -->
   ```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: bag-api-pair
     namespace: bagtrack
   spec:
     containers:
     - name: bag-api
       image: localhost:5000/bag-api:1.0
       envFrom:
       - configMapRef:
           name: bag-api-config
     - name: scanner
       image: localhost:5000/scanner:1.0
       env:
       - name: API_URL
         value: http://localhost:8000
   ```

2. Apply it.

   ```bash
   kubectl apply -f k8s/pair-pod.yaml
   ```

3. Show the Pod.

   ```bash
   kubectl -n bagtrack get pod bag-api-pair
   ```

   READY is `2/2`, one for each container (run the command again if it is lower).

   <!-- test
   kubectl -n bagtrack wait --for=condition=Ready pod/bag-api-pair --timeout=180s
   for i in $(seq 1 30); do
     kubectl -n bagtrack logs bag-api-pair -c scanner | grep -q ' -> ' && break
     sleep 2
   done
   kubectl -n bagtrack logs bag-api-pair -c scanner | t_contains ' -> ' "a scan in the scanner log"
   -->

4. Show the last lines of the log of the scanner container.

   ```bash
   kubectl -n bagtrack logs bag-api-pair -c scanner --tail 5
   ```

   The lines show scans such as `scanner bag-api-pair: BT100004 loaded -> unloaded`.

5. Show the last requests that the bag-api container received.

   ```bash
   kubectl -n bagtrack logs bag-api-pair -c bag-api --tail 3
   ```

   The requests come from `127.0.0.1`, because the scanner calls bag-api on `localhost`.

6. Delete the Pod.

   ```bash
   kubectl -n bagtrack delete pod bag-api-pair
   ```

## Part 7: A bare Pod is not replaced

1. Delete the bag-api Pod.

   ```bash
   kubectl -n bagtrack delete pod bag-api
   ```

2. List the Pods in the namespace.

   ```bash
   kubectl -n bagtrack get pods
   ```

   The output is `No resources found in bagtrack namespace.`, and no new bag-api Pod appears.

   <!-- test
   t_eq "$(kubectl -n bagtrack get pods --no-headers 2>/dev/null | wc -l)" 0 "Pods left in bagtrack"
   -->

## Check your work

1. List the nodes.

   ```bash
   kubectl get nodes
   ```

   Three nodes show `Ready`.

2. Show the ConfigMap and the Secret of bag-api.

   ```bash
   kubectl -n bagtrack get configmap/bag-api-config secret/bag-api-db
   ```

   Both are listed.

3. List the Pods in the namespace.

   ```bash
   kubectl -n bagtrack get pods
   ```

   No Pods are left.

   <!-- test
   t_eq "$(kubectl get nodes --no-headers | grep -cw Ready)" 3 "Ready nodes"
   t_eq "$(kubectl -n bagtrack get configmap bag-api-config -o jsonpath='{.data.HUB}')" ORD "ConfigMap bag-api-config"
   kubectl -n bagtrack get secret bag-api-db >/dev/null
   t_eq "$(kubectl -n bagtrack get pods --no-headers 2>/dev/null | wc -l)" 0 "Pods left in bagtrack"
   command -v kubectl >/dev/null
   command -v k3d >/dev/null
   dpkg -s headlamp >/dev/null
   -->

<!-- runner: stop -->

## Troubleshooting

| Problem | Fix |
|---|---|
| `sudo: gpg: command not found` | Install it with `sudo apt-get -o DPkg::Lock::Timeout=300 install -y gpg`, then repeat Part 1, step 2. |
| `k3d cluster create` stops with `port is already allocated` | Another container uses port 8081, 30080 or 6550. Find it with `docker ps` and stop it, run `k3d cluster delete hub`, and create the cluster again. |
| `Failed to create cluster 'hub' because a cluster with that name already exists` | Run `k3d cluster delete hub`, then create the cluster again. |
| kubectl prints `The connection to the server localhost:8080 was refused` | kubectl has no settings for the cluster, for example after `sudo k3d cluster create`. Run `k3d kubeconfig merge hub --kubeconfig-merge-default`. |
| A Pod shows `ErrImagePull` or `ImagePullBackOff` | Check that the `registry` container runs (`docker ps`) and is on the `lab` network (`docker network inspect lab`). If you created the cluster without `k8s/registries.yaml`, delete the cluster and create it again. |
| `error: failed to create secret secrets "bag-api-db" already exists` | The Secret is there from an earlier try. Go on with the next step. |
| Headlamp does not open, and `headlamp` in a terminal prints `libasound.so.2: cannot open shared object file` | Install the library with `sudo apt-get -o DPkg::Lock::Timeout=300 install -y libasound2t64`. |
| Headlamp does not list `k3d-hub` | Headlamp started before the cluster existed. Close Headlamp and start it again. |

## Going further (optional)

- Run `kubectl explain pod.spec.containers.startupProbe` and compare it with the readiness probe.
- Change `HUB` to `DEN` in the ConfigMap, run the bag-api Pod again and call `/api/info`; set `HUB` back to `ORD` and delete the Pod when you are done.
- With the bag-api Pod running, click **Terminal / Exec** on its Headlamp page and run `id`; delete the Pod when you are done.
