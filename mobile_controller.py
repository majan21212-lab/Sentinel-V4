"""
mobile_controller.py — Transparent API gateway.
Forwards all /web-api/api/* calls to the real backend (web_server.py on port 8000).
"""
import os, httpx, uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
DIST_PATH  = "../../dist"
BACKEND    = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Transparent proxy: /web-api/api/* → real backend /api/* ───────────────────

@app.api_route("/web-api/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    target_url = f"{BACKEND}/api/{path}"
    params     = dict(request.query_params)

    try:
        body = await request.body()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(
                method  = request.method,
                url     = target_url,
                params  = params,
                content = body,
                headers = {
                    k: v for k, v in request.headers.items()
                    if k.lower() not in ("host", "content-length")
                },
            )
        return JSONResponse(
            content    = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {},
            status_code= resp.status_code,
        )
    except httpx.ConnectError:
        return JSONResponse({"status": "error", "message": "Backend unreachable"}, status_code=503)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ── Static file serving for the React frontend ─────────────────────────────────

if os.path.exists(DIST_PATH):
    try:
        app.mount("/assets", StaticFiles(directory=f"{DIST_PATH}/assets"), name="assets")
    except Exception:
        pass

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    candidate = os.path.join(DIST_PATH, full_path)
    if os.path.isfile(candidate):
        return FileResponse(candidate)
    index = os.path.join(DIST_PATH, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return JSONResponse({"status": "ok", "message": "Fleet Command Gateway"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
