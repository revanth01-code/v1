import time
from fastapi import Request


async def log_requests(request: Request, call_next):
    start = time.time()
    print(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    print(f"← {request.method} {request.url.path} {response.status_code} ({duration_ms:.0f}ms)")
    return response