# 🧠 AI-Powered Insurance Fraud Detection Chatbot (LLM + ML + OCR)

## 👨‍💻 Developed by
**Pruthviraj Rathod** – AI/ML Engineer  
📧 **Email:** prithvirathod29884@gmail.com  
🔗 [**LinkedIn**](https://linkedin.com/in/rathod-pruthviraj) | [**GitHub**](https://github.com/prithvi429) | [**Portfolio**](https://prithvi429.github.io/Portfolio_pruthviraj_rathod/)

---

## 🚀 Project Overview

The **AI-Powered Insurance Fraud Detection Chatbot** is designed to help insurance companies identify **fake claims**, **analyze documents**, and **guide users** through claim submission or policy queries.  

It combines **Machine Learning (ML)**, **Natural Language Processing (NLP)**, **Optical Character Recognition (OCR)**, and **Large Language Models (LLMs)** to analyze data, detect anomalies, and provide explainable results.

### 🧩 Key Features
- Interacts with users via a chatbot interface  
- Detects fraudulent claims in real time  
- Analyzes uploaded claim documents using OCR  
- Uses ML models to generate fraud probability scores  
- Validates authenticity of uploaded documents  
- Provides explainable AI outputs using LLMs  
- Retrieves claim guidance via RAG (Retrieval-Augmented Generation)

---

## 🏗️ System Architecture

👤 User → 🌐 Frontend (React.js) → ⚙️ FastAPI Backend
→ 🧩 Rule Engine | 🤖 ML Model | 🧾 OCR | 📚 Vector DB (Pinecone)
→ 🧠 Decision Layer + LLM Explanation → 🗄️ PostgreSQL + ☁️ S3 Storage


### 🔹 Workflow Explanation

1. **User Interaction:**  
   Users upload claim details and documents through a web chatbot.

2. **FastAPI Backend:**  
   Acts as the core API layer — routes user queries, processes documents, and connects to ML/NLP components.

3. **Rule Engine:**  
   Flags simple rule-based fraud patterns (e.g., *Late Reporting*, *High Claim Amount*).

4. **Machine Learning Module:**  
   Predicts fraud probability using models like **Random Forest** or **XGBoost**.

5. **Document Analysis (OCR + CV):**  
   Extracts and verifies text from scanned claim documents using **Tesseract OCR** and **OpenCV**.

6. **RAG / Vector Database:**  
   Uses **Pinecone** and **Hugging Face embeddings** to retrieve guidance or policy-related documents.

7. **LLM Layer (LangChain + GPT):**  
   Generates human-readable reasoning —  
   _“This claim looks fraudulent because the reported amount exceeds the limit…”_

8. **Decision & Storage:**  
   Final results, alarms, and analysis are stored in **PostgreSQL** (structured data) and **S3 buckets** (documents).

---

## 🧩 Key Modules

| Module | Description | Technology Used |
|--------|--------------|-----------------|
| **Frontend (Chatbot UI)** | Web-based chatbot interface | React.js, HTML, CSS |
| **API Backend** | Main controller for data routing | FastAPI (Python) |
| **ML Model** | Fraud classification | Random Forest, XGBoost |
| **OCR Engine** | Extracts text from PDFs/images | Tesseract, OpenCV |
| **LLM Integration** | Explanation generation | LangChain, GPT / Hugging Face |
| **RAG System** | Retrieves semantic guidance | Pinecone Vector DB, Hugging Face Embeddings |
| **Database Layer** | Stores data and documents | PostgreSQL, AWS S3 |
| **Logging & Monitoring** | Tracks tool calls and errors | Python Logger, Elastic Stack (optional) |

---

## 🧠 Tech Stack

**Programming Languages:** Python, JavaScript  
**Frameworks:** FastAPI, React.js, LangChain  
**Machine Learning:** Scikit-learn, XGBoost  
**LLMs / NLP:** Hugging Face Transformers, OpenAI API  
**OCR & CV:** Tesseract, OpenCV  
**Vector DB:** Pinecone / Milvus  
**Databases:** PostgreSQL, AWS S3  
**Deployment:** Docker, AWS EC2 / GCP  
**Visualization:** Power BI, Matplotlib  

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/prithvi429/insurance-fraud-detection-chatbot.git
cd insurance-fraud-detection-chatbot

2️⃣ Create a Virtual Environment

python -m venv env_chatbot_f
source env_chatbot_f/bin/activate   # Linux/Mac
env_chatbot_f\Scripts\activate      # Windows

3️⃣ Install Dependencies

pip install -r requirements.txt

4️⃣ Run the FastAPI App

uvicorn main:app --reload

Access API Docs:
👉 http://127.0.0.1:8000/docs

