# FastAPI Troubleshooting

## FastAPI connection timeout to PostgreSQL
**Symptom:** A FastAPI application returns 500 errors, and the logs show `sqlalchemy.exc.OperationalError: connection timed out`, `asyncpg.exceptions.ConnectionDoesNotExistError`, or `TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`.

**Causes:**
- **Pool exhausted:** database sessions are not released, so requests wait for a free connection until the pool timeout. This is the `QueuePool limit` error.
- **Wrong host:** FastAPI runs in a Docker container and connects to `localhost`, where PostgreSQL is not running (see PostgreSQL connection refused).
- **Network or firewall:** the database is unreachable from the FastAPI container (see PostgreSQL connection timeout).
- PostgreSQL itself reached `max_connections` (see PostgreSQL too many clients already).

**Diagnose:**
1. Read the error. `QueuePool limit ... reached` points to a session leak or an undersized pool. `connection refused` or a plain timeout points to a network or host problem.
2. Check the `DATABASE_URL` host. In Docker it must be the PostgreSQL service name, not `localhost`.
3. From the FastAPI container, run `nc -zv postgres 5432`.
4. On the database, run `SELECT count(*) FROM pg_stat_activity;` to see whether connections pile up.

**Fix:**
- Manage sessions with a dependency that always closes them, using `try/finally` or a context manager (see the session dependency entry below).
- Use the PostgreSQL service name in `DATABASE_URL`, and put both containers on the same network.
- Tune `pool_size`, `max_overflow`, and `pool_pre_ping=True` when creating the SQLAlchemy engine.
- Add `connect_args={"timeout": 5}` (or `connect_timeout`) so connection failures are quick and readable.

## FastAPI database session not closed
**Symptom:** The FastAPI application works at first, then slows down and starts failing after some traffic, with pool exhaustion errors. PostgreSQL shows many `idle in transaction` connections.

**Causes:**
- A session is created inside the endpoint and never closed, especially when an exception occurs.
- The session is stored globally and shared across requests.

**Diagnose:**
- Check for endpoints that create sessions manually without `close()`.
- On PostgreSQL, look at `pg_stat_activity` for `idle in transaction` sessions from the application.

**Fix:**
Use a dependency that yields the session and always closes it:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items")
def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

## FastAPI 422 Unprocessable Entity
**Symptom:** A request returns `422 Unprocessable Entity` with a body like `{"detail":[{"type":"missing","loc":["body","name"],"msg":"Field required"}]}`.

**Causes:**
- The request body, query parameters, or path parameters do not match the Pydantic model or type hints.
- A required field is missing, a value has the wrong type, or the client did not send JSON with `Content-Type: application/json`.

**Diagnose:**
- Read the `loc` and `msg` fields in the response. They name exactly which field and location failed validation.
- Compare the client's payload with the Pydantic model.

**Fix:**
- Fix the client payload, or make the field optional or give it a default in the model.
- Send JSON with the correct `Content-Type` header.

## FastAPI CORS error in the browser
**Symptom:** The browser console shows `Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:3000' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header`. The same request works with curl.

**Causes:**
- The browser enforces CORS, and the FastAPI server does not allow the frontend's origin.

**Diagnose:**
- Confirm the request works from curl or Postman. If it does, the API is fine and CORS is the issue.
- Check that the origin in the error (scheme, host, and port) matches an allowed origin exactly.

**Fix:**
Add CORS middleware with the frontend's exact origin:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## FastAPI slow or freezing under load
**Symptom:** All FastAPI endpoints become slow when one endpoint is called, or the API hangs while a request is being processed.

**Causes:**
- A blocking call (synchronous database driver, `requests`, `time.sleep`, heavy computation) inside an `async def` endpoint blocks the event loop, so no other request is served meanwhile.

**Diagnose:**
- Look for synchronous I/O inside `async def` functions.
- Check whether latency of unrelated endpoints rises while one slow endpoint runs.

**Fix:**
- Use plain `def` for endpoints that do blocking work. FastAPI runs them in a thread pool.
- Or use async libraries (`httpx`, `asyncpg`, async SQLAlchemy) inside `async def`.
- Move heavy work to a background worker.

## FastAPI not reachable from outside its Docker container
**Symptom:** The FastAPI app runs in a container and logs `Uvicorn running on http://127.0.0.1:8000`, but requests from the host or other containers get `Connection refused` or `ERR_EMPTY_RESPONSE`.

**Causes:**
- Uvicorn binds to `127.0.0.1`, which is only reachable from inside the container.
- The port is not published in the Docker run or compose configuration.

**Diagnose:**
- Check the startup log for the bind address, and `docker ps` for the port mapping.

**Fix:**
- Start Uvicorn with `--host 0.0.0.0`: `uvicorn main:app --host 0.0.0.0 --port 8000`.
- Publish the port, for example `"8000:8000"` in compose.