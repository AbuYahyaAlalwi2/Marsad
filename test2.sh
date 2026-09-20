#!/bin/bash
echo "Testing All Endpoints..."
echo ""

endpoints=(
    "GET /"
    "GET /api/status"
    "POST /api/agents/deploy"
    "POST /api/swarm/deploy"
    "POST /api/ip/rotate"
    "GET /api/vault/keys"
    "GET /api/logs"
)

for endpoint in "${endpoints[@]}"; do
    method=$(echo $endpoint | cut -d' ' -f1)
    path=$(echo $endpoint | cut -d' ' -f2)
    
    echo "Testing: $method $path"
    
    if [ "$method" = "GET" ]; then
        curl -s http://localhost:5000$path
    else
        curl -s -X $method http://localhost:5000$path \
            -H "Content-Type: application/json" \
            -d '{"count": 100}'
    fi
    
    echo ""
    echo "---"
done

echo "All tests complete!"
