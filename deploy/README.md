# نشر Worker Nodes على السحابات

## المعمارية
Control Plane (Render) + Worker Nodes (245 clouds)
= 1,000,000 agents

## كل Worker
- 10,000 وكيل
- heartbeat كل 30 ثانية
- يُسجّل تلقائياً

## النشر

### Fly.io
fly launch --config deploy/fly.toml
fly scale count 10

### Railway
railway up --dockerfile deploy/Dockerfile.worker

### Docker المحلي
docker build -t marsad-worker -f deploy/Dockerfile.worker .
docker run -e CG_CLOUD_PROVIDER=local marsad-worker

## التوسع
1 worker = 10K agents
10 workers = 100K agents
100 workers = 1,000,000 agents
