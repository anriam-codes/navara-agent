# PostgreSQL Troubleshooting

## PostgreSQL connection refused
**Symptom:** `psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused`, or an application logs `could not connect to server: Connection refused`.

**Causes:**
- The PostgreSQL server is not running.
- PostgreSQL listens on a different port or interface. `listen_addresses` defaults to `localhost`, so it does not accept connections from other machines or containers.
- The client connects to `localhost` from inside a Docker container, where `localhost` is the container itself.

**Diagnose:**
1. Check the server: `pg_isready -h localhost -p 5432`, or `docker ps` and `docker logs <postgres-container>`.
2. Check the port and interface: `SHOW port;` and `SHOW listen_addresses;`.

**Fix:**
- Start the server.
- Set `listen_addresses = '*'` in `postgresql.conf` and restart if remote clients must connect.
- When the client is another container, use the PostgreSQL service name as the host (for example `postgres`), not `localhost`.

## PostgreSQL password authentication failed
**Symptom:** `FATAL: password authentication failed for user "app"`, or `no pg_hba.conf entry for host "172.18.0.3", user "app", database "appdb", SSL off`.

**Causes:**
- Wrong username or password.
- The database user or password in the container was set after the data volume already existed, so the new `POSTGRES_PASSWORD` was ignored.
- `pg_hba.conf` has no rule allowing this user, database, and client address.

**Diagnose:**
1. Try to log in with `psql` using the same credentials.
2. Read the PostgreSQL server log, which states which `pg_hba.conf` rule applied or was missing.

**Fix:**
- Correct the credentials in the application's connection string.
- Reset the password: `ALTER USER app WITH PASSWORD 'new_password';`.
- Add a matching `host` line in `pg_hba.conf` and reload with `SELECT pg_reload_conf();`.
- In Docker, `POSTGRES_PASSWORD` only applies when the data directory is empty. Remove the volume to re-initialize (this deletes data).

## PostgreSQL too many clients already
**Symptom:** `FATAL: sorry, too many clients already` or `remaining connection slots are reserved for non-replication superuser connections`.

**Causes:**
- The number of open connections reached `max_connections` (default 100).
- The application opens connections without closing them (connection leak).
- Many application instances each hold a large connection pool.

**Diagnose:**
1. Count connections: `SELECT count(*) FROM pg_stat_activity;`.
2. See who holds them: `SELECT usename, state, count(*) FROM pg_stat_activity GROUP BY 1, 2;`. Many `idle` or `idle in transaction` sessions indicate a leak.

**Fix:**
- Fix leaks by always closing connections and sessions.
- Cap the pool size in each application so that instances times pool size stays below `max_connections`.
- Use a pooler such as PgBouncer.
- Raise `max_connections` only as a last resort, because each connection uses memory.

## PostgreSQL connection timeout
**Symptom:** An application waits and then fails with `connection timed out`, `timeout expired`, or `could not connect to server: Operation timed out`. Unlike "connection refused", nothing answers at all.

**Causes:**
- A firewall or security group drops traffic to port 5432.
- The host or IP in the connection string is wrong or unreachable.
- The client and database are on different Docker networks.
- The server is overloaded, or all connections are in use and new ones wait.

**Diagnose:**
1. Test reachability from the client: `nc -zv <host> 5432` or `pg_isready -h <host>`.
2. Check firewall and security-group rules for port 5432.
3. In Docker, run `docker network inspect` to confirm both containers share a network.
4. Check `pg_stat_activity` for connection saturation.

**Fix:**
- Open the port for the client's address, and correct the host in the connection string.
- Put the client and database on the same Docker network and use the service name as host.
- Set a `connect_timeout` in the connection string so failures are quick and clear.

## PostgreSQL queries slow or blocked by locks
**Symptom:** Queries hang for a long time, or an `UPDATE` never finishes while other sessions work normally.

**Causes:**
- A long-running or `idle in transaction` session holds locks that block others.
- Missing indexes cause full table scans.

**Diagnose:**
1. Find blocked and blocking sessions: `SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE state <> 'idle';`.
2. Inspect a slow query with `EXPLAIN ANALYZE <query>` and look for `Seq Scan` on large tables.

**Fix:**
- End the blocking session: `SELECT pg_terminate_backend(<pid>);`.
- Add indexes on columns used in `WHERE` and `JOIN`.
- Keep transactions short and commit or roll back promptly.