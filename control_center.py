import os
import subprocess
import threading
import time
import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sentinel Control Center")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to get paths
def get_resource_path(relative_path):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# --- PROXY ENGINE ---
# This allows the control center to forward requests to the bot when it's running on port 8000

BOT_API_URL = "http://127.0.0.1:8000"

@app.api_route("/web-api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_bot(request: Request, path: str):
    url = f"{BOT_API_URL}/api/{path}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward the request to the bot
            method = request.method
            content = await request.body()
            headers = dict(request.headers)
            # Remove host header to avoid issues with proxying
            headers.pop("host", None)
            
            resp = await client.request(
                method, 
                url, 
                content=content, 
                headers=headers,
                params=dict(request.query_params)
            )
            from fastapi import Response
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "bot_offline", "message": "The trading bot is currently stopped. Use the Control Panel to start it."}
            )

@app.post("/api/auth/login")
async def login_bypass(request: Request):
    # This bypass allows you to enter the dashboard on your phone regardless of credentials
    return {
        "status": "success",
        "access_token": "MASTER_CONTROL_TOKEN",
        "token_type": "bearer",
        "user": {"username": "admin", "role": "commander"}
    }

# --- CONTROL API ---

@app.get("/api/control/status")
async def get_bot_status():
    try:
        result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, shell=True)
        import json
        processes = json.loads(result.stdout)
        for p in processes:
            if p['name'] == 'sentinel-backend':
                return {"status": p['pm2_env']['status']}
        return {"status": "not_found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/control/start")
async def start_bot():
    try:
        # We use 'pm2 start' which handles both starting from scratch or restarting a stopped process
        subprocess.run(["pm2", "start", "sentinel-backend"], check=True, shell=True)
        return {"status": "starting"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/control/stop")
async def stop_bot():
    try:
        subprocess.run(["pm2", "stop", "sentinel-backend"], check=True, shell=True)
        return {"status": "stopping"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- STATIC FILES (DASHBOARD) ---

# Serve the React dist folder
# Assuming dist is in the root (../../dist)
DIST_PATH = get_resource_path("../../dist")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(DIST_PATH, "index.html"))

@app.get("/{full_path:path}")
async def serve_assets(full_path: str):
    file_path = os.path.join(DIST_PATH, full_path)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    # Fallback to index for SPA
    return FileResponse(os.path.join(DIST_PATH, "index.html"))

if __name__ == "__main__":
    import uvicorn
    # This server will ALWAYS be online on port 8080
    # The trading bot will run separately on port 8000.
    uvicorn.run(app, host="0.0.0.0", port=8080)
