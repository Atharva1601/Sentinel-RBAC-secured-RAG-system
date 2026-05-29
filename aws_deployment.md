# 🚀 AWS Deployment Guide — Sentinel RAG System

> **Learning guide only.** This walks you through the concepts and steps to deploy
> this project on AWS. You are not expected to hit "final deploy" in one sitting —
> read, understand, then experiment step-by-step.

---

## 🧠 AWS Services Explained (What You Actually Need)

Before touching anything, understand which AWS services apply to this project:

| AWS Service | What It Is | Do We Use It? |
| :--- | :--- | :---: |
| **EC2** | A virtual machine (Linux server in the cloud) | ✅ Yes — runs FastAPI |
| **S3** | File/object storage (like a cloud hard drive) | ✅ Optional — store uploaded PDFs |
| **ECR** | Docker image registry (like DockerHub but AWS) | ✅ Optional — store our Docker image |
| **ECS** | Runs Docker containers at scale | 🔄 Advanced option |
| **App Runner** | Simplified container hosting (like Render but AWS) | 🔄 Simpler alternative to EC2 |
| **ElastiCache** | Managed Redis | ✅ Optional (use Upstash free instead) |
| **RDS** | Managed SQL database | ❌ We use local SQLite, not needed |
| **Lambda** | Serverless functions (stateless, short-lived) | ❌ Bad fit — loads 400MB model on startup |
| **Bedrock** | AWS-hosted LLMs (Claude, Titan, etc.) | ❌ We use Groq — not needed |
| **Amplify** | Frontend hosting (like Vercel/Netlify) | ✅ Optional — host the React frontend |
| **CloudFront** | CDN (speed up static assets globally) | 🔄 Advanced |

**TL;DR for this project:**
- **Backend** → EC2 (or App Runner)
- **Frontend** → AWS Amplify (or just Vercel — simpler)
- **Vector DB** → Qdrant Cloud (free tier) — do NOT try to run Qdrant on EC2 free tier
- **Redis** → Upstash free tier (or ElastiCache — paid)

---

## 📐 Target Architecture

```
                  ┌─────────────────────────────────────┐
                  │            AWS Cloud                 │
                  │                                      │
Users ──HTTPS──▶  │  EC2 (t3.small)                      │
                  │  ┌──────────────────────────────┐   │
                  │  │  Docker Container             │   │
                  │  │  ├─ FastAPI (uvicorn)         │   │
                  │  │  ├─ BGE-small embedding model │   │
                  │  │  └─ Cross-encoder reranker    │   │
                  │  └──────────────────────────────┘   │
                  │          │           │               │
                  └──────────┼───────────┼───────────────┘
                             │           │
                    ┌────────▼───┐  ┌────▼──────────┐
                    │ Qdrant     │  │  Upstash Redis │
                    │ Cloud      │  │  (free tier)   │
                    │ (free 1GB) │  └───────────────-┘
                    └────────────┘
                             │
                    ┌────────▼───┐
                    │  Groq API  │
                    │  (LLM)     │
                    └────────────┘
```

---

## ✅ Prerequisites (Do These First)

### 1. AWS Account Setup
1. Create an account at [aws.amazon.com](https://aws.amazon.com)
2. Go to **IAM** → Create a user with programmatic access (don't use root account)
3. Attach policy: `AmazonEC2FullAccess`, `AmazonS3FullAccess`
4. Download the **Access Key ID** and **Secret Access Key**

### 2. Install AWS CLI on Windows
```powershell
# Install AWS CLI
winget install Amazon.AWSCLI

# Verify
aws --version

# Configure with your keys
aws configure
# Enter: Access Key ID, Secret Access Key, region (e.g. ap-south-1 for Mumbai), output format: json
```

### 3. Install Docker Desktop
- Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- Docker is how we package the app to run reliably on any server

### 4. Set Up Qdrant Cloud (Required — Free)
1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a free cluster (1GB, no credit card needed for free tier)
3. Note your **Cluster URL** and **API Key**
4. Update your `.env`:
   ```
   QDRANT_USE_CLOUD=true
   QDRANT_CLOUD_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
   QDRANT_CLOUD_API_KEY=your_api_key_here
   ```
5. **Re-ingest your documents** after switching to cloud Qdrant — the cloud collection is empty initially.

---

## 🐳 Step 1 — Dockerize the Backend

This packages the entire backend into a single portable container.

### 1.1 Create `Dockerfile` in `llm-se-backend/`

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding and reranker models during build
# This avoids cold-start delays on the server
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.2 Create `.dockerignore` in `llm-se-backend/`

```
.env
data/
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
```

### 1.3 Build and Test Locally

```powershell
cd "c:\Users\athar\Documents\Projects\LLM SE platform\llm-se-backend"

# Build the image (takes 5-10 mins first time — downloads models)
docker build -t sentinel-backend .

# Test it locally
docker run -p 8000:8000 --env-file .env sentinel-backend

# Visit http://localhost:8000/docs to verify it works
```

> ⚠️ The image will be ~3-4GB because it bakes in the ML models. This is intentional —
> it means zero cold start on the server.

---

## ☁️ Step 2 — Push Docker Image to AWS ECR

ECR (Elastic Container Registry) is AWS's private Docker image storage.

```powershell
# Get your AWS account ID
$ACCOUNT_ID = $(aws sts get-caller-identity --query Account --output text)
$REGION = "ap-south-1"   # Change to your region

# Create a repository in ECR
aws ecr create-repository --repository-name sentinel-backend --region $REGION

# Authenticate Docker to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Tag the image
docker tag sentinel-backend:latest "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/sentinel-backend:latest"

# Push to ECR (uploads ~3-4GB — takes a few minutes)
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/sentinel-backend:latest"
```

---

## 🖥️ Step 3 — Launch an EC2 Instance

### 3.1 Via AWS Console (Easier for Learning)

1. Go to **EC2 → Launch Instance**
2. Settings:
   - **Name**: `sentinel-backend`
   - **AMI**: Ubuntu 22.04 LTS (Free Tier eligible)
   - **Instance type**: `t2.micro` (free tier) for testing, `t3.small` (~$15/month) for actual running
   - **Key pair**: Create new → download `.pem` file → **save it safely, you cannot re-download it**
   - **Security group**: Allow inbound `SSH (22)` and `Custom TCP 8000` from Anywhere (`0.0.0.0/0`)
3. Click **Launch Instance**

> ⚠️ RAM Warning:
> - `t2.micro` = 1GB RAM → the BGE embedding model needs ~400MB, which leaves 600MB for everything else. It will likely crash or run very slowly.
> - `t3.small` = 2GB RAM → comfortable minimum for this project.
> - `t3.small` is NOT free tier, but costs ~$0.0208/hour (~$15/month). Stop the instance when not in use.

### 3.2 Connect to Your Instance via SSH

```powershell
# On Windows PowerShell — fix permissions on .pem file first
icacls "C:\path\to\your-key.pem" /inheritance:r /grant:r "$env:USERNAME:(R)"

# SSH into the instance
ssh -i "C:\path\to\your-key.pem" ubuntu@<your-ec2-public-ip>
```

---

## 🔧 Step 4 — Set Up the EC2 Server

Run these commands **on the EC2 instance** (after SSH-ing in):

```bash
# Update packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu   # allow ubuntu user to run docker
newgrp docker                    # apply group change without logout

# Install AWS CLI (to pull from ECR)
sudo apt-get install -y awscli

# Configure AWS credentials on the server
aws configure
# Enter your Access Key ID, Secret Key, region
```

---

## 🚀 Step 5 — Run the Container on EC2

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com

# Pull your image from ECR
docker pull <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com/sentinel-backend:latest

# Create your .env file on the server
nano .env
# Paste in all your environment variables (GROQ_API_KEY, QDRANT_CLOUD_URL, etc.)
# Ctrl+X to save and exit

# Run the container
docker run -d \
  --name sentinel \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  <your-account-id>.dkr.ecr.ap-south-1.amazonaws.com/sentinel-backend:latest

# Check logs
docker logs -f sentinel
```

After this, your API will be live at: `http://<your-ec2-public-ip>:8000`

Test it: `http://<your-ec2-public-ip>:8000/docs`

---

## 🌐 Step 6 — Point the Frontend to the New Backend

In `llm-se-frontend/frontend/.env.local`, change the API URL:

```
VITE_API_BASE_URL=http://<your-ec2-public-ip>:8000
```

Then rebuild and redeploy the frontend (Vercel is easiest — push to GitHub and it auto-deploys).

---

## 💡 Step 7 (Optional) — Add a Domain + HTTPS

For a real deployment, you need HTTPS (browsers block mixed HTTP/HTTPS content):

1. Buy a cheap domain (~$1/year on Namecheap or use a free `.tk` domain)
2. Set up **AWS Certificate Manager (ACM)** for a free SSL certificate
3. Put an **Application Load Balancer (ALB)** in front of EC2 (routes HTTPS → HTTP to your container)

This is an intermediate-level AWS topic. Skip for now, come back to it when ready.

---

## 💰 Cost Breakdown (Learn Mode)

| Service | Cost |
| :--- | :--- |
| EC2 `t2.micro` | Free (750 hrs/month, 12 months) |
| EC2 `t3.small` | ~$0.02/hr → **Stop when not testing** |
| ECR storage | ~$0.10/GB/month → ~$0.40/month for 4GB image |
| Qdrant Cloud | **Free** (1GB cluster) |
| Upstash Redis | **Free** (10k requests/day) |
| Groq API | **Free** (rate-limited) |
| **Total (learning)** | **~$0–2/month** if you stop EC2 when done |

> 💡 **Tip**: Set up an **AWS Budget Alert** at $5 so you get an email if costs spike.
> Go to AWS Billing → Budgets → Create Budget.

---

## 🔄 Render vs Railway vs AWS — Quick Comparison

| Feature | Render (Free) | Railway (Free) | AWS EC2 |
| :--- | :---: | :---: | :---: |
| Cold start | ~60s (spins down) | ~15s (spins down) | None (always on) |
| RAM | 512MB | 512MB | 1-2GB (configurable) |
| BGE model fits? | ❌ Likely OOM | ❌ Likely OOM | ✅ On t3.small |
| Cost | Free | $5 credit | ~$0-15/month |
| Skill gained | Low | Low | **High (real AWS)** |
| Production-ready | No | No | Yes |

**Conclusion:** Railway and Render will both OOM crash with the BGE model loaded.
AWS EC2 is the right choice for actually running this project.

---

## 📋 Deployment Checklist

- [ ] AWS account created, IAM user configured, CLI installed
- [ ] Docker Desktop installed and working
- [ ] Qdrant Cloud cluster created, API key saved
- [ ] `.env` updated with `QDRANT_USE_CLOUD=true` and cloud credentials
- [ ] Documents re-ingested into Qdrant Cloud
- [ ] `Dockerfile` created in `llm-se-backend/`
- [ ] Docker image builds successfully locally (`docker build`)
- [ ] App runs correctly in Docker locally (`docker run`)
- [ ] ECR repository created, image pushed
- [ ] EC2 instance launched (t3.small recommended)
- [ ] Docker installed on EC2, image pulled from ECR
- [ ] Container running on EC2, API reachable at `:8000`
- [ ] Frontend `.env.local` updated with EC2 URL
- [ ] AWS Budget Alert set to $5
