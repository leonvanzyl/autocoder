#!/bin/bash
cd "$(dirname "$0")"

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo ""
echo "========================================"
echo "  Autonomous Coding Agent"
echo "========================================"
echo ""

# Check for custom API authentication (ANTHROPIC_AUTH_TOKEN)
if [ -n "$ANTHROPIC_AUTH_TOKEN" ]; then
    echo "[OK] Using custom API authentication"
    echo "    ANTHROPIC_AUTH_TOKEN is set"
    if [ -n "$ANTHROPIC_BASE_URL" ]; then
        echo "    ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
    fi
    echo ""
else
    # No custom API - check for Claude CLI
    echo "Checking for Claude CLI..."
    if ! command -v claude &> /dev/null; then
        echo "[ERROR] Claude CLI not found"
        echo ""
        echo "You have two options:"
        echo ""
        echo "1. Install Claude CLI (recommended):"
        echo "   curl -fsSL https://claude.ai/install.sh | bash"
        echo "   Then run 'claude login' to authenticate."
        echo ""
        echo "2. Use API token authentication:"
        echo "   Create a .env file with:"
        echo "     ANTHROPIC_AUTH_TOKEN=your-token-here"
        echo "     ANTHROPIC_BASE_URL=https://api.example.com/api/anthropic"
        echo ""
        exit 1
    fi

    echo "[OK] Claude CLI found"

    # Check if user has credentials
    CLAUDE_CREDS="$HOME/.claude/.credentials.json"
    if [ -f "$CLAUDE_CREDS" ]; then
        echo "[OK] Claude credentials found"
    else
        echo "[!] Not authenticated with Claude"
        echo ""
        echo "You need to run 'claude login' to authenticate."
        echo "This will open a browser window to sign in."
        echo ""
        read -p "Would you like to run 'claude login' now? (y/n): " LOGIN_CHOICE

        if [[ "$LOGIN_CHOICE" =~ ^[Yy]$ ]]; then
            echo ""
            echo "Running 'claude login'..."
            echo "Complete the login in your browser, then return here."
            echo ""
            claude login

            # Check if login succeeded
            if [ -f "$CLAUDE_CREDS" ]; then
                echo ""
                echo "[OK] Login successful!"
            else
                echo ""
                echo "[ERROR] Login failed or was cancelled."
                echo "Please try again."
                exit 1
            fi
        else
            echo ""
            echo "Please run 'claude login' manually, then try again."
            exit 1
        fi
    fi
fi

echo ""

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Run the app
python start.py
