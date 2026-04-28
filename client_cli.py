#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib import error, request

try:
    import readline
except Exception:
    readline = None


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
CONFIG_DIR = Path.home() / ".lan-llm-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
IS_WINDOWS = os.name == "nt"

COLOR_RESET = "\033[0m"
COLOR_DIM = "\033[2m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_MAGENTA = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_RED = "\033[91m"

SLASH_COMMANDS = [
    "/help",
    "/mode <ask|agent>",
    "/workspace <ruta>",
    "/approve <on|off>",
    "/model <nombre>",
    "/key <api_key>",
    "/models",
    "/new",
    "/history",
    "/context <n>",
    "/usage",
    "/update",
    "/save",
    "/status",
    "/setup",
    "/copy",
    "/clear",
    "/exit",
]

MODEL_COMPLETIONS: list[str] = []


def default_config() -> dict:
    return {
        "base_url": DEFAULT_BASE_URL,
        "api_key": "",
        "model": "",
        "max_context_messages": 12,
        "mode": "ask",
        "workspace": str(Path.cwd()),
        "auto_approve_tools": False,
    }


def enable_windows_colors() -> None:
    if IS_WINDOWS:
        os.system("")


def paint(text: str, color: str) -> str:
    return f"{color}{text}{COLOR_RESET}"


def hr(char: str = "─", width: int = 68) -> str:
    return char * width


def format_assistant_output(text: str) -> str:
    lines = text.split("\n")
    formatted = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            formatted.append(paint(line, COLOR_CYAN))
        elif in_code_block:
            if line.startswith("+"):
                formatted.append(paint(line, COLOR_GREEN))
            elif line.startswith("-"):
                formatted.append(paint(line, COLOR_RED))
            elif line.startswith("@@"):
                formatted.append(paint(line, COLOR_MAGENTA))
            else:
                formatted.append(paint(line, COLOR_YELLOW))
        else:
            formatted.append(line)
    return "\n".join(formatted)


def print_cli_header(base_url: str, model: str, client_id: str) -> None:
    logo = [
        "  __  __       _       _     ",
        " |  \\/  |     | |     | |    ",
        " | \\  / |_____| | __ _| |__  ",
        " | |\\/| |    | |/ _` | '_ \\ ",
        " | |  | |     | | (_| | |_) |",
        " |_|  |_|     |_|\\__,_|_.__/ ",
    ]
    print(paint(hr("="), COLOR_BLUE))
    for row in logo:
        print(paint(row, COLOR_BOLD + COLOR_BLUE))
    print(paint(" M-LAB CLI ", COLOR_BOLD + COLOR_CYAN))
    print(f"{paint('Base URL:', COLOR_DIM)} {base_url}")
    print(f"{paint('Modelo:', COLOR_DIM)} {model}")
    print(f"{paint('Cliente:', COLOR_DIM)} {client_id}")
    print("")
    print(paint(hr("="), COLOR_BLUE))


def print_command_help() -> None:
    print(paint("Comandos disponibles:", COLOR_BOLD + COLOR_MAGENTA))
    print(f"  {paint('/help', COLOR_CYAN)}           Mostrar ayuda")
    print(f"  {paint('/mode <ask|agent>', COLOR_CYAN)} Cambiar modo de trabajo")
    print(f"  {paint('/workspace <ruta>', COLOR_CYAN)}  Definir carpeta para modo agent")
    print(f"  {paint('/approve <on|off>', COLOR_CYAN)}  Confirmacion de herramientas")
    print(f"  {paint('/model <nombre>', COLOR_CYAN)} Cambiar modelo actual")
    print(f"  {paint('/key <api_key|new>', COLOR_CYAN)}  Cambiar API key o generar nueva")
    print(f"  {paint('/models', COLOR_CYAN)}         Listar modelos disponibles")
    print(f"  {paint('/new', COLOR_CYAN)}            Iniciar nueva conversacion")
    print(f"  {paint('/history', COLOR_CYAN)}        Ver resumen de historial actual")
    print(f"  {paint('/context <n>', COLOR_CYAN)}    Ajustar contexto para mas velocidad")
    print(f"  {paint('/usage', COLOR_CYAN)}          Ver uso global del gateway")
    print(f"  {paint('/update', COLOR_CYAN)}         Actualizar CLI desde servidor")
    print(f"  {paint('/save', COLOR_CYAN)}           Guardar modelo/key en config local")
    print(f"  {paint('/status', COLOR_CYAN)}         Ver estado rapido")
    print(f"  {paint('/setup', COLOR_CYAN)}          Ejecutar configuracion interactiva")
    print(f"  {paint('/copy', COLOR_CYAN)}           Copiar la ultima respuesta de la IA")
    print(f"  {paint('/clear', COLOR_CYAN)}          Limpiar pantalla")
    print(f"  {paint('/exit', COLOR_CYAN)}           Salir")


def render_status_compact(cfg: dict, current_model: str) -> None:
    masked = "no configurada"
    if cfg.get("api_key"):
        k = cfg["api_key"]
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***"
    print(paint(hr(), COLOR_DIM))
    print(f"{paint('URL', COLOR_DIM)}: {cfg.get('base_url') or DEFAULT_BASE_URL}")
    print(f"{paint('API key', COLOR_DIM)}: {masked}")
    print(f"{paint('Modelo', COLOR_DIM)}: {current_model or 'no configurado'}")
    print(paint(hr(), COLOR_DIM))


def setup_slash_completer() -> None:
    if readline is None:
        return
        
    hist_file = CONFIG_DIR / ".history"
    try:
        readline.read_history_file(str(hist_file))
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
    import atexit
    atexit.register(readline.write_history_file, str(hist_file))

    commands = [item.split(" ")[0].lstrip("/") for item in SLASH_COMMANDS]

    def completer(text: str, state: int):
        buffer = readline.get_line_buffer()
        if not buffer.startswith("/"):
            return None
        # Autocompletado contextual para /model <nombre>.
        if buffer.startswith("/model "):
            raw_model_prefix = buffer[len("/model ") :].strip()
            options = [m for m in MODEL_COMPLETIONS if m.startswith(raw_model_prefix)]
            if state < len(options):
                return options[state]
            return None
        word = buffer[readline.get_begidx() : readline.get_endidx()]
        prefix = (word or buffer).lstrip("/")
        options = [cmd for cmd in commands if cmd.startswith(prefix)]
        return options[state] if state < len(options) else None

    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)


def pick_model_interactive(current_model: str) -> str | None:
    if not MODEL_COMPLETIONS:
        print(paint("No hay modelos cargados para seleccionar.", COLOR_RED))
        return None
    print(paint("Selector de modelo (ENTER para mantener actual, /cancel para salir)", COLOR_CYAN))
    print(paint(f"Modelo actual: {current_model}", COLOR_DIM))
    filtered = MODEL_COMPLETIONS[:]
    while True:
        query = input(paint("Filtro modelo > ", COLOR_BOLD + COLOR_GREEN)).strip()
        if not query:
            return current_model
        if query.lower() in ("/cancel", "cancel", "salir"):
            return None
        filtered = [m for m in MODEL_COMPLETIONS if query.lower() in m.lower()]
        if not filtered:
            print(paint("Sin coincidencias, intenta otro filtro.", COLOR_YELLOW))
            continue
        print(paint(hr(), COLOR_DIM))
        for idx, m in enumerate(filtered[:20], start=1):
            print(f" {idx:>2}. {m}")
        print(paint(hr(), COLOR_DIM))
        choice = input(paint("Elige numero o escribe mas filtro > ", COLOR_BOLD + COLOR_GREEN)).strip()
        if not choice:
            continue
        if choice.isdigit():
            pos = int(choice)
            if 1 <= pos <= min(20, len(filtered)):
                return filtered[pos - 1]
            print(paint("Numero fuera de rango.", COLOR_RED))
            continue
        # Si no es numero, se toma como nuevo query.
        query = choice
        filtered = [m for m in MODEL_COMPLETIONS if query.lower() in m.lower()]
        if len(filtered) == 1:
            return filtered[0]
        if filtered:
            print(paint("Coincidencias parciales encontradas, afina filtro.", COLOR_DIM))
        else:
            print(paint("Sin coincidencias con ese filtro.", COLOR_YELLOW))


def spinner_while_thinking(stop_event: threading.Event) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0
    while not stop_event.is_set():
        frame = frames[idx % len(frames)]
        sys.stdout.write(f"\r{paint(f'{frame} pensando...', COLOR_YELLOW)}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.09)
    sys.stdout.write("\r" + (" " * 56) + "\r")
    sys.stdout.flush()


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return default_config()
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_config()


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def prompt_value(label: str, current: str = "", required: bool = False) -> str:
    while True:
        suffix = f" [{current}]" if current else ""
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if current:
            return current
        if not required:
            return ""
        print("Este valor es requerido.")


def resolve_safe_path(workspace: Path, user_path: str) -> Path:
    path = Path(user_path)
    full = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
    if workspace not in [full, *full.parents]:
        raise RuntimeError("Ruta fuera del workspace permitido")
    return full


def tool_list_files(workspace: Path, rel_path: str = ".") -> str:
    target = resolve_safe_path(workspace, rel_path)
    if not target.exists():
        return f"No existe: {target}"
    if target.is_file():
        return str(target.relative_to(workspace))
    items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = []
    for p in items[:200]:
        marker = "F" if p.is_file() else "D"
        lines.append(f"[{marker}] {p.relative_to(workspace)}")
    return "\n".join(lines) if lines else "(vacio)"


def tool_read_file(workspace: Path, rel_path: str) -> str:
    target = resolve_safe_path(workspace, rel_path)
    if not target.exists() or not target.is_file():
        return f"Archivo no encontrado: {rel_path}"
    return target.read_text(encoding="utf-8", errors="replace")[:120000]


def tool_write_file(workspace: Path, rel_path: str, content: str) -> str:
    target = resolve_safe_path(workspace, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Archivo escrito: {target.relative_to(workspace)} ({len(content)} chars)"


def tool_append_file(workspace: Path, rel_path: str, content: str) -> str:
    target = resolve_safe_path(workspace, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(content)
    return f"Archivo actualizado: {target.relative_to(workspace)} (+{len(content)} chars)"


def tool_mkdir(workspace: Path, rel_path: str) -> str:
    target = resolve_safe_path(workspace, rel_path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Directorio creado/listo: {target.relative_to(workspace)}"


def tool_search(workspace: Path, pattern: str, rel_path: str = ".") -> str:
    target = resolve_safe_path(workspace, rel_path)
    try:
        cmd = ["rg", "-n", "--hidden", "--glob", "!.git", pattern, str(target)]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out[:120000] if out else "(sin resultados)"
    except subprocess.CalledProcessError as exc:
        return (exc.output or "").strip() or "(sin resultados)"


def execute_tool_call(workspace: Path, tool_name: str, args: dict) -> str:
    if tool_name == "list_files":
        return tool_list_files(workspace, args.get("path", "."))
    if tool_name == "read_file":
        return tool_read_file(workspace, args.get("path", ""))
    if tool_name == "write_file":
        return tool_write_file(workspace, args.get("path", ""), args.get("content", ""))
    if tool_name == "append_file":
        return tool_append_file(workspace, args.get("path", ""), args.get("content", ""))
    if tool_name == "mkdir":
        return tool_mkdir(workspace, args.get("path", ""))
    if tool_name == "search":
        return tool_search(workspace, args.get("pattern", ""), args.get("path", "."))
    raise RuntimeError(f"Herramienta no soportada: {tool_name}")


def parse_tool_call(text: str) -> dict | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if isinstance(data, dict) and data.get("tool"):
        if "args" not in data or not isinstance(data.get("args"), dict):
            data["args"] = {}
        return data
    return None

def api_call(method: str, url: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Error de conexion: {exc}") from exc


def auth_api_call(method: str, url: str, payload: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Error de conexion: {exc}") from exc


def cmd_update(_: argparse.Namespace) -> None:
    cfg = load_config()
    base_url = cfg.get("base_url") or DEFAULT_BASE_URL
    server_base = base_url.rsplit("/v1", 1)[0] if base_url.endswith("/v1") else base_url
    target_path = Path(__file__).resolve()
    url = f"{server_base}/install/client_cli.py?ts={int(time.time() * 1000)}"
    print(paint(f"Actualizando CLI desde: {url}", COLOR_DIM))
    try:
        req = request.Request(
            url=url,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            method="GET",
        )
        with request.urlopen(req, timeout=120) as resp:
            content = resp.read().decode("utf-8")
        old_content = ""
        if target_path.exists():
            old_content = target_path.read_text(encoding="utf-8")
        old_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest() if old_content else ""
        new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if old_hash == new_hash:
            print(paint("CLI ya esta actualizado (sin cambios remotos).", COLOR_YELLOW))
            return

        target_path.write_text(content, encoding="utf-8")
        print(paint("CLI actualizado correctamente (nueva version aplicada).", COLOR_GREEN))
        print(paint(f"Archivo: {target_path}", COLOR_DIM))
        print(paint("Recargando CLI para usar la nueva version...", COLOR_CYAN))
        os.execv(sys.executable, [sys.executable, str(target_path), *sys.argv[1:]])
    except Exception as exc:
        print(paint(f"No se pudo actualizar el CLI: {exc}", COLOR_RED))


def cmd_init(args: argparse.Namespace) -> None:
    cfg = load_config()
    if args.base_url:
        cfg["base_url"] = args.base_url.rstrip("/")
    if args.api_key:
        cfg["api_key"] = args.api_key.strip()
    if args.model:
        cfg["model"] = args.model.strip()
    if args.max_context_messages is not None:
        cfg["max_context_messages"] = max(2, int(args.max_context_messages))
    if args.mode:
        cfg["mode"] = args.mode
    if args.workspace:
        cfg["workspace"] = str(Path(args.workspace).resolve())
    if args.auto_approve_tools is not None:
        cfg["auto_approve_tools"] = args.auto_approve_tools
    save_config(cfg)
    print(f"Configuracion guardada en: {CONFIG_FILE}")


def cmd_setup(_: argparse.Namespace) -> None:
    cfg = load_config()
    print(paint("Configuracion inicial LAN LLM CLI", COLOR_BOLD + COLOR_CYAN))
    
    base_url = prompt_value("Base URL", cfg.get("base_url") or DEFAULT_BASE_URL, required=True).rstrip("/")
    cfg["base_url"] = base_url
    server_base = base_url.rsplit("/v1", 1)[0] if base_url.endswith("/v1") else base_url
    
    print(paint("\nAutenticacion requerida.", COLOR_YELLOW))
    action = prompt_value("¿Que deseas hacer? (login/register)", "login", required=True).lower()
    
    username = prompt_value("Usuario", "", required=True)
    import getpass
    password = getpass.getpass("Contraseña: ")
    
    try:
        endpoint = f"{server_base}/api/auth/{action}"
        resp = auth_api_call("POST", endpoint, {"username": username, "password": password})
        cfg["api_key"] = resp.get("api_key", "")
        print(paint(f"¡{action.capitalize()} exitoso! API key guardada.", COLOR_GREEN))
    except Exception as exc:
        print(paint(f"Error en {action}: {exc}", COLOR_RED))
        return

    cfg["model"] = prompt_value("Modelo por defecto", cfg.get("model", ""), required=True)
    cfg["mode"] = prompt_value("Modo por defecto (ask/agent)", cfg.get("mode", "ask"), required=True).lower()
    cfg["workspace"] = prompt_value(
        "Workspace para modo agent",
        cfg.get("workspace", str(Path.cwd())),
        required=True,
    )
    approve = prompt_value(
        "Auto aprobar herramientas en agent (on/off)",
        "on" if cfg.get("auto_approve_tools") else "off",
        required=True,
    ).lower()
    cfg["auto_approve_tools"] = approve in ("on", "true", "1", "yes", "si", "s")
    raw_context = prompt_value(
        "Maximo de mensajes de contexto",
        str(cfg.get("max_context_messages", 12)),
        required=True,
    )
    try:
        cfg["max_context_messages"] = max(2, int(raw_context))
    except ValueError:
        cfg["max_context_messages"] = 12
    if "admin_token" in cfg:
        del cfg["admin_token"]
    save_config(cfg)
    print(f"Configuracion guardada en: {CONFIG_FILE}")


def cmd_status(_: argparse.Namespace) -> None:
    cfg = load_config()
    masked = ""
    if cfg.get("api_key"):
        k = cfg["api_key"]
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***"
    print("Estado CLI")
    print(f"- Config: {CONFIG_FILE}")
    print(f"- Base URL: {cfg.get('base_url') or DEFAULT_BASE_URL}")
    print(f"- API key: {masked or 'no configurada'}")
    print(f"- Modelo por defecto: {cfg.get('model') or 'no configurado'}")
    print(f"- Max context mensajes: {cfg.get('max_context_messages', 12)}")
    print(f"- Modo: {cfg.get('mode', 'ask')}")
    print(f"- Workspace: {cfg.get('workspace', str(Path.cwd()))}")
    print(f"- Auto approve tools: {'on' if cfg.get('auto_approve_tools') else 'off'}")


def cmd_models(_: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg.get("api_key"):
        print("Primero configura la CLI con: lanllm setup")
        return
    data = api_call("GET", f"{cfg['base_url']}/models", cfg["api_key"])
    models = data.get("data", [])
    if not models:
        print("No se encontraron modelos.")
        return
    print("Modelos disponibles:")
    for item in models:
        print(f"- {item.get('id')}")


def cmd_usage(_: argparse.Namespace) -> None:
    cfg = load_config()
    base_url = cfg.get("base_url") or DEFAULT_BASE_URL
    api_key = cfg.get("api_key", "")
    server_base = base_url.rsplit("/v1", 1)[0] if base_url.endswith("/v1") else base_url
    try:
        usage_data = api_call("GET", f"{server_base}/api/usage", api_key)
        print(
            f"Uso global: conv={usage_data.get('conversations', 0)} "
            f"msg={usage_data.get('messages', 0)} "
            f"tokens={usage_data.get('total_tokens', 0)}"
        )
    except Exception as exc:
        print(f"No se pudo obtener usage. Verifica tu sesion. Error: {exc}")


def run_agent_turn(
    base_url: str,
    api_key: str,
    model: str,
    conversation_id: str,
    history: list[dict[str, str]],
    workspace: Path,
    auto_approve_tools: bool,
    max_context_messages: int,
) -> tuple[str, list[dict[str, str]]]:
    agent_system = {
        "role": "system",
        "content": (
            "Eres un agente de codigo con herramientas locales. "
            "Si necesitas usar herramienta, responde SOLO JSON con formato: "
            '{"tool":"read_file|write_file|append_file|list_files|mkdir|search","args":{...}}. '
            "Si ya terminaste, responde texto normal sin JSON."
        ),
    }
    working = history[:]
    max_steps = 6
    for _ in range(max_steps):
        messages_to_send = [agent_system] + working[-max_context_messages:]
        payload = {
            "model": model,
            "messages": messages_to_send,
            "conversation_id": conversation_id,
            "client_id": "cli-agent",
            "title": "Sesion Agent CLI",
        }
        response = api_call("POST", f"{base_url}/chat/completions", api_key, payload)
        assistant = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        tool_call = parse_tool_call(assistant)
        working.append({"role": "assistant", "content": assistant})
        if tool_call is None:
            return assistant, working

        tool_name = tool_call.get("tool", "")
        args = tool_call.get("args", {})
        if not auto_approve_tools:
            decision = input(
                paint(f"Herramienta solicitada: {tool_name} args={args} ¿ejecutar? [y/N]: ", COLOR_YELLOW)
            ).strip().lower()
            if decision not in ("y", "yes", "s", "si"):
                result = "Ejecucion cancelada por usuario"
            else:
                result = execute_tool_call(workspace, tool_name, args)
        else:
            result = execute_tool_call(workspace, tool_name, args)

        tool_result = f"TOOL_RESULT {tool_name}: {result}"
        print(paint(f"tool> {tool_name}", COLOR_CYAN))
        working.append({"role": "user", "content": tool_result})

    return "No se pudo finalizar: se alcanzo el maximo de pasos de agente.", working


def cmd_chat(args: argparse.Namespace) -> None:
    enable_windows_colors()
    setup_slash_completer()
    cfg = load_config()
    base_url = cfg.get("base_url") or DEFAULT_BASE_URL
    api_key = cfg.get("api_key") or ""
    selected_model = getattr(args, "model", None)
    client_id = getattr(args, "client_id", os.getenv("HOSTNAME", "cli-client"))
    title = getattr(args, "title", "Sesion CLI")
    model = selected_model or cfg.get("model") or ""
    max_context_messages = int(cfg.get("max_context_messages", 12))
    mode = cfg.get("mode", "ask")
    workspace = Path(cfg.get("workspace", str(Path.cwd()))).resolve()
    auto_approve_tools = bool(cfg.get("auto_approve_tools", False))

    if not api_key:
        print("No hay API key configurada. Iniciando setup...")
        cmd_setup(args)
        cfg = load_config()
        base_url = cfg.get("base_url") or DEFAULT_BASE_URL
        api_key = cfg.get("api_key") or ""
        model = selected_model or cfg.get("model") or ""
    if not model:
        print("No hay modelo configurado. Ejecuta: lanllm setup")
        return

    # Precarga modelos para autocompletar en /model <TAB>.
    try:
        global MODEL_COMPLETIONS
        model_data = api_call("GET", f"{base_url}/models", api_key)
        MODEL_COMPLETIONS = [str(item.get("id")) for item in model_data.get("data", []) if item.get("id")]
    except Exception:
        MODEL_COMPLETIONS = []

    print_cli_header(base_url, model, client_id)
    print(paint("Tip: escribe '/' y presiona TAB para autocompletar comandos.", COLOR_DIM))
    print(paint(f"Contexto activo: ultimos {max_context_messages} mensajes", COLOR_DIM))
    print(paint(f"Modo actual: {mode} | Workspace: {workspace}", COLOR_DIM))
    print_command_help()
    conversation_id = str(uuid.uuid4())
    history: list[dict[str, str]] = []

    while True:
        try:
            user_text = input(paint("\nTu > ", COLOR_BOLD + COLOR_GREEN)).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{paint('Sesion finalizada.', COLOR_YELLOW)}")
            return

        if not user_text:
            continue
        if user_text.startswith("/") and user_text.strip() == "/":
            print_command_help()
            continue
        if user_text == "/exit":
            print(paint("Sesion finalizada.", COLOR_YELLOW))
            return
        if user_text == "/help":
            print_command_help()
            continue
        if user_text.startswith("/mode "):
            raw_mode = user_text.split(" ", 1)[1].strip().lower()
            if raw_mode not in ("ask", "agent"):
                print(paint("Modo invalido. Usa /mode ask o /mode agent", COLOR_RED))
                continue
            mode = raw_mode
            cfg["mode"] = mode
            print(paint(f"Modo cambiado a: {mode}", COLOR_CYAN))
            continue
        if user_text.startswith("/workspace "):
            raw_ws = user_text.split(" ", 1)[1].strip()
            new_ws = Path(raw_ws).expanduser().resolve()
            if not new_ws.exists() or not new_ws.is_dir():
                print(paint("Workspace invalido (no existe o no es carpeta).", COLOR_RED))
                continue
            workspace = new_ws
            cfg["workspace"] = str(workspace)
            print(paint(f"Workspace cambiado a: {workspace}", COLOR_CYAN))
            continue
        if user_text.startswith("/approve "):
            raw = user_text.split(" ", 1)[1].strip().lower()
            if raw not in ("on", "off"):
                print(paint("Usa /approve on u /approve off", COLOR_RED))
                continue
            auto_approve_tools = raw == "on"
            cfg["auto_approve_tools"] = auto_approve_tools
            print(paint(f"Auto approve tools: {'on' if auto_approve_tools else 'off'}", COLOR_CYAN))
            continue
        if user_text == "/model":
            selected = pick_model_interactive(model)
            if selected is not None:
                model = selected
                print(paint(f"Modelo cambiado a: {model}", COLOR_CYAN))
            continue
        if user_text.startswith("/model "):
            raw_model = user_text.split(" ", 1)[1].strip()
            matches = [m for m in MODEL_COMPLETIONS if raw_model.lower() in m.lower()]
            if len(matches) == 1:
                model = matches[0]
                print(paint(f"Modelo cambiado a: {model}", COLOR_CYAN))
            elif len(matches) > 1:
                print(paint("Coincidencias encontradas:", COLOR_MAGENTA))
                for m in matches[:20]:
                    print(f" - {m}")
                print(paint("Usa /model y el selector para elegir.", COLOR_DIM))
            else:
                model = raw_model
                print(paint(f"Modelo cambiado a: {model}", COLOR_CYAN))
            continue
        if user_text.startswith("/models"):
            try:
                data = api_call("GET", f"{base_url}/models", api_key)
                print(paint(hr(), COLOR_DIM))
                print(paint("Modelos disponibles:", COLOR_BOLD + COLOR_MAGENTA))
                models = data.get("data", [])
                if not models:
                    print(" (sin modelos disponibles)")
                for item in models:
                    print(f" - {item.get('id')}")
                print(paint(hr(), COLOR_DIM))
            except Exception as exc:
                print(paint(f"No se pudo listar modelos: {exc}", COLOR_RED))
            continue
        if user_text.startswith("/key "):
            new_key_val = user_text.split(" ", 1)[1].strip()
            if new_key_val.lower() == "new":
                try:
                    admin_url = f"{base_url.rsplit('/v1', 1)[0]}/api/keys"
                    resp = api_call("POST", admin_url, api_key, {"name": "CLI Auto Generated"})
                    new_api_key = resp.get("api_key")
                    cfg["api_key"] = new_api_key
                    save_config(cfg)
                    api_key = new_api_key
                    print(paint(f"Nueva API key generada y guardada en config: {api_key}", COLOR_GREEN))
                except Exception as exc:
                    print(paint(f"No se pudo generar API key: {exc}", COLOR_RED))
            else:
                api_key = new_key_val
                cfg["api_key"] = api_key
                save_config(cfg)
                print(paint("API key actualizada en memoria y guardada en config.", COLOR_CYAN))
            continue
        if user_text.startswith("/context "):
            raw_n = user_text.split(" ", 1)[1].strip()
            try:
                max_context_messages = max(2, int(raw_n))
                cfg["max_context_messages"] = max_context_messages
                print(paint(f"Contexto ajustado a {max_context_messages} mensajes.", COLOR_CYAN))
            except ValueError:
                print(paint("Valor invalido. Usa /context 12", COLOR_RED))
            continue
        if user_text == "/new":
            conversation_id = str(uuid.uuid4())
            history = []
            print(paint("Nueva conversacion iniciada.", COLOR_CYAN))
            continue
        if user_text == "/history":
            turns = len([m for m in history if m.get("role") == "user"])
            print(paint(hr(), COLOR_DIM))
            print(f"{paint('Historial', COLOR_BOLD + COLOR_MAGENTA)} turnos={turns} mensajes={len(history)}")
            print(paint(hr(), COLOR_DIM))
            continue
        if user_text == "/save":
            cfg["model"] = model
            cfg["api_key"] = api_key
            cfg["mode"] = mode
            cfg["workspace"] = str(workspace)
            cfg["auto_approve_tools"] = auto_approve_tools
            cfg["max_context_messages"] = max_context_messages
            save_config(cfg)
            print(paint(f"Configuracion guardada en: {CONFIG_FILE}", COLOR_CYAN))
            continue
        if user_text == "/update":
            cmd_update(args)
            continue
        if user_text == "/usage":
            try:
                server_base = base_url.rsplit('/v1', 1)[0] if base_url.endswith("/v1") else base_url
                usage_data = api_call("GET", f"{server_base}/api/usage", api_key)
                print(paint(hr(), COLOR_DIM))
                print(
                    f"{paint('Uso global', COLOR_BOLD + COLOR_MAGENTA)} "
                    f"conv={usage_data.get('conversations', 0)} "
                    f"msg={usage_data.get('messages', 0)} "
                    f"tokens={usage_data.get('total_tokens', 0)}"
                )
                print(paint(hr(), COLOR_DIM))
            except Exception as exc:
                print(paint(f"No se pudo obtener usage. Error: {exc}", COLOR_RED))
            continue
        if user_text == "/status":
            cfg["model"] = model
            cfg["api_key"] = api_key
            render_status_compact(cfg, model)
            continue
        if user_text == "/setup":
            cmd_setup(args)
            cfg = load_config()
            base_url = cfg.get("base_url") or DEFAULT_BASE_URL
            api_key = cfg.get("api_key") or ""
            model = cfg.get("model") or model
            admin_token = cfg.get("admin_token", "")
            max_context_messages = int(cfg.get("max_context_messages", 12))
            mode = cfg.get("mode", "ask")
            workspace = Path(cfg.get("workspace", str(Path.cwd()))).resolve()
            auto_approve_tools = bool(cfg.get("auto_approve_tools", False))
            print(paint("Configuracion recargada.", COLOR_CYAN))
            continue
        if user_text == "/copy":
            if not history or history[-1].get("role") != "assistant":
                print(paint("No hay una respuesta reciente de la IA para copiar.", COLOR_YELLOW))
                continue
            last_text = history[-1].get("content", "")
            try:
                subprocess.run("clip", input=last_text, text=True, check=True)
                print(paint("Respuesta copiada al portapapeles.", COLOR_GREEN))
            except Exception as e:
                print(paint(f"Error al copiar: {e}", COLOR_RED))
            continue
        if user_text == "/clear":
            os.system("cls" if IS_WINDOWS else "clear")
            print_cli_header(base_url, model, client_id)
            continue
        if user_text.startswith("/"):
            print(paint("Comando no reconocido. Usa /help", COLOR_RED))
            continue

        history.append({"role": "user", "content": user_text})
        started_at = time.perf_counter()
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=spinner_while_thinking, args=(stop_event,), daemon=True)
        spinner_thread.start()
        try:
            if mode == "agent":
                assistant, history = run_agent_turn(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    conversation_id=conversation_id,
                    history=history,
                    workspace=workspace,
                    auto_approve_tools=auto_approve_tools,
                    max_context_messages=max_context_messages,
                )
            else:
                messages_to_send = history[-max_context_messages:]
                payload = {
                    "model": model,
                    "messages": messages_to_send,
                    "conversation_id": conversation_id,
                    "client_id": client_id,
                    "title": title,
                }
                response = api_call("POST", f"{base_url}/chat/completions", api_key, payload)
                assistant = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                history.append({"role": "assistant", "content": assistant})
        except Exception as exc:
            stop_event.set()
            spinner_thread.join(timeout=1.0)
            print(paint(f"Error > {exc}", COLOR_RED))
            history.pop()
            continue
        finally:
            stop_event.set()
            spinner_thread.join(timeout=1.0)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        print(paint(hr(), COLOR_DIM))
        print(f"{paint('IA >', COLOR_BOLD + COLOR_MAGENTA)}\n{format_assistant_output(assistant)}")
        print(paint(f"T: {elapsed_ms} ms", COLOR_DIM))
        print(paint(hr(), COLOR_DIM))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lanllm",
        description="Cliente CLI simple para LAN LLM API Gateway",
    )
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Guardar base_url, api_key y modelo")
    p_init.add_argument("--base-url", help="Ej: http://192.168.1.50:8000/v1")
    p_init.add_argument("--api-key", help="API key lan_...")
    p_init.add_argument("--model", help="Modelo por defecto")
    p_init.add_argument("--admin-token", help="Token admin opcional para /usage")
    p_init.add_argument("--max-context-messages", type=int, help="Mensajes maximos para acelerar respuestas")
    p_init.add_argument("--mode", choices=["ask", "agent"], help="Modo por defecto")
    p_init.add_argument("--workspace", help="Ruta de workspace para modo agent")
    p_init.add_argument(
        "--auto-approve-tools",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Aprobar automaticamente herramientas en modo agent",
    )
    p_init.set_defaults(func=cmd_init)

    p_setup = sub.add_parser("setup", help="Configuracion guiada interactiva")
    p_setup.set_defaults(func=cmd_setup)

    p_status = sub.add_parser("status", help="Ver configuracion local")
    p_status.set_defaults(func=cmd_status)

    p_models = sub.add_parser("models", help="Listar modelos disponibles")
    p_models.set_defaults(func=cmd_models)

    p_usage = sub.add_parser("usage", help="Ver uso global del gateway")
    p_usage.set_defaults(func=cmd_usage)

    p_update = sub.add_parser("update", help="Actualizar CLI desde servidor")
    p_update.set_defaults(func=cmd_update)

    p_chat = sub.add_parser("chat", help="Abrir chat interactivo en terminal")
    p_chat.add_argument("--model", help="Sobrescribe modelo por defecto")
    p_chat.add_argument("--client-id", default=os.getenv("HOSTNAME", "cli-client"))
    p_chat.add_argument("--title", default="Sesion CLI")
    p_chat.set_defaults(func=cmd_chat)

    p_run = sub.add_parser("run", help="Alias de chat")
    p_run.add_argument("--model", help="Sobrescribe modelo por defecto")
    p_run.add_argument("--client-id", default=os.getenv("HOSTNAME", "cli-client"))
    p_run.add_argument("--title", default="Sesion CLI")
    p_run.set_defaults(func=cmd_chat)

    p_start = sub.add_parser("start", help="Alias de chat")
    p_start.add_argument("--model", help="Sobrescribe modelo por defecto")
    p_start.add_argument("--client-id", default=os.getenv("HOSTNAME", "cli-client"))
    p_start.add_argument("--title", default="Sesion CLI")
    p_start.set_defaults(func=cmd_chat)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        cmd_chat(args)
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
