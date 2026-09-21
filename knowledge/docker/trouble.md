# Docker Troubleshooting

## Docker port is already allocated
**Symptom:** `docker run` or `docker compose up` fails with `Bind for 0.0.0.0:5432 failed: port is already allocated` or `address already in use`.

**Causes:**
- Another container already publishes the same host port.
- A local service (for example a PostgreSQL installed on the host) is already using the port.

**Diagnose:**
1. List containers and their ports: `docker ps`.
2. Find the process on the port. Linux/macOS: `lsof -i :5432`. Windows: `netstat -ano | findstr :5432`.

**Fix:**
- Stop the conflicting container or service.
- Or change the host side of the mapping, for example `"5433:5432"`. The first number is the host port, the second is the container port.

## Docker container exits immediately
**Symptom:** `docker ps` shows nothing running, and `docker ps -a` shows the container as `Exited (1)` seconds after start.

**Causes:**
- The main process crashed (bad configuration, missing environment variable, failed dependency).
- The container's main process finished, because containers stop when PID 1 exits.
- Wrong `CMD` or `ENTRYPOINT`.

**Diagnose:**
1. Read the logs: `docker logs <container>`. This shows the actual error most of the time.
2. Inspect the exit code: `docker inspect <container> --format '{{.State.ExitCode}}'`.

**Fix:**
- Fix the error shown in the logs (usually a missing environment variable or bad config).
- Make sure the main process runs in the foreground, not as a background daemon.

## Docker container killed with exit code 137
**Symptom:** A container stops with `Exited (137)`, or `docker inspect` shows `OOMKilled: true`.

**Causes:**
- The container used more memory than its limit, or the host ran out of memory, and the kernel killed the process (SIGKILL = 137).

**Diagnose:**
1. Check `docker inspect <container> --format '{{.State.OOMKilled}}'`.
2. Watch usage with `docker stats`.

**Fix:**
- Raise the memory limit (`--memory` or `mem_limit` in compose).
- On Docker Desktop, raise the memory allocated to the Docker VM in Settings.
- Fix memory leaks or reduce application memory settings (for example Java heap size).

## Docker containers cannot connect to each other using localhost
**Symptom:** An application in one container fails with `Connection refused` when connecting to `localhost:5432` or `localhost:9092`, even though the database or Kafka container is running and its port is published.

**Causes:**
- Inside a container, `localhost` means the container itself, not the host machine and not other containers.
- The containers are on different Docker networks.

**Diagnose:**
1. Check both containers are on the same network: `docker network inspect <network>`.
2. From inside the app container, test the target: `docker exec -it <app> nc -zv postgres 5432`.

**Fix:**
- Use the service name from `docker-compose.yml` as the hostname, for example `postgres:5432` or `kafka:29092`. Compose puts services on a shared network where service names resolve via DNS.
- Use the container port (right side of the mapping), not the published host port.
- From the app container to a service on the host machine, use `host.docker.internal` (Docker Desktop).

## Docker no space left on device
**Symptom:** Builds or pulls fail with `no space left on device`, or containers crash when writing files.

**Causes:**
- Unused images, stopped containers, build cache, and dangling volumes fill the disk.
- Large container logs.

**Diagnose:**
- `docker system df` shows how much space images, containers, volumes, and build cache use.

**Fix:**
- `docker system prune` removes stopped containers, unused networks, and dangling images.
- `docker builder prune` clears build cache.
- `docker volume prune` removes unused volumes. This deletes data, so confirm you don't need it first.
- Limit log growth with the `json-file` logging options `max-size` and `max-file`.

## Docker permission denied on volume or docker.sock
**Symptom:** `permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock`, or a container gets `Permission denied` writing to a mounted volume.

**Causes:**
- The current user is not in the `docker` group (Linux).
- The container process runs as a non-root user that does not own the mounted directory.

**Diagnose:**
- Run `groups` to check for `docker`. Check the owner of the mounted directory with `ls -ld <path>`.

**Fix:**
- Add the user to the group: `sudo usermod -aG docker $USER`, then log out and back in.
- Change ownership of the mounted directory to the UID the container runs as, or set the container's `user:` to match.