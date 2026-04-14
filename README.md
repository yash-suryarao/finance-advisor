# 🚀 AI Finance Advisor

<div align="center">
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green" alt="Django" />
  <img src="https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E" alt="JavaScript" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="TailwindCSS" />
  <img src="https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white" alt="Gemini AI" />
  <img src="https://img.shields.io/badge/Apache_ECharts-AA344D?style=for-the-badge&logo=apacheecharts&logoColor=white" alt="ECharts" />
</div>

<br/>

**AI Finance Advisor** is a next-generation, intelligent personal finance management platform. It moves beyond static expense tracking by integrating **Machine Learning (XGBoost/Prophet)** and **Generative AI (Google Gemini)** to actively coach users, enforce accountability, and generate personalized zero-based budgets based on historical behavior.

---

## 🌟 The Problem Statement

Modern banking apps and traditional budget trackers are passive. They show you *where* your money went, but they don't tell you *why*, nor do they effectively intervene to change your financial habits. Users often set arbitrary budgets that they quickly abandon, leading to poor financial health, missed savings goals, and unchecked lifestyle inflation.

## 🎯 Our Objective

To build an active, "memory-aware" financial coach that:
1. **Automates Budgeting**: Predicts and suggests hyper-personalized budget limits that adapt to real-life spending.
2. **Enforces Accountability**: Tracks the user's commitments (e.g., "I will spend less on dining this month") and evaluates their success in subsequent reports.
3. **Translates Data into Action**: Uses LLMs to turn raw transaction grids into plain-English, actionable daily advice.

---

## ✨ Core Features

*   🧠 **Generative AI Financial Coach (XAI)**: Generates comprehensive monthly reviews. It flags anomalies, praises discipline, and identifies overspending. If the AI suggests a strict budget limit and you accept it, the AI *remembers* your commitment and holds you accountable in future reports.
*   📊 **Smart 50/30/20 Analysis**: Automatically categorizes your expenses into Needs, Wants, and Savings using advanced transaction mapping to grade your Financial Health Score.
*   🔮 **Predictive Trajectory Modeling**: Uses time-series forecasting (Prophet) to project your month-end financial runway based on your current burn rate.
*   📈 **Dynamic Visualization**: Uses Apache ECharts for stunning, interactive dashboards including Zero-Based Budget Trajectories, Stacked Category Breakdowns, and Anomaly Heatmaps.
*   🎯 **Intelligent Savings Goals**: Set goals with specific deadlines. The system calculates the exact monthly contributions needed based on your historical cash flow.
*   💸 **P2P Payment Wallets**: Integrated digital wallet architecture supporting mock peer-to-peer settlements and transaction ledgering.

---

## 🏗️ System Architecture

The project is built on a modular backend-heavy architecture, separating core ledgers from AI logic.

*   **`backend/`**: The core Django project router and global configuration settings.
*   **`transactions/`**: The fundamental ledger. Handles CRUD operations for incomes, expenses, categories, and wallet balances.
*   **`insights/`**: The "brain" of the app. Houses the DRF APIs that pass data to ML models and the Gemini API. Manages Budget Targets and AI Accountability Logs.
*   **`payments/`**: Processes wallet deposits, withdrawals, and peer-to-peer transfers securely.
*   **`users/`**: Extends the default Django Auth model to handle secure profile authentication.
*   **`frontend/`**: The presentation layer. Utilizes vanilla JavaScript, TailwindCSS, and ECharts to asynchronously render AI analytics without heavy page reloads.

---

## ⚙️ How it Works (The Accountability Loop)

1.  **Data Ingestion**: The user logs transactions or uploads CSV statements.
2.  **Algorithmic Analysis**: The `insights` engine calculates daily burn rates and queries the database for historic trends.
3.  **Prompt Engineering**: A highly structured prompt payload (injecting user net worth, last month's spending, and previous promises made) is sent to **Gemini 2.0 Flash**.
4.  **User Action**: The AI suggests a strict new budget target right inside the generated report.
5.  **Database Persistence**: If the user clicks **"Accept Budget"**, the platform updates the `TransactionsBudget` table and logs a `User Action` feature in the database.
6.  **The Loop closes**: Next month, step 3 includes the logged Action, allowing the AI to say: *"Last month you agreed to limit Dining to ₹5,000, but you spent ₹7,000. Let's adjust..."*

---

## 🛠️ Local Setup & Installation

### Prerequisites
*   Python 3.10+
*   Google Gemini API Key

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/finance-advisor.git
   cd finance-advisor
   ```

2. **Set up a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory and add your secret keys:
   ```env
   GEMINI_API_KEY=your_google_gemini_key_here
   DEBUG=True
   ```

5. **Run Database Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```
   Navigate to `http://127.0.0.1:8000/` to access the application.

---
