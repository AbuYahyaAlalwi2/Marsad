#!/bin/bash
echo "Testing Marsad Server..."
echo ""
echo "1. Root:"
curl -s http://localhost:5000/
echo ""
echo "2. Status:"
curl -s http://localhost:5000/api/status
echo ""
echo "3. Deploy Agents:"
curl -s -X POST http://localhost:5000/api/agents/deploy \
  -H "Content-Type: application/json" \
  -d '{"count": 1000}'
echo ""
echo "Done!"
