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

# Start-up refuses the published key and demo password with DEBUG off; the seed below turns DEBUG on.
QA_SAFE_KEY=qa-only-key-k7Qx9vT2mWp4Zr8LbN3cYd6HfJs1UaEg5XoVt0RiKwMq2PzBn
manage() { SECRET_KEY=$QA_SAFE_KEY DEMO_PASSWORD= uv run --env-file .env.example python manage.py "$@"; }

manage migrate --noinput >/dev/null
# The seed refuses to run with DEBUG off; the server below runs without it.
DEBUG=true SECRET_KEY=$QA_SAFE_KEY DEMO_PASSWORD=demo-password-published uv run --env-file .env.example python manage.py seed_demo >/dev/null

# A script node is not an agent stage: these processes are meant to outlive it.
start() {
    name=$1
    shift
    setsid nohup "$@" > "scratch/qa/$name.log" 2>&1 < /dev/null &
}
start mail uv run --with aiosmtpd==1.4.6 python -u -m aiosmtpd -n -l 127.0.0.1:1025
# All interfaces of the sandbox, so `fabro sandbox preview <run> 8000` can show this instance.
start server env SECRET_KEY=$QA_SAFE_KEY DEMO_PASSWORD= uv run --env-file .env.example python manage.py runserver 0.0.0.0:8000 --noreload
start worker env SECRET_KEY=$QA_SAFE_KEY DEMO_PASSWORD= uv run --env-file .env.example python manage.py run_worker

attempts=0
until curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/health; do
    attempts=$((attempts + 1))
    [ "$attempts" -lt 60 ] || { echo "qa stack: the product did not answer" >&2; exit 1; }
    sleep 1
done
echo "qa stack: ready at http://127.0.0.1:8000, mail in scratch/qa/mail.log"
