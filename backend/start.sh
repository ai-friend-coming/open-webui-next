#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

# Add conditional Playwright browser installation
if [[ "${WEB_LOADER_ENGINE,,}" == "playwright" ]]; then
    if [[ -z "${PLAYWRIGHT_WS_URL}" ]]; then
        echo "Installing Playwright browsers..."
        playwright install chromium
        playwright install-deps chromium
    fi

    python -c "import nltk; nltk.download('punkt_tab')"
fi

if [ -n "${WEBUI_SECRET_KEY_FILE}" ]; then
    KEY_FILE="${WEBUI_SECRET_KEY_FILE}"
else
    KEY_FILE=".webui_secret_key"
fi

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
if test "$WEBUI_SECRET_KEY $WEBUI_JWT_SECRET_KEY" = " "; then
  echo "Loading WEBUI_SECRET_KEY from file, not provided as an environment variable."

  if ! [ -e "$KEY_FILE" ]; then
    echo "Generating WEBUI_SECRET_KEY"
    # Generate a random value to use as a WEBUI_SECRET_KEY in case the user didn't provide one.
    echo $(head -c 12 /dev/random | base64) > "$KEY_FILE"
  fi

  echo "Loading WEBUI_SECRET_KEY from $KEY_FILE"
  WEBUI_SECRET_KEY=$(cat "$KEY_FILE")
fi

if [[ "${USE_OLLAMA_DOCKER,,}" == "true" ]]; then
    echo "USE_OLLAMA is set to true, starting ollama serve."
    ollama serve &
fi

if [[ "${USE_CUDA_DOCKER,,}" == "true" ]]; then
  echo "CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries."
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib/python3.11/site-packages/torch/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"
fi

# Check if SPACE_ID is set, if so, configure for space
if [ -n "$SPACE_ID" ]; then
  echo "Configuring for HuggingFace Space deployment"
  if [ -n "$ADMIN_USER_EMAIL" ] && [ -n "$ADMIN_USER_PASSWORD" ]; then
    echo "Admin user configured, creating"
    WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" uvicorn open_webui.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '*' &
    webui_pid=$!
    echo "Waiting for webui to start..."
    while ! curl -s "http://localhost:${PORT}/health" > /dev/null; do
      sleep 1
    done
    echo "Creating admin user..."
    curl \
      -X POST "http://localhost:${PORT}/api/v1/auths/signup" \
      -H "accept: application/json" \
      -H "Content-Type: application/json" \
      -d "{ \"email\": \"${ADMIN_USER_EMAIL}\", \"password\": \"${ADMIN_USER_PASSWORD}\", \"name\": \"Admin\" }"
    echo "Shutting down webui..."
    kill $webui_pid
  fi

  export WEBUI_URL=${SPACE_HOST}
fi

PYTHON_CMD=$(command -v python3 || command -v python)
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

# Run database migrations
echo "Running database migrations..."
if ! "$PYTHON_CMD" -m alembic upgrade head; then
    echo "Warning: Database migration failed. The application may not function correctly."
    echo "Please check your database connection and migration files."
fi

# Auto-fix missing invite codes (in case migration backfill failed)
echo "Checking for users without invite codes..."
"$PYTHON_CMD" << 'EOF'
import sys
from sqlalchemy import create_engine, text
from open_webui.env import DATABASE_URL

try:
    from open_webui.utils.invite import generate_invite_code

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if invite_code column exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user' AND column_name = 'invite_code'
        """))

        if not result.fetchone():
            print("INFO: invite_code column does not exist yet, skipping auto-fix")
            sys.exit(0)

        # Check for users without invite codes
        result = conn.execute(text('SELECT COUNT(*) FROM "user" WHERE invite_code IS NULL'))
        count = result.scalar()

        if count == 0:
            print(f"INFO: All users have invite codes (checked {count} users)")
            sys.exit(0)

        print(f"INFO: Found {count} users without invite codes, generating...")

        # Get users without invite codes
        result = conn.execute(text('SELECT id FROM "user" WHERE invite_code IS NULL'))
        users = result.fetchall()

        # Generate invite codes
        generated_codes = set()
        for user_row in users:
            user_id = user_row[0]

            # Generate unique invite code
            for attempt in range(10):
                invite_code = generate_invite_code(6 if attempt < 5 else 8)

                # Check if exists
                existing = conn.execute(
                    text('SELECT COUNT(*) FROM "user" WHERE invite_code = :code'),
                    {"code": invite_code}
                ).scalar()

                if existing == 0 and invite_code not in generated_codes:
                    generated_codes.add(invite_code)
                    break
            else:
                # Use 8-char code if still conflicting
                invite_code = generate_invite_code(8)

            # Update user
            conn.execute(
                text('UPDATE "user" SET invite_code = :code WHERE id = :user_id'),
                {"code": invite_code, "user_id": user_id}
            )

        conn.commit()
        print(f"SUCCESS: Generated invite codes for {len(users)} users")

except Exception as e:
    print(f"WARNING: Failed to auto-fix invite codes: {e}")
    # Don't fail the startup, just log the warning
    sys.exit(0)
EOF

# If script is called with arguments, use them; otherwise use default workers
if [ "$#" -gt 0 ]; then
    ARGS=("$@")
else
    ARGS=(--workers "$UVICORN_WORKERS")
fi

# Run uvicorn
WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" exec "$PYTHON_CMD" -m uvicorn open_webui.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips '*' \
    "${ARGS[@]}"