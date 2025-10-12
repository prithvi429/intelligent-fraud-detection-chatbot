# Deployment Guide

This document describes how to deploy the **Insurance Fraud Detection Chatbot** for both **local development** and **production (AWS)** environments.

The project leverages:
- **Docker Compose** for local simulation  
- **Terraform + CloudFormation** for AWS Infrastructure as Code (IaC)
- **Bash automation scripts** for Lambda and model deployment

---

## 🧩 Prerequisites

| Requirement | Description |
|--------------|-------------|
| **Python** | 3.11+ |
| **Docker** | For local containerized development |
| **Terraform** | v1.5 or newer |
| **AWS CLI** | v2.0+, configured with IAM credentials |
| **Git** | Version control |
| **AWS Account** | Free-tier eligible |
| **IDE** | VS Code (recommended) with Python, Terraform extensions |

### 💰 Estimated Costs
| Environment | Approx. Monthly Cost | Components |
|--------------|----------------------|-------------|
| Local | Free | Docker, LocalStack |
| AWS Dev | ~$30 | t3.micro RDS, t3.medium SageMaker |
| AWS Prod | ~$100+ | Multi-AZ RDS, larger SageMaker instance |

---

## ⚙️ Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/<your-org>/intelligent-fraud-detection-chatbot.git
cd intelligent-fraud-detection-chatbot
