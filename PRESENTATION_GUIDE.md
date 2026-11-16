# Enterprise AI Knowledge Assistant
## Simple presentation and viva guide

### A note before presenting

Use this guide to understand and explain the project in your own words. Keep the statements about your personal contribution accurate. If you used help or AI tools, be honest if your instructor asks or your course rules require disclosure.

## 1. Short introduction

> My project is an AI Knowledge Assistant. A user can upload PDF documents and ask questions about them. The system searches the document text, sends the most relevant parts to an AI model, and returns an answer with source pages. I also prepared Docker and Kubernetes deployment files, plus monitoring for the Docker Compose setup.

## 2. The problem and goal

Reading a long document to find one answer can take a lot of time. This application lets a user ask a question in normal language and look for the answer in uploaded PDFs.

The answer is based on the uploaded text, not just a general AI response. The application also shows source information so the user can check where the answer came from.

## 3. How the application works

### When a PDF is uploaded

1. The React web page sends the PDF to the FastAPI backend.
2. The backend checks that the file name ends in `.pdf` and extracts text from its pages.
3. The text is split into smaller, overlapping pieces called chunks. Overlap helps keep context when a useful passage crosses a chunk boundary.
4. A sentence-transformer model turns each chunk into a numeric vector, called an embedding.
5. The backend saves the chunks and vectors in files so the index can be loaded again.

### When a question is asked

1. The backend turns the question into an embedding using the same model.
2. It compares that vector with the stored document vectors and selects the closest matches using cosine similarity.
3. It sends the question and matched text to OpenRouter through an OpenAI-compatible API.
4. The model is instructed to answer only from those excerpts and to cite the filename and page.
5. The frontend displays the answer and lets the user open the matching source snippets.

If there are no uploaded documents, the API reports that instead of asking the language model to answer.

## 4. Main technologies and why they were used

| Technology | What it does | Why it fits this project |
| --- | --- | --- |
| React and Vite | Build and serve the user interface | They provide a straightforward way to make a responsive single-page web app and create a production build. |
| FastAPI | Provide the backend API | It is a small Python web framework, works well for API endpoints, and provides interactive API documentation. |
| PyPDF | Extract text and page numbers from PDFs | It supports the basic text-based PDF workflow required by the demo. |
| Sentence Transformers | Convert text into embeddings | Embeddings help find passages that are related in meaning, even when the question uses different words. |
| NumPy | Store and compare vectors | It keeps the small demo's similarity search simple without setting up a separate vector database. |
| OpenRouter | Generate the final answer from retrieved passages | It provides access to an LLM through an API compatible with the OpenAI client. The configured model and its availability can change. |
| Docker Compose | Run the app and monitoring services together | One command can start the backend, frontend, Prometheus, Grafana, Loki, and Alloy for a local demonstration. |
| Kubernetes | Deploy the frontend and backend as workloads | Deployments, Services, probes, and persistent storage describe how to run and check the app in a cluster. |
| Prometheus, Grafana, Loki, and Alloy | Collect metrics and logs and display them | Prometheus scrapes backend metrics; Alloy forwards Docker logs to Loki; Grafana displays dashboard panels. |

This is a small demonstration design. A larger production system would normally use a shared vector database and additional controls for scale, access, and operations.

## 5. Why the design has a few limits

- The vector index is held in the backend process while it is running. The backend is therefore set to one replica. Multiple independent replicas could have different in-memory indexes.
- A persistent volume keeps the backend's data files and model cache across restarts. It does not make the in-memory index shared between replicas.
- PyPDF extracts selectable text. A scanned PDF that contains only page images may need OCR, which is not included here.
- The answer needs a working OpenRouter API key and network access. The key belongs in a local environment file or a Kubernetes Secret, not in source control.
- The current Prometheus/Grafana/Loki/Alloy setup is in Docker Compose. The Kubernetes manifests deploy the application and its storage; they do not deploy a separate monitoring stack into Kubernetes.

These are useful next steps to discuss if asked how the project could be improved.

## 6. Containers, Kubernetes, and monitoring

### Docker Compose

The backend and frontend have their own Dockerfiles. Compose starts them with the monitoring services. The frontend waits for the backend health check before it starts. Named volumes preserve application and monitoring data when containers stop.

### Kubernetes

The manifests create a namespace, configuration, a persistent volume claim, and backend and frontend Deployments and Services. The backend has startup, readiness, and liveness probes. A probe lets Kubernetes check whether a container has started and whether it is ready to receive traffic.

### Monitoring

The backend exposes a health endpoint and a Prometheus metrics endpoint. The dashboard includes request rate, request latency, upload and question outcomes, retrieval/LLM latency, and container logs. Metrics show numeric measurements; logs help explain individual events and errors.

## 7. CI/CD: what it does in this project

CI/CD is automation that checks and delivers changes. **CI** means Continuous Integration: test the changes and build the app. **CD** means Continuous Delivery or Deployment: prepare or deploy a working version.

The workflow is in `.github/workflows/ci-cd.yml`. It starts when code is pushed to `main`, when a pull request targets `main`, or when someone starts it manually.

### The workflow steps

1. **Validate:** GitHub Actions checks out the code, installs Python 3.12 and the backend packages, runs the backend unit tests, installs Node.js 22, and builds the frontend. A failed validation prevents the later jobs from running.
2. **Publish images:** After validation, a non-pull-request run builds the backend and frontend Docker images and pushes them to GitHub Container Registry (GHCR). Each image gets a tag for the commit and a `latest` tag. The workflow uses GitHub's provided token to sign in.
3. **Optional Kubernetes deploy:** This job runs only after image publishing, and only for a push to `main` when the repository variable `KUBE_DEPLOY` is set to `true`. It reads cluster access from the `KUBE_CONFIG` secret, applies the Kubernetes manifests, updates the Deployments to the new images, and waits for both rollouts.

### What happened in the checked run

The run for the initial project push passed validation and published both images. Its Kubernetes deploy job was **skipped** because the optional automatic-deployment condition was not met. The Kubernetes deployment was checked separately; do not say GitHub Actions performed that deployment.

For automatic Kubernetes deployment, the repository also needs the `KUBE_DEPLOY=true` variable, a valid `KUBE_CONFIG` secret, a cluster that can pull the GHCR images, and the `assistant-secrets` Secret already created in the cluster.

**Simple explanation to say:** “When I push code, GitHub Actions first runs the backend tests and builds the frontend. If those checks pass, it builds and publishes the Docker images. It can also deploy them to Kubernetes, but that last step is optional and needs cluster credentials. In the run I checked, the tests and image publishing passed; automatic Kubernetes deployment was skipped.”

## 8. Problems encountered and what they meant

These are the issues observed while checking and validating the project. Explain the fix you actually performed; do not claim a step you did not do.

### PowerShell blocked `npm`

PowerShell tried to run `npm.ps1`, but the machine's script policy blocked it. Using `npm.cmd` avoids that PowerShell script wrapper. The first build command also ran from the repository root, where there is no `package.json`; running it from the `frontend` folder worked.

**Result:** `npm.cmd run build` in `frontend` completed successfully.

### Backend tests could not start in the local Python environment

The first test command ran from the wrong folder, so Python could not find the backend's `app` package. Running from `backend` fixed that path issue, but the selected local Python environment did not have dependencies such as FastAPI and NumPy installed.

The tests were then run with the dependencies in the backend Docker image, with the test files mounted into a temporary test container.

**Result:** all three backend unit tests passed.

### Kubernetes initially returned `invalid character '<'`

`kubectl` received an HTML response where it expected Kubernetes API data. That usually means the configured endpoint or context was not reaching a usable Kubernetes API at that time. After the cluster became reachable, the node reported Ready, the application pods reported Running, the storage claim was Bound, and both deployments rolled out successfully.

### Git was not set up at first

Initially the project folder did not have Git metadata. Git was initialized, a `main` branch and `origin` remote were set up, and the project was pushed. The `.gitignore` excludes `.env`; the backend environment file was checked and is not tracked.

**Result:** the local `main` branch is clean and synchronized with `origin/main`. In the initial push's Actions run, validation and image publishing succeeded; the optional automatic Kubernetes deploy was skipped.

## 9. What was checked

- The frontend production build passed.
- All three backend unit tests passed in the backend Docker image.
- Docker Compose configuration validation passed.
- The local application, API health endpoint, Prometheus health endpoint, and Grafana health endpoint responded successfully.
- Kubernetes showed a Ready node, one Running backend pod, one Running frontend pod, a Bound persistent volume claim, and successful rollouts.
- Git showed a clean `main` branch synchronized with `origin/main`.
- GitHub Actions validation and image publishing passed for the pushed commit; the optional deployment job was skipped.

These checks confirm the build, selected tests, service availability, and deployment status at the time of checking. They do not prove every possible question will get a correct answer. During the live presentation, test a real text-based PDF and a question whose answer can be found in it.

## 10. Suggested live demonstration

1. Open the application.
2. Upload a small text-based PDF.
3. Ask a question with an answer stated in that PDF.
4. Show the answer and open its source list to point out the filename and page.
5. Ask a question that is not answered in the document and explain the intended “not found” behavior.
6. Show `/api/docs` and `/api/health`.
7. Show the Kubernetes pods and Services, then explain that each app pod is running.
8. Open Grafana and explain one latency panel and one outcome or logs panel.

Use a PDF you are allowed to share. Do not display your API key or the contents of your `.env` file.

## 11. Short closing statement

> This project demonstrates a complete document-question-answering flow: upload a PDF, retrieve relevant passages, generate a grounded answer, and show its sources. I also validated the application build and tests, ran it with Docker, deployed the app to Kubernetes, and checked the monitoring and CI results. The main next improvement would be using a shared vector database and adding OCR for scanned PDFs.

## 12. Possible questions

**What does RAG mean?**  
Retrieval-Augmented Generation. The application first retrieves related document passages, then gives those passages to the language model to help form an answer.

**Why use embeddings instead of searching only for exact words?**  
Embeddings compare meaning, so a question and a passage can be related even if they do not use exactly the same words.

**Why keep only one backend replica?**  
The current vector index is in process memory. Separate replicas would not automatically share the same index.

**What happens if the PDF does not contain the answer?**  
The model is instructed to say it could not find the answer in the uploaded documents. This behavior should be demonstrated and reviewed; an LLM can still make mistakes.

**What is the difference between Docker and Kubernetes here?**  
Docker packages and runs each service as a container. Docker Compose coordinates the local demo services. Kubernetes manages application containers in a cluster and checks their health and availability.

**What would you improve next?**  
I would add OCR for scanned PDFs, a shared vector database for scaling, authentication and upload limits, and Kubernetes-native monitoring if the monitoring stack also needs to run in the cluster.
