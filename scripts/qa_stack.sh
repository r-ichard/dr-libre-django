#!/bin/sh
# Stack for a QA run in the fabro sandbox: the product on 127.0.0.1:8000 with DEBUG off,
# demo data, the worker, a mail sink, and a headless browser for the agent.
set -eu

make setup
apt-get install -y -qq chromium gh >/dev/null
mkdir -p scratch/qa

# Claude Code reads user-scope MCP servers from ~/.claude.json: the agent gets a browser.
cat > "$HOME/.claude.json" <<'EOF'
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": [
        "-y", "chrome-devtools-mcp@1.13.0", "--headless=true", "--isolated=true",
        "--executablePath=/usr/bin/chromium", "--chromeArg=--no-sandbox",
        "--chromeArg=--disable-dev-shm-usage"
      ]
    }
  }
}
EOF

manage() { uv run --env-file .env.example python manage.py "$@"; }

manage migrate --noinput >/dev/null
# The seed refuses to run with DEBUG off; the server below runs without it.
DEBUG=true manage seed_demo >/dev/null

# A script node is not an agent stage: these processes are meant to outlive it.
start() {
    name=$1
    shift
    setsid nohup "$@" > "scratch/qa/$name.log" 2>&1 < /dev/null &
}
start mail uv run --with aiosmtpd==1.4.6 python -u -m aiosmtpd -n -l 127.0.0.1:1025
start server uv run --env-file .env.example python manage.py runserver 127.0.0.1:8000 --noreload
start worker uv run --env-file .env.example python manage.py run_worker

attempts=0
until curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/health; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 60 ] || { echo "qa stack: the product did not answer" >&2; exit 1; }
    sleep 1
done
echo "qa stack: ready at http://127.0.0.1:8000, mail in scratch/qa/mail.log"
