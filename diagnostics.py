import socket

SERVICES = {
    "kafka": ("localhost", 9092),
    "postgresql": ("localhost", 5432),
    "fastapi": ("localhost", 8000),
    "docker": ("localhost", 2375),  # Docker Desktop's TCP API is off by default; usually shows unreachable
}


def check_service_status(service):
    """Try to open a TCP connection to the service's usual port. Returns a dict, never raises."""
    service = service.lower()
    if service not in SERVICES:
        return {"service": service, "status": "unknown", "detail": f"No check defined for '{service}'."}

    host, port = SERVICES[service]
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return {"service": service, "status": "reachable", "detail": f"{host}:{port} accepted a connection."}
    except (ConnectionRefusedError, OSError) as e:
        return {"service": service, "status": "unreachable", "detail": f"{host}:{port} — {e}"}


if __name__ == "__main__":
    for name in SERVICES:
        print(check_service_status(name))   