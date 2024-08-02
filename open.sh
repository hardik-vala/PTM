#!/bin/bash

DASHBOARD_URL="http://localhost:3000/d/bdq3qig8v6xvkc/ptm-dashboard?orgId=1"
POPULATE_DB_SCRIPT="src/populate_db.py"

echo "Populating db..."
python3 "$POPULATE_DB_SCRIPT"

if [ $? -eq 0 ]; then
    echo "Population completed successfully."
else
    echo "Population failed. Exiting."
    exit 1
fi

sleep 1

# Determine the operating system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "$DASHBOARD_URL"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$DASHBOARD_URL"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    start "$DASHBOARD_URL"
else
    echo "Unsupported operating system. Please open $DASHBOARD_URL manually."
fi
