# Enterprise AI Knowledge Assistant
[![CI/CD](https://github.com/sr2801x/rag_know/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/sr2801x/rag_know/actions/workflows/ci-cd.yml)

Upload PDFs and ask questions grounded in their contents, with inline page citations.

## What the application does

1. The React interface uploads a PDF to the FastAPI backend.
2. The backend extracts text, splits it into overlapping chunks, and creates local embeddings with `sentence-transformers/all-MiniLM-L6-v2`.
3. The NumPy vector store retrieves the most relevant chunks for a question.
4. The backend sends those excerpts to OpenRouter and returns an answer with source pages.

The current vector store is a small, file-backed implementation intended for a single backend instance. It is not a shared database for multiple replicas.

## Run the full demo with Docker Compose (recommended)

Requirements: Docker Desktop with Linux containers and Docker Compose.

From the project root in PowerShell:

```powershell
if (-not (Test-Path .\backend\.env)) { Copy-Item .\backend\.env.example .\backend\.env }
notepad .\backend\.env
```

Add your OpenRouter key to `OPENROUTER_API_KEY` in the file. The default model is `openrouter/free`; free-model availability and rate limits are controlled by OpenRouter. Do not commit `.env` or paste your key into chat.

Start the application, Prometheus, Grafana, Loki, and Grafana Alloy:

```powershell
docker compose up --build -d
docker compose ps
```

If port 8080 is already in use, choose another host port before starting:

```powershell
$env:FRONTEND_PORT = "8088"
docker compose up --build -d
```

In that case, open the application and API docs on port 8088 instead of 8080.

Open:

| Service | URL | Purpose |
| --- | --- | --- |
| Application | http://localhost:8080 | Upload PDFs and ask questions |
| API docs | http://localhost:8080/api/docs | Inspect and try the REST API |
| Prometheus | http://localhost:9090 | Check scraped application metrics |
| Grafana | http://localhost:3000 | Review the provisioned dashboard |

Grafana's local demo login is `admin` / `admin`. Change it before sharing the machine or using this setup outside a local demo. The **AI Knowledge Assistant** dashboard is provisioned automatically. Its logs panel reads container logs from Loki; Grafana Explore can also query `{job="docker"}`.

To generate dashboard data, upload a text-based PDF and ask a few questions. The first upload downloads the embedding model and may take a little while.

```powershell
docker compose logs -f backend
docker compose down
```

Named volumes keep indexed documents and monitoring data when containers stop. `docker compose down -v` removes those volumes and deletes the local demo data.

## Run in development mode

Start the backend from one PowerShell window:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Start the frontend from another window:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` requests to the backend, so the browser does not need a cross-origin API request.

## Build and deploy to Kubernetes

The manifests target a local Kubernetes cluster such as Docker Desktop Kubernetes. Enable Kubernetes in Docker Desktop and confirm a node is ready:

```powershell
kubectl get nodes
```

Build the images from the project root:

```powershell
docker build -t knowledge-assistant-backend:local .\backend
docker build -t knowledge-assistant-frontend:local .\frontend
```

If using Minikube, load the images into its image cache:

```powershell
minikube image load knowledge-assistant-backend:local
minikube image load knowledge-assistant-frontend:local
```

Create the namespace and Kubernetes secret without writing the key into a manifest:

```powershell
kubectl apply -f .\k8s\00-namespace.yaml
$openRouterSecureKey = Read-Host "OpenRouter API key" -AsSecureString
$openRouterKey = [System.Net.NetworkCredential]::new("", $openRouterSecureKey).Password
kubectl -n knowledge-assistant create secret generic assistant-secrets --from-literal="OPENROUTER_API_KEY=$openRouterKey" --dry-run=client -o yaml | kubectl apply -f -
Remove-Variable openRouterKey, openRouterSecureKey
```

Apply the app configuration, persistent volume claim, backend, and frontend:

```powershell
kubectl apply -f .\k8s\
kubectl -n knowledge-assistant get pods
kubectl -n knowledge-assistant rollout status deployment/backend
kubectl -n knowledge-assistant rollout status deployment/frontend
kubectl -n knowledge-assistant port-forward service/frontend 8080:80
```

While port-forwarding is running, open http://localhost:8080. The frontend's Nginx server forwards API traffic to the backend service. The backend is deliberately limited to one replica because the current vector index is held in process memory; its files and embedding cache use a persistent volume.

## CI/CD

The GitHub Actions workflow at `.github/workflows/ci-cd.yml` runs backend tests and builds the frontend on pull requests. Pushes to `main` also build and publish backend and frontend images to GitHub Container Registry.

Automatic Kubernetes deployment is optional. To enable it, configure the GitHub Actions variable `KUBE_DEPLOY=true` and secret `KUBE_CONFIG` for a cluster that can pull the published images. Create the `assistant-secrets` Secret in that cluster first. If the GHCR packages are private, configure an image-pull secret in the cluster or make the packages public.

## Monitoring and logs

The FastAPI service exposes `/health` and Prometheus metrics at `/metrics`. Docker Compose scrapes the metrics with Prometheus. Grafana is provisioned with panels for request rate, HTTP p95 latency, upload outcomes, question outcomes, retrieval/LLM p95 latency, and container logs. Grafana Alloy collects Docker logs and forwards them to Loki.

## Assessment demo and presentation

1. Explain the architecture and the PDF-to-answer flow.
2. Upload a PDF and ask a question whose answer is present; point out the page citation.
3. Ask a question the PDF cannot answer and show that the assistant says it could not find the answer in the documents.
4. Show the API routes and `/health` in the FastAPI docs.
5. Show the Docker containers and the Kubernetes pods/services.
6. Open the Grafana dashboard and explain one latency panel and one error/outcome panel.
7. Review the GitHub Actions run and explain the single-replica/persistent-storage design choice.

## API endpoints

`POST /upload`, `POST /ask`, `GET /documents`, `DELETE /documents/{id}`, `GET /health`, and `GET /metrics`.


[def]: https://github.com/sr2801x/rag_know/actions/workflows/ci-cd.yml/badge.svg