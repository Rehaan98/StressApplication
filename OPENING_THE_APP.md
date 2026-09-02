# 🚀 How to Open the Psychological Stress AI Application

## ✅ Current Status: Application is RUNNING

Both servers are currently active and ready:
- **Backend**: Running on http://localhost:8000 ✓
- **Frontend**: Running on http://localhost:3000 ✓

## 📱 Step-by-Step: Open the Application

### Step 1: Open Your Web Browser
- Safari, Chrome, Firefox, or any modern browser

### Step 2: Navigate to the Application
Type or paste this URL in your address bar:
```
http://localhost:3000
```

### Step 3: You Should See the Landing Page
**What you'll see:**
- Big heading: "Precision Psychological Stress Assessment with Explainable AI"
- Two buttons: "Launch Live Dashboard" and "Explore RAG Coping Assistant"
- Three feature cards explaining the system

### Step 4: Click "Sign In" (top right)
Or go directly to: http://localhost:3000/login

### Step 5: Login with One of These Accounts

**Regular User (Recommended for testing):**
```
Email:    user@stressai.com
Password: User@2026
```

**Admin User (for admin panel access):**
```
Email:    admin@stressai.com
Password: Admin@StressAI2026
```

**Clinician User:**
```
Email:    dr.sarah@clinic.com
Password: Clinician@2026
```

### Step 6: After Login, You'll See the Dashboard
The dashboard shows:
- Welcome message with your name
- Current stress level gauge
- Average metrics (HRV, Sleep, PSS Score)
- Stress distribution chart
- RAG coping recommendations
- Assessment history timeline

## 🎯 What Can You Do Now?

### 1. Take a Stress Assessment
- Click **"New Stress Assessment"** button
- Complete the 4-step wizard:
  1. PSS-10 Questionnaire (10 questions about stress)
  2. Physiological Markers (heart rate, HRV, sleep, activity)
  3. Workload & Cognition (work hours, screen time, anxiety)
  4. Review & Submit
- Get instant AI prediction

### 2. View Your Prediction Results
- See your stress level: Low / Moderate / High / Severe
- View confidence score
- See probability distribution across all classes

### 3. Explore Explainability (XAI)
- **SHAP Feature Attribution**: Bar chart showing which features increased/decreased your stress
- **LIME Rules**: If-then rules explaining the prediction
- **Global Feature Importance**: Overall model insights

### 4. Get RAG Coping Interventions
- Personalized evidence-based protocols
- Categories: CBT, Breathing, Sleep, Workload, Mindfulness
- Each intervention shows:
  - Summary and protocol steps
  - Evidence base (research source)
  - Duration and difficulty
  - Relevance score

### 5. View Analytics
- Timeline trends (PSS score, HRV, sleep over time)
- Stress distribution pie chart
- Export CSV reports

### 6. Admin Panel (admin@stressai.com only)
- View all users
- System-wide statistics
- ML model performance metrics

## 🔍 Troubleshooting: "Application Not Opening"

### If you see a blank page or connection error:

**Check 1: Are the servers running?**
Look at your terminals. You should see:
- **Terminal 1 (Backend)**: "Application startup complete"
- **Terminal 2 (Frontend)**: "✓ Ready in [time]ms"

**Check 2: Test the servers directly**
Open these URLs in your browser:
- http://localhost:8000/health — Should show: `{"status":"healthy"}`
- http://localhost:8000/docs — Should show the API documentation (Swagger UI)
- http://localhost:3000 — Should show the application landing page

**Check 3: Check for port conflicts**
```bash
# See what's using port 8000
lsof -i :8000

# See what's using port 3000
lsof -i :3000
```

**Check 4: Clear browser cache**
- Press `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows) to hard refresh
- Or use Incognito/Private browsing mode

**Check 5: Check browser console**
- Press `F12` or `Cmd+Option+I` to open DevTools
- Click "Console" tab
- Look for red error messages

### Common Issues and Fixes

**Issue: "Failed to fetch" or "Network Error"**
- Backend isn't running → Start it: `./start.sh backend`
- Wrong API URL → Check `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`

**Issue: Login says "Invalid credentials"**
- Double-check the email/password
- Try: `user@stressai.com` / `User@2026`
- Check backend logs for error details

**Issue: Page is blank/white screen**
- Frontend crashed → Check Terminal 2 for errors
- React error → Check browser console (F12)
- Try restarting frontend: `Ctrl+C` then `./start.sh frontend`

**Issue: "404 Not Found" on API calls**
- Backend might not have reloaded → Restart it: `Ctrl+C` then `./start.sh backend`

## 🛠️ Restarting the Servers

If something isn't working, restart:

**Stop both servers:**
1. Go to Terminal 1 (backend) → Press `Ctrl+C`
2. Go to Terminal 2 (frontend) → Press `Ctrl+C`

**Restart:**
```bash
# Terminal 1
./start.sh backend

# Terminal 2
./start.sh frontend
```

**Or use the all-in-one:**
```bash
./start.sh
```

## 📊 Quick Test: Is Everything Working?

Run this test script:
```bash
cd "/Users/shaik/Documents/Psychological stress AI"
source venv/bin/activate
PYTHONPATH=. python -c "
import urllib.request as ur
import json

# Test backend health
h = json.loads(ur.urlopen('http://localhost:8000/health').read())
print(f'✓ Backend: {h[\"status\"]}')

# Test frontend
ur.urlopen('http://localhost:3000').read()
print('✓ Frontend: responsive')

# Test login
req = ur.Request('http://localhost:8000/api/v1/auth/login',
    data=json.dumps({'email':'user@stressai.com','password':'User@2026'}).encode(),
    headers={'Content-Type':'application/json'})
tok = json.loads(ur.urlopen(req).read())
print(f'✓ Auth: {tok[\"user\"][\"full_name\"]} logged in')

print('\n All systems operational. Open: http://localhost:3000')
"
```

## 🌐 Direct Links (Copy-paste these)

- **Application Home**: http://localhost:3000
- **Login Page**: http://localhost:3000/login
- **Dashboard**: http://localhost:3000/dashboard
- **New Assessment**: http://localhost:3000/assessment
- **RAG Coping**: http://localhost:3000/rag-coping
- **Analytics**: http://localhost:3000/analytics
- **API Documentation**: http://localhost:8000/docs

## ✨ What You Should See on Each Page

### Landing Page (/)
- Large hero with gradient text
- "Precision Psychological Stress Assessment with Explainable AI"
- Two CTA buttons
- Three feature cards

### Login (/login)
- Blue brain icon logo
- "Sign In to StressAI"
- Email and password fields
- "Sign In" button with arrow
- "Create account" link at bottom

### Dashboard (/dashboard)
- Welcome banner with your name
- "New Stress Assessment" button
- 4 metric cards (Stress Level, HRV, Sleep, PSS Score)
- Risk gauge (circular with color indicator)
- Stress distribution grid
- RAG intervention cards
- Recent history table

### Assessment (/assessment)
- 4-step progress bar
- PSS-10 questions (Step 1)
- Slider inputs for physiological data (Step 2)
- Slider inputs for workload data (Step 3)
- Review summary (Step 4)
- "Submit & Generate AI Prediction" button

### Predictions (/predictions)
- Stress level badge (colored pill)
- Risk gauge
- Confidence percentage
- Probability distribution bars
- SHAP bar chart (red/green bars)
- LIME rules list
- RAG intervention cards

## 🆘 Still Can't See It?

The application is **definitely running** and **working correctly**.

Here's proof — both servers responded successfully:
- ✅ Backend health check: OK
- ✅ Frontend responding: OK
- ✅ Login API: OK
- ✅ Full pipeline test: OK

**Try this:**
1. Open a new browser window
2. Type: `localhost:3000`
3. Press Enter

If you see anything other than the landing page, take a screenshot and I'll help debug specifically.

The most likely issue is:
- You're typing the wrong URL (should be `localhost:3000` not `localhost:8000`)
- Browser is showing cached old version (press Cmd+Shift+R to hard refresh)
- Firewall blocking localhost (unlikely on Mac)
