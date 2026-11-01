# Containerization Fast Track

Hands-on labs and slides for a three-day course on containers.
- **Day 1:** you package and run software with Docker.
- **Day 2:** you build small, secure images and publish them from a CI pipeline in Harness Open Source.
- **Day 3:** you run the whole system on Kubernetes.

All labs use **BagTrack**, a small baggage-tracking system for an airline hub. It has four parts:

| Part | What it is |
|---|---|
| `bag-api` | Python (FastAPI) service that records bags and their scans at each checkpoint |
| `scanner` | Go worker that simulates the checkpoint scanners |
| `board` | Baggage-claim board in the browser, served by nginx |
| `db` | PostgreSQL |

The local tools stand in for AWS services: Docker Compose and ECS task definitions stand in for Amazon ECS on AWS Fargate, and the local Kubernetes cluster stands in for Amazon EKS.

## Course outline

**Day 1: Containers and Docker** ([slides](slides/day1.html))
- Lectures: distributed systems and cloud native · containers and virtual machines · Linux under the hood · images and Dockerfiles · data, networking and troubleshooting
- [Lab 01: Your lab machine and first containers](labs/01-first-containers.md)
- [Lab 02: Build images](labs/02-images.md)
- [Lab 03: Data, networks and health](labs/03-data-and-networks.md)

**Day 2: Docker in depth** ([slides](slides/day2.html))
- Lectures: building small images · container security · Compose and Amazon ECS/Fargate · CI for images with Harness Open Source
- [Lab 04: Smaller, safer images](labs/04-small-secure-images.md)
- [Lab 05: Compose, then ECS](labs/05-compose-and-ecs.md)
- [Lab 06: Build, scan and publish with Harness Open Source](labs/06-harness-ci.md)

**Day 3: Kubernetes** ([slides](slides/day3.html))
- Lectures: orchestration and Kubernetes architecture · Pods and configuration · Services and Deployments · stateful and batch workloads
- [Lab 07: A cluster and its first Pods](labs/07-pods.md)
- [Lab 08: Deployments and Services](labs/08-deployments-services.md)
- [Lab 09: Storage, StatefulSets and batch work](labs/09-state-and-batch.md)

PDF copies of the slides are in [`slides/pdf/`](slides/pdf/).

## Your lab machine

- Ubuntu 24.04 LTS with a desktop and a web browser
- 8 vCPUs, 16 GB RAM, 80 GB disk
- A user with sudo rights, and outbound internet access

You install every tool yourself during the labs:

| Tool | Version | Installed in |
|---|---|---|
| Docker Engine (with Compose and Buildx) | 29.9 | Lab 01 |
| Portainer Community Edition | 2.45.3 | Lab 01 |
| Container registry (`registry`) | 3 | Lab 02 |
| Trivy | 0.76.1 | Lab 04 |
| Harness Open Source | 3.3.0 | Lab 06 |
| kubectl | 1.36 | Lab 07 |
| k3d (runs k3s v1.36.5) | 5.9.0 | Lab 07 |
| Headlamp | 0.46.0 | Lab 07 |

Official base images come from Amazon ECR Public (`public.ecr.aws/docker/library/...`), so the labs need no Docker Hub account.

## Getting started

Open a terminal on your lab machine and start [Lab 01](labs/01-first-containers.md). Copy each command with the copy button on its code block, paste it into the terminal, and press Enter.

## If you fall behind or switch machines

Each lab starts where the previous one ended. To start a lab on a new machine, run the earlier labs automatically:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/nicklotz/containerization-fundamentals.git ~/containerization-fundamentals
~/containerization-fundamentals/scripts/catch-up.sh 05
```

Replace `05` with the number of the lab you want to start. The script needs a machine where you have not started the labs.

## What is in this repository

| Path | Contents |
|---|---|
| `labs/` | The nine labs, with screenshots in `labs/img/` |
| `slides/` | The three slide decks (open the `.html` files in a browser) and their PDFs |
| `app/` | BagTrack source code: `bag-api`, `scanner` and `board` |
| `challenge/` | The code challenge in Lab 04 |
| `solutions/` | Every file you create in the labs, as it is at the end of each lab |
| `scripts/catch-up.sh` | Runs the earlier labs on a new machine |
| `tests/` | The runner that tests every lab on a fresh machine |

Copyright (C) 2026 Nicholas Lotz. Licensed under the GNU Affero General Public License v3.0 (see `LICENSE`). The fonts in `slides/fonts/` are IBM Plex, licensed under the SIL Open Font License (see the `*-OFL.txt` files).
