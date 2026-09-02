# Psychological Stress AI — Quick Start Guide

## ✅ Application is Ready!

Both servers are currently running:
- **Backend API**: http://localhost:8000
- **Frontend App**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## 🚀 How to Access the Application

1. **Open your web browser**
2. **Go to**: http://localhost:3000
3. **Login with**:
   - **User Account**: `user@stressai.com` / `User@2026`
   - **Admin Account**: `admin@stressai.com` / `Admin@StressAI2026`
   - **Clinician Account**: `dr.sarah@clinic.com` / `Clinician@2026`

## 📋 Available Features

### For Regular Users:
- ✅ **Dashboard**: Real-time stress analytics and trends
- ✅ **Assessment**: Complete PSS-10 + physiological stress assessment
- ✅ **Predictions**: AI-powered stress level prediction (XGBoost)
- ✅ **Explainability**: SHAP & LIME feature attribution
- ✅ **RAG Coping**: Evidence-based intervention recommendations
- ✅ **Analytics**: Historical trends and visualizations
- ✅ **Reports**: Download CSV reports of your assessments

### For Admins:
- ✅ **Admin Panel**: User management and system analytics
- ✅ **Model Performance**: ML metrics and monitoring

## 🔧 Starting/Stopping the Application

### Option 1: Using the startup script (recommended)
```bash
# Start both servers
./start.sh

# Or start individually:
./start.sh backend    # Backend only (port 8000)
./start.sh frontend   # Frontend only (port 3000)
```

### Option 2: Manual startup

**Terminal 1 - Backend:**
```bash
cd "/Users/shaik/Documents/Psychological stress AI"
source venv/bin/activate
PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd "/Users/shaik/Documents/Psychological stress AI/frontend"
npm run dev
```

### To Stop:
- Press `Ctrl+C` in each terminal

## 🎯 First-Time Setup (Already Done)

The following setup steps have already been completed:
- ✅ Python virtual environment created
- ✅ Dependencies installed
- ✅ SQLite database seeded with demo users
- ✅ ML model trained (in `ml_engine/models/`)
- ✅ Frontend built and configured

## 📊 Test the Full Pipeline

1. **Login** at http://localhost:3000/login
2. **Take Assessment** → Complete the stress questionnaire
3. **View Prediction** → See your AI stress level
4. **Check Explainability** → Understand the SHAP/LIME drivers
5. **Get RAG Coping** → Receive personalized interventions
6. **View Analytics** → See trends over time

## 🔍 Troubleshooting

### Frontend not loading?
- Check terminal: Frontend should show "✓ Ready in [time]ms"
- Browser: Go to http://localhost:3000
- Clear browser cache if seeing old version

### Backend not responding?
- Check terminal: Should show "Application startup complete"
- Test API: http://localhost:8000/health
- Check database exists: `ls stress_ai.db`

### Port already in use?
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### Need to retrain the ML model?
```bash
./start.sh train
```

### Need to reset the database?
```bash
rm stress_ai.db
./start.sh seed
```

## 📁 Project Structure

```
Psychological stress AI/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # API endpoints
│   │   ├── core/        # Config, database, security
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   └── services/    # Business logic
│   └── requirements.txt
├── frontend/             # Next.js frontend
│   ├── src/
│   │   ├── app/         # Pages (dashboard, assessment, etc.)
│   │   ├── components/  # Reusable React components
│   │   └── lib/         # API client, auth context
│   └── package.json
├── ml_engine/            # Machine learning pipeline
│   ├── models/          # Trained model artifacts
│   ├── src/             # Training, preprocessing, XAI, RAG
│   └── predict.py       # Inference entrypoint
├── database/             # SQL schema and seed data
├── stress_ai.db         # SQLite database
├── .env                 # Environment variables
└── start.sh             # Startup script
```

## 🎓 User Accounts (Already Seeded)

| Email | Password | Role |
|-------|----------|------|
| user@stressai.com | User@2026 | User |
| admin@stressai.com | Admin@StressAI2026 | Admin |
| dr.sarah@clinic.com | Clinician@2026 | Clinician |

## 🆘 Still Having Issues?

The application is currently running and ready to use. Just open your browser and go to:

👉 **http://localhost:3000**

If you see any errors, check:
1. Both terminal windows are running (backend on :8000, frontend on :3000)
2. No firewall blocking localhost connections
3. Browser console for any JavaScript errors (F12 → Console tab)
