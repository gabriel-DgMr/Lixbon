import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.orchestrator import NodeOrchestrator

from app.db import (
    create_api_key,
    ensure_conversation,
    get_usage_summary,
    init_db,
    list_api_keys,
    list_clients_usage,
    list_recent_conversations,
    save_message,
    validate_api_key,
    create_user,
    verify_user,
    get_user_by_id
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
APP_TITLE = "LAN LLM API Gateway"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SOURCE_PATH = PROJECT_ROOT / "client_cli.py"
DEBUG_LOG_PATH = PROJECT_ROOT / ".cursor" / "debug.log"

app = FastAPI(title=APP_TITLE, version="0.1.0")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
http_client_fast: httpx.AsyncClient | None = None
http_client_chat: httpx.AsyncClient | None = None
orquestador: NodeOrchestrator = NodeOrchestrator()

cors_origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limit_lock = threading.Lock()
rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)

def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    try:
        payload = {
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
        }
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{payload}\n")
    except Exception:
        pass

class AuthRequest(BaseModel):
    username: str
    password: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Modelo de Ollama")
    messages: list[ChatMessage]
    conversation_id: str | None = None
    title: str | None = None
    client_id: str | None = None
    stream: bool = False

class UIChatRequest(BaseModel):
    model: str
    message: str
    conversation_id: str | None = None
    title: str | None = None

class CompletionRequest(BaseModel):
    model: str = Field(..., description="Modelo de Ollama")
    prompt: str
    conversation_id: str | None = None
    title: str | None = None
    client_id: str | None = None
    stream: bool = False

def get_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()

def api_key_required(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = get_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="API key ausente")
    user_data = validate_api_key(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="API key invalida")
    enforce_rate_limit(token)
    return user_data


def validate_model_access(user_data: dict[str, Any], requested_model: str) -> None:
    """Lanza 403 si la key tiene modelo asignado y no coincide con el solicitado."""
    key_model = user_data.get("key_model")
    if key_model and key_model != requested_model:
        raise HTTPException(
            status_code=403,
            detail=f"Esta API key solo permite el modelo '{key_model}'. Solicitud: '{requested_model}'",
        )

def cookie_auth_required(session_token: str | None = Cookie(default=None), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = session_token or get_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="No estas logueado")
    user_data = validate_api_key(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Sesion invalida")
    return user_data

def enforce_rate_limit(api_key: str) -> None:
    now_ts = time.time()
    window_seconds = 60
    with rate_limit_lock:
        bucket = rate_limit_hits[api_key]
        while bucket and (now_ts - bucket[0]) > window_seconds:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MIN:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit excedido: maximo {RATE_LIMIT_PER_MIN} requests por minuto",
            )
        bucket.append(now_ts)


@app.on_event("startup")
async def on_startup() -> None:
    global http_client_fast, http_client_chat
    init_db()
    http_client_fast = httpx.AsyncClient(timeout=10.0)
    http_client_chat = httpx.AsyncClient(timeout=120.0)
    # Inicia el orquestador de nodos LAN en background
    orquestador.iniciar()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global http_client_fast, http_client_chat
    orquestador.detener()
    if http_client_fast is not None:
        await http_client_fast.aclose()
    if http_client_chat is not None:
        await http_client_chat.aclose()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

@app.post("/api/auth/register")
async def api_register(payload: AuthRequest):
    user = create_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    
    # Crea una API key inicial
    raw_key, _ = create_api_key(f"Default Key - {payload.username}", user["id"])
    
    response = JSONResponse({"message": "Usuario registrado", "api_key": raw_key, "user": user})
    response.set_cookie(key="session_token", value=raw_key, httponly=True)
    return response

@app.post("/api/auth/login")
async def api_login(payload: AuthRequest):
    user = verify_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        
    # Genera una key de sesion (o para la CLI)
    raw_key, _ = create_api_key(f"Login {int(time.time())}", user["id"])
    
    response = JSONResponse({"message": "Login correcto", "api_key": raw_key, "user": user})
    response.set_cookie(key="session_token", value=raw_key, httponly=True)
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session_token: str | None = Cookie(default=None)):
    if not session_token:
        return RedirectResponse(url="/login")
        
    user_data = validate_api_key(session_token)
    if not user_data:
        response = RedirectResponse(url="/login")
        response.delete_cookie("session_token")
        return response

    user_id = user_data["id"]
    usage = get_usage_summary(user_id)
    conversations = list_recent_conversations(user_id=user_id)
    clients = list_clients_usage(user_id=user_id)
    keys = list_api_keys(user_id=user_id)
    models = await fetch_models()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user_data,
            "usage": usage,
            "conversations": conversations,
            "clients": clients,
            "keys": keys,
            "models": models,
            "ollama_url": OLLAMA_BASE_URL,
            "rate_limit_per_min": RATE_LIMIT_PER_MIN,
            "server_base_url": str(request.base_url).rstrip("/"),
        },
    )

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/install/client_cli.py")
async def download_cli() -> FileResponse:
    if not CLI_SOURCE_PATH.exists():
        raise HTTPException(status_code=404, detail="Archivo client_cli.py no encontrado")
    return FileResponse(path=str(CLI_SOURCE_PATH), media_type="text/x-python", filename="client_cli.py")


@app.get("/install.sh")
async def install_script(request: Request) -> PlainTextResponse:
    server_base = str(request.base_url).rstrip("/")
    try:
        script = f"""#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="${{1:-{server_base}}}"
INSTALL_DIR="${{HOME}}/.lan-llm-cli"
BIN_DIR="${{HOME}}/.local/bin"
CLI_FILE="${{INSTALL_DIR}}/client_cli.py"
LAUNCHER_FILE="${{BIN_DIR}}/lanllm"

echo "Instalando LAN LLM CLI..."
mkdir -p "${{INSTALL_DIR}}" "${{BIN_DIR}}"
curl -fsSL "${{SERVER_URL}}/install/client_cli.py" -o "${{CLI_FILE}}"
chmod +x "${{CLI_FILE}}"
python3 "${{CLI_FILE}}" init --base-url "${{SERVER_URL}}/v1" >/dev/null 2>&1 || true

cat > "${{LAUNCHER_FILE}}" <<'EOF'
#!/usr/bin/env bash
python3 "${{HOME}}/.lan-llm-cli/client_cli.py" "$@"
EOF
chmod +x "${{LAUNCHER_FILE}}"

for profile in "${{HOME}}/.bashrc" "${{HOME}}/.zshrc"; do
  if [ -f "$profile" ] && ! grep -q '\\.local/bin' "$profile"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$profile"
  fi
done

echo "CLI instalado en: ${{CLI_FILE}}"
echo "Comando creado: ${{LAUNCHER_FILE}}"
echo "Ejemplo:"
echo "  lanllm setup"
echo "  lanllm"
echo "  lanllm chat"
echo
echo "Si 'lanllm' no se reconoce en la sesion actual, ejecuta:"
echo "  export PATH=\\"$HOME/.local/bin:$PATH\\""
"""
        return PlainTextResponse(content=script)
    except Exception as exc:
        raise

@app.get("/install.ps1")
async def install_script_windows(request: Request) -> PlainTextResponse:
    server_base = str(request.base_url).rstrip("/")
    script = f"""$ErrorActionPreference = "Stop"

$ServerUrl = if ($args.Count -gt 0 -and $args[0]) {{ $args[0] }} else {{ "{server_base}" }}
$InstallDir = Join-Path $env:USERPROFILE ".lan-llm-cli"
$CliFile = Join-Path $InstallDir "client_cli.py"
$LauncherFile = Join-Path $InstallDir "lanllm.cmd"

Write-Host "Instalando LAN LLM CLI en Windows..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Invoke-WebRequest -Uri "$ServerUrl/install/client_cli.py" -OutFile $CliFile
python $CliFile init --base-url "$ServerUrl/v1" | Out-Null

@"
@echo off
python "%USERPROFILE%\\.lan-llm-cli\\client_cli.py" %*
"@ | Set-Content -Path $LauncherFile -Encoding Ascii

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) {{ $userPath = "" }}
if ($userPath -notlike "*$InstallDir*") {{
  $newPath = if ($userPath) {{ "$userPath;$InstallDir" }} else {{ $InstallDir }}
  [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
  Write-Host "Se agrego al PATH de usuario: $InstallDir"
}} else {{
  Write-Host "El PATH de usuario ya contiene: $InstallDir"
}}

Write-Host ""
Write-Host "CLI instalado en: $CliFile"
Write-Host "Comando: lanllm (abre una nueva terminal para usarlo)"
Write-Host "Ejemplo:"
Write-Host "  lanllm setup"
Write-Host "  lanllm"
Write-Host "  lanllm chat"
"""
    return PlainTextResponse(content=script)

@app.get("/api/usage")
async def api_usage(user_data: dict[str, Any] = Depends(cookie_auth_required)):
    return get_usage_summary(user_data["id"])


@app.get("/api/nodes")
async def api_nodos(user_data: dict[str, Any] = Depends(cookie_auth_required)):
    """Lista todos los nodos con su estado y métricas actuales."""
    return {"nodos": orquestador.estado_nodos()}


@app.get("/api/nodes/best")
async def api_mejor_nodo(user_data: dict[str, Any] = Depends(cookie_auth_required)):
    """Muestra cuál sería el nodo elegido en este momento."""
    nodo = orquestador.best_node()
    if not nodo:
        return {"nodo": None, "mensaje": "Sin nodos online. Se usará Ollama local."}
    return {"nodo": nodo}

@app.get("/v1/models")
async def models(user_data: dict[str, Any] = Depends(api_key_required)):
    return {"object": "list", "data": await fetch_models()}

@app.get("/api/key/info")
async def api_key_info(user_data: dict[str, Any] = Depends(api_key_required)):
    """Devuelve el modelo vinculado a la API key actual (None = global)."""
    return {
        "user": user_data.get("username"),
        "key_model": user_data.get("key_model"),
    }

@app.post("/api/keys")
async def create_api_key_endpoint(payload: dict[str, Any], user_data: dict[str, Any] = Depends(cookie_auth_required)):
    name = (payload.get("name") or "").strip()
    model = (payload.get("model") or "").strip() or None
    # Si no hay nombre, usar el modelo como nombre; si tampoco hay modelo, usar etiqueta genérica
    if not name:
        name = model or "Nueva Key"
    raw_key, key_data = create_api_key(name, user_data["id"], model)
    return {"api_key": raw_key, "data": key_data}

@app.post("/api/chat")
async def api_chat(payload: UIChatRequest, user_data: dict[str, Any] = Depends(cookie_auth_required)):
    conv_id = payload.conversation_id or str(uuid.uuid4())
    ensure_conversation(conv_id, user_data["id"], payload.title, "dashboard")
    messages = [{"role": "user", "content": payload.message}]
    save_message(conv_id, "user", payload.message, model=payload.model)

    started_at = time.perf_counter()
    ollama_resp = await ollama_chat(payload.model, messages)
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    assistant_text = ollama_resp.get("message", {}).get("content", "")
    prompt_tokens = int(ollama_resp.get("prompt_eval_count") or 0)
    completion_tokens = int(ollama_resp.get("eval_count") or 0)
    save_message(
        conv_id,
        "assistant",
        assistant_text,
        model=payload.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
    )
    return {
        "conversation_id": conv_id,
        "model": payload.model,
        "message": assistant_text,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "latency_ms": latency_ms,
    }


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest, user_data: dict[str, Any] = Depends(api_key_required)):

    # Verificar que el modelo del request coincida con el vinculado a la key
    validate_model_access(user_data, payload.model)

    conv_id = payload.conversation_id or str(uuid.uuid4())
    ensure_conversation(conv_id, user_data["id"], payload.title, payload.client_id)

    if payload.messages:
        last_msg = payload.messages[-1]
        if last_msg.role == "user":
            save_message(conv_id, "user", last_msg.content, model=payload.model)

    # Seleccionar nodo que tenga el modelo con más recursos libres
    nodo_elegido = orquestador.best_node_for_model(payload.model)
    started_at = time.perf_counter()

    import logging as _log
    _log.getLogger("uvicorn").info(f"[chat] modelo='{payload.model}' stream={payload.stream} nodo={nodo_elegido.get('id') if nodo_elegido else 'fallback-local'}")

    if payload.stream:
        # Generador único con manejo de error interno
        async def _stream_con_fallback():
            ollama_url = nodo_elegido["ollama_url"] if nodo_elegido else None
            try:
                if ollama_url:
                    async for chunk in orquestador.proxy_chat_stream(
                        ollama_url, payload.model,
                        [m.model_dump() for m in payload.messages],
                        http_client_chat,
                    ):
                        yield chunk
                    return
            except Exception as exc:
                _log.getLogger("uvicorn").warning(f"[stream] Fallo en nodo ({exc}), usando fallback local")
            # Fallback directo a Ollama local
            async for chunk in ollama_chat_stream(payload.model, [m.model_dump() for m in payload.messages]):
                yield chunk

        return StreamingResponse(_stream_con_fallback(), media_type="text/event-stream")


    # Modo Normal (Sin stream)
    if nodo_elegido:
        try:
            ollama_resp = await orquestador.proxy_chat(
                nodo_elegido["ollama_url"],
                payload.model,
                [m.model_dump() for m in payload.messages],
                http_client_chat,
            )
            origen = nodo_elegido["id"]
        except Exception:
            # Fallback al Ollama local si el nodo falla durante la petición
            ollama_resp = await ollama_chat(payload.model, [m.model_dump() for m in payload.messages])
            origen = "local-fallback"
    else:
        ollama_resp = await ollama_chat(payload.model, [m.model_dump() for m in payload.messages])
        origen = "local"

    latency_ms = int((time.perf_counter() - started_at) * 1000)

    assistant_text = ollama_resp.get("message", {}).get("content", "")
    prompt_tokens = int(ollama_resp.get("prompt_eval_count") or 0)
    completion_tokens = int(ollama_resp.get("eval_count") or 0)
    save_message(
        conv_id,
        "assistant",
        assistant_text,
        model=payload.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
    )

    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex[:16]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.model,
            "conversation_id": conv_id,
            "node": origen,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": assistant_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": latency_ms,
        }
    )

@app.get("/api/status")
async def api_status(user_data: dict[str, Any] = Depends(cookie_auth_required)):
    models = await fetch_models()
    ollama_ok = not (models and str(models[0].get("id", "")).startswith("error:"))
    return {
        "ollama_ok": ollama_ok,
        "ollama_url": OLLAMA_BASE_URL,
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
    }

@app.post("/v1/completions")
async def completions(payload: CompletionRequest, user_data: dict[str, Any] = Depends(api_key_required)):

    # Verificar que el modelo del request coincida con el vinculado a la key
    validate_model_access(user_data, payload.model)

    conv_id = payload.conversation_id or str(uuid.uuid4())
    ensure_conversation(conv_id, user_data["id"], payload.title, payload.client_id)
    save_message(conv_id, "user", payload.prompt, model=payload.model)

    # Seleccionar nodo con más recursos libres; si no hay, usar Ollama local
    nodo_elegido = orquestador.best_node()
    started_at = time.perf_counter()

    if nodo_elegido:
        try:
            ollama_resp = await orquestador.proxy_chat(
                nodo_elegido["ollama_url"],
                payload.model,
                [{"role": "user", "content": payload.prompt}],
                http_client_chat,
            )
            origen = nodo_elegido["id"]
        except Exception:
            ollama_resp = await ollama_chat(payload.model, [{"role": "user", "content": payload.prompt}])
            origen = "local-fallback"
    else:
        ollama_resp = await ollama_chat(payload.model, [{"role": "user", "content": payload.prompt}])
        origen = "local"

    latency_ms = int((time.perf_counter() - started_at) * 1000)

    assistant_text = ollama_resp.get("message", {}).get("content", "")
    prompt_tokens = int(ollama_resp.get("prompt_eval_count") or 0)
    completion_tokens = int(ollama_resp.get("eval_count") or 0)
    save_message(
        conv_id,
        "assistant",
        assistant_text,
        model=payload.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
    )

    return JSONResponse(
        {
            "id": f"cmpl-{uuid.uuid4().hex[:16]}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": payload.model,
            "conversation_id": conv_id,
            "node": origen,
            "choices": [
                {
                    "index": 0,
                    "text": assistant_text,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": latency_ms,
        }
    )


async def fetch_models() -> list[dict[str, Any]]:
    # Si hay nodos online, usar sus modelos agregados
    modelos_nodos = orquestador.todos_los_modelos()
    if modelos_nodos:
        return modelos_nodos

    # Fallback: modelos del Ollama local
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        client = http_client_fast or httpx.AsyncClient(timeout=10.0)
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        return [
            {
                "id": m.get("name"),
                "object": "model",
                "owned_by": "ollama",
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at"),
            }
            for m in models
        ]
    except Exception as exc:
        return [{"id": f"error: {exc}", "object": "model", "owned_by": "system"}]


async def ollama_chat(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        client = http_client_chat or httpx.AsyncClient(timeout=120.0)
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Error de Ollama: {exc.response.text}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con Ollama: {exc}") from exc

async def ollama_chat_stream(model: str, messages: list[dict[str, str]]):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {"model": model, "messages": messages, "stream": True}
    chat_id = f"chatcmpl-{uuid.uuid4()}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            last_keepalive = time.time()

            async for chunk in response.aiter_lines():
                # Keep-alive cada 5s para que Cloudflare no corte la conexión
                now = time.time()
                if now - last_keepalive >= 5:
                    yield ": keep-alive\n\n"
                    last_keepalive = now

                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                    content = data.get("message", {}).get("content", "")
                    done = data.get("done", False)

                    openai_chunk = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content} if not done else {},
                                "finish_reason": "stop" if done else None,
                            }
                        ],
                    }
                    last_keepalive = time.time()
                    yield f"data: {json.dumps(openai_chunk)}\n\n"
                except Exception:
                    pass

        yield "data: [DONE]\n\n"
