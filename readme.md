# 🚀 LeaveSmart  
## Automated Leave, Attendance & Workload Balancing System

An intelligent leave management system that combines **rule-based automation, workload awareness, deadline sensitivity, and risk scoring** to make smarter leave approval decisions.

Built as a competition-ready MVP with enterprise-grade clarity.

---

## 📖 Problem Statement

Traditional leave management systems ignore:

- Team workload
- Project deadlines
- Real-time team capacity
- Risk-based prioritization

This leads to poor planning, reduced productivity, and last-minute chaos.

---

## 💡 Solution Overview

LeaveSmart introduces:

- ⚙️ Rule-Based Auto-Approval Engine  
- 📊 Capacity-Aware Leave Decisions  
- 🧠 Risk Scoring Mechanism (0–100)  
- 🧾 Deadline Conflict Detection  
- 🔁 Manager Override System  
- 📈 Live Capacity Visualization  
- 🧮 Separate Leave Buckets (EL / CL / SL)  

---

## 🧠 Core Intelligence Logic

### 1️⃣ Rule-Based Decision Engine

Every leave request is evaluated against:

- Business day calculation
- Leave balance (EL / CL / SL)
- Team size
- Approved overlapping leaves
- Deadline overlap policy
- Capacity threshold
- Sentiment-based reason classification
- Risk scoring

---

### 2️⃣ Deadline Policies

Deadlines can be configured as:

- `HARD_BLOCK` → Auto reject if overlapping  
- `ESCALATE` → Increase risk and send to manager  

---

### 3️⃣ Capacity Formula

```text
Capacity % = (Team Size - Approved Leaves) / Team Size * 100
```

If projected capacity drops below threshold → Leave is rejected.

---

### 4️⃣ Risk Score (0–100)

Risk Score is calculated using:

- Capacity Component (0–40)
- Deadline Component (0–40)
- Duration Component (0–20)

Decision Logic:

- Low Risk → Auto Approve  
- Medium Risk → Escalate  
- Critical Violation → Reject  

---

## 👥 User Roles

### 👨‍💼 Employee

- View EL / CL / SL balances  
- Submit leave request  
- Pre-check risk before final submission  
- View leave history  

### 👩‍💼 Manager

- View pending requests  
- Approve / Reject leave  
- Override past decisions  
- Add / Edit / Delete deadlines  
- View 7-day capacity projection  

---

## 🏗 Architecture

```text
Frontend (Bootstrap)
        ↓
Flask Routes
        ↓
Rule Engine
        ↓
SQLite Database
        ↓
Audit Log
        ↓
Chart.js Analytics
```

---

## 📂 Project Structure

```
leave-smart/
│
├── app.py
├── models.py
├── rules.py
├── seed.py
├── requirements.txt
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── employee_leaves.html
│   ├── employee_leave_new.html
│   ├── manager_dashboard.html
│
└── static/
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone Repository

```bash
git clone https://github.com/your-username/leave-smart.git
cd leave-smart
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

Activate:

Windows:
```bash
venv\Scripts\activate
```

Mac/Linux:
```bash
source venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Initialize Database

```bash
python seed.py
```

### 5️⃣ Run Server

```bash
python app.py
```

Open in browser:

```
http://127.0.0.1:5000
```

---

## 🔐 Demo Credentials

### Manager
```
Email: manager@demo.com
Password: demo123
```

### Employees
```
Email: e1@demo.com
Password: demo123
```

(Also e2@demo.com to e5@demo.com)

---

## 🧾 Audit Logging

System logs:

- SUBMIT_REJECT  
- AUTO_APPROVE  
- ESCALATE  
- APPROVE  
- REJECT  
- OVERRIDE  
- ADD_DEADLINE  
- EDIT_DEADLINE  
- DELETE_DEADLINE  

---

## 📊 Dashboard Features

Manager dashboard includes:

- 📈 7-Day Capacity Line Chart  
- 📋 Pending Leave Requests  
- 🧾 Deadline Management  
- 🔁 Decision Override  

---

## 🎯 Why This Is Competition-Ready

✔ Intelligent rule engine  
✔ Workload-aware approval logic  
✔ Risk-based scoring system  
✔ Role-based dashboards  
✔ Override accountability  
✔ Clean architecture  
✔ Clear demonstration impact  

---

## 🚀 Future Enhancements

- Email notifications  
- Advanced NLP sentiment analysis  
- PostgreSQL production database  
- Multi-team scaling  
- REST API version  
- Docker deployment  

---

## 📜 License

Holoforge License