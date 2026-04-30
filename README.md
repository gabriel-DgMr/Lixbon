# LAN LLM API Gateway para Ollama

Capa API para exponer modelos de `Ollama` en una red LAN con:

- API keys por equipo.
- Endpoint de chat estilo proveedor LLM (`/v1/chat/completions`).
- Conteo de tokens (prompt/completion/total).
- Registro de conversaciones simultaneas.
- Dashboard web simple para administracion.

## Requisitos
- Python 3.10+.
## Levantar servidor
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Instalacion

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecucion

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export ALLOWED_ORIGINS="*"
export ADMIN_TOKEN=""
export RATE_LIMIT_PER_MIN="120"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Dashboard: `http://IP_DEL_SERVIDOR:8000/`
- Health: `http://IP_DEL_SERVIDOR:8000/health`

## v1.1 pragmatica (operacion estable)

- `ADMIN_TOKEN`: si se define, bloquea acciones admin (`/admin/*`) sin header `X-Admin-Token`.
- `RATE_LIMIT_PER_MIN`: limita requests por minuto por API key en endpoints `/v1/*`.
- Panel con sidebar y seccion de integraciones para uso rapido en IDE, n8n y terminal.

## Flujo recomendado

1. Entra al dashboard y crea una API key para cada equipo LAN.
2. Cada cliente usa esa key en `Authorization: Bearer <API_KEY>`.
3. Llama al endpoint de chat.

## Ejemplo API (cliente LAN)

```bash
curl -X POST "http://IP_DEL_SERVIDOR:8000/v1/chat/completions" \
  -H "Authorization: Bearer lan_xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {"role":"user","content":"Resume este texto en 3 puntos"}
    ],
    "client_id": "pc-marketing",
    "title": "Resumen diario"
  }'
```

## Compatibilidad con apps externas

Esta API expone endpoints compatibles con estilo OpenAI:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`

Eso permite conectarla desde herramientas externas sin depender de terminal.

### n8n (local)

- Nodo: `OpenAI Chat Model` (o equivalente OpenAI).
- Base URL: `http://IP_DEL_SERVIDOR:8000/v1`
- API Key: la generada en el dashboard.
- Modelo: uno de `GET /v1/models` (ej: `llama3.1:8b`).

### IDEs / herramientas con proveedor OpenAI compatible

- API Base URL: `http://IP_DEL_SERVIDOR:8000/v1`
- API Key: `lan_...`
- Modelo: nombre exacto de Ollama.

### React + Node.js (frontend web o chat app)

- Frontend usa `fetch`/SDK hacia `http://IP_DEL_SERVIDOR:8000/v1/chat/completions`.
- Header: `Authorization: Bearer <API_KEY>`.
- Si es navegador, `ALLOWED_ORIGINS` debe incluir tu origen (`http://localhost:3000`, etc.).

Ejemplo `ALLOWED_ORIGINS`:

```bash
export ALLOWED_ORIGINS="http://localhost:3000,http://192.168.1.10:5173"
```

## Notas de red LAN

- Abre el puerto `8000` en firewall si aplica.
- Mantener `OLLAMA_BASE_URL` en localhost del servidor para no exponer Ollama directamente.
- Usa HTTPS/reverse proxy (Nginx/Caddy) si la red requiere trafico cifrado.

## Encabezado admin (si activas ADMIN_TOKEN)

Incluye este header en llamadas admin:

```text
X-Admin-Token: <ADMIN_TOKEN>
```

En el dashboard puedes guardarlo localmente en el panel lateral "Configuracion admin".

## Cliente CLI para otro PC (tipo chat terminal)

Se incluye `client_cli.py` para usar la API desde terminal en otro equipo y guardar la API key localmente.

### Instalacion en otro PC

1. Copia `client_cli.py` al otro equipo.
2. Verifica Python 3.10+.

### Configurar y guardar API key

```bash
python3 client_cli.py init \
  --base-url "http://IP_DEL_SERVIDOR:8000/v1" \
  --api-key "lan_xxxxxxxxx" \
  --model "llama3.1:8b"
```

La configuracion se guarda en:

- `~/.lan-llm-cli/config.json`

### Comprobar estado y modelos

```bash
python3 client_cli.py status
python3 client_cli.py models
```

### Usar chat interactivo

```bash
python3 client_cli.py chat
```

Comandos dentro del chat:

- `/model <nombre>` cambiar modelo en caliente.
- `/key <api_key>` cambiar key en memoria.
- `/mode ask|agent` cambiar modo conversacional o agente.
- `/workspace <ruta>` definir carpeta de trabajo para modo agente.
- `/approve on|off` activar confirmacion de herramientas.
- `/models` listar modelos disponibles.
- `/new` iniciar nueva conversacion.
- `/history` ver resumen de historial.
- `/context <n>` reducir/aumentar contexto para velocidad.
- `/usage` ver uso global (requiere token admin si aplica).
- `/update` actualizar CLI en caliente.
- `/save` guardar modelo y key para futuras sesiones.
- `/exit` salir.

## Modo agente (crear/editar archivos)

En modo `agent`, el modelo puede solicitar herramientas locales dentro del workspace configurado:

- `list_files`
- `read_file`
- `write_file`
- `append_file`
- `mkdir`
- `search`

Recomendado:

```bash
lanllm setup
# elegir mode=agent y workspace del proyecto
lanllm
```

## Instalacion remota del CLI (recomendado)

Con el gateway activo, instala el CLI desde otro PC con un solo comando:

### Linux / macOS

```bash
curl -fsSL "http://IP_DEL_SERVIDOR:8000/install.sh" | bash -s -- "http://IP_DEL_SERVIDOR:8000"
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -Command "irm 'http://IP_DEL_SERVIDOR:8000/install.ps1' | iex"
```

Despues de instalar, abre una terminal nueva y ejecuta:

```powershell
lanllm setup
lanllm chat
```

Si `lanllm` no se reconoce en la misma sesion, usa:

```powershell
& "$env:USERPROFILE\.lan-llm-cli\lanllm.cmd" status
```

Luego:

```bash
lanllm setup
lanllm chat
```

Si `lanllm` no se reconoce:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
