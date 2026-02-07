# Streamlit Cloud Deployment Guide

This guide covers deploying the Machine Learning system to Streamlit Cloud for public access.

## Prerequisites

- GitHub account with repository access
- Streamlit Cloud account (free tier available)
- Firebase Firestore project with credentials
- Gemini API key
- Groq API key
- DuckDuckGo search capability

## Step 1: Prepare GitHub Repository

1. **Clone/Initialize your repo:**
   ```bash
   git clone <your-repo-url>
   cd machine-learning-main
   ```

2. **Ensure `requirements.txt` exists** with all dependencies:
   ```bash
   # Current dependencies include:
   streamlit>=1.28.0
   firebase-admin>=6.0.0
   google-generativeai>=0.3.0
   groq>=0.4.0
   spacy>=3.7.0
   nltk>=3.8.0
   duckduckgo-search>=3.9.0
   chromadb>=0.4.0
   ```

3. **Ensure `.streamlit/config.toml` exists** for Streamlit configuration:
   ```toml
   [theme]
   primaryColor = "#0078d4"
   backgroundColor = "#ffffff"
   secondaryBackgroundColor = "#e8f0f8"
   textColor = "#1f1f1f"
   
   [client]
   showErrorDetails = true
   
   [logger]
   level = "info"
   ```

4. **Create `.gitignore`** (if not present):
   ```
   # Python
   __pycache__/
   *.py[cod]
   *$py.class
   *.so
   .Python
   env/
   venv/
   .venv
   
   # IDE
   .vscode/
   .idea/
   *.swp
   
   # Environment
   .env
   .env.local
   
   # Data/Caches
   db/chroma/
   .cache/
   
   # OS
   .DS_Store
   ```

5. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Prep for Streamlit Cloud deployment"
   git push origin main
   ```

## Step 2: Create Firestore Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your Firebase project
3. Navigate to **Project Settings → Service Accounts**
4. Click **Generate New Private Key**
5. Save the JSON file locally (you'll copy-paste the contents)

## Step 3: Set Up Streamlit Cloud Secrets

1. Go to [Streamlit Cloud Dashboard](https://share.streamlit.io)
2. Click **New app** → Connect repository
3. Select your repository and `app.py` as the main file
4. Deploy (will fail initially - that's ok, we'll add secrets)
5. Once deployed, click on your app → **Settings** → **Secrets**

6. **Add all required secrets as environment variables:**

```toml
# Firebase Service Account (paste entire JSON from step 2)
FIREBASE_CONFIG = """
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "...",
  "token_uri": "...",
  "auth_provider_x509_cert_url": "...",
  "client_x509_cert_url": "..."
}
"""

# API Keys
GEMINI_API_KEY = "your-gemini-api-key"
GROQ_API_KEY = "your-groq-api-key"

# Configuration
LEARNING_INTERVAL = 60
MAX_LEARNING_RETRIES = 3
QUICK_LEARN_COUNT = 3
```

## Step 4: Environment Variables Reference

The app automatically loads these from `.streamlit/secrets.toml` on Streamlit Cloud:

| Variable | Description | Required |
|----------|-------------|----------|
| `FIREBASE_CONFIG` | Full Firestore service account JSON | ✅ Yes |
| `GEMINI_API_KEY` | Google Gemini API key | ✅ Yes |
| `GROQ_API_KEY` | Groq LLM API key (fallback) | ✅ Yes |
| `LEARNING_INTERVAL` | Auto-learning cycle interval (seconds) | ⚠️ Optional (default: 60) |
| `MAX_LEARNING_RETRIES` | Max retries for learning | ⚠️ Optional (default: 3) |
| `QUICK_LEARN_COUNT` | Number of concepts to learn per cycle | ⚠️ Optional (default: 3) |

## Step 5: Deploy to Streamlit Cloud

1. **Push changes to GitHub:**
   ```bash
   git add .streamlit/config.toml
   git commit -m "Add Streamlit configuration"
   git push origin main
   ```

2. **Streamlit Cloud auto-deploys** when you push to main

3. **Monitor deployment:**
   - Check the **Logs** tab in your Streamlit Cloud app
   - Look for "Service Health Status: {'firebase': {'online': True}, 'gemini': {'configured': True}, ...}"

## Step 6: Verify Deployment

1. **Check app status:**
   - App should load and show chat interface
   - Check sidebar for "Service Health Status"
   - Should show: ✅ Firebase, ✅ Gemini, ✅ Groq, ✅ spaCy

2. **Run a test interaction:**
   ```
   User: "Explain machine learning in simple terms"
   
   Expected:
   - Bot responds with explanation
   - Sidebar shows unknowns detected (e.g., 'machine learning', 'simple terms')
   - After 60 seconds, "Quick Learn" automatically runs
   - "Deep Learn" button available for manual deepening
   ```

3. **Check Firestore:**
   - Go to your Firebase console
   - Check collections: `known_words`, `unknown_words`, `needs_review`, `solidified_knowledge`
   - Verify data is being written

## Troubleshooting

### "Connection refused" errors

**Cause**: Firefox Service Account credentials not configured
**Fix**: 
1. Check `.streamlit/secrets.toml` on Streamlit Cloud
2. Verify `FIREBASE_CONFIG` JSON is complete and valid
3. Try escaping newlines: Use raw JSON or environment variable

### "Quota exceeded" (429 error)

**Cause**: Hit Gemini free tier limit (20 requests/day)
**This is expected behavior** - automatic fallback to Groq handles it
**Solution**: Upgrade Gemini tier or use Groq API directly

### spaCy model not found

**Cause**: First run needs to download en_core_web_sm
**Fix**: This is automatic on app startup (takes ~5-10 seconds first time)

### NLTK WordNet errors

**Cause**: WordNet data not downloaded
**Fix**: Automatic on first use, gracefully skips if unavailable

### Learning not triggering

**Cause**: 
- No unknowns detected (normal for common words)
- Research API rate limited
- LLM quota exceeded

**Debug steps**:
1. Ask question with specific/technical terms: "Explain variational inference"
2. Check sidebar for unknowns
3. Check app logs for error details

### Slow first load

**Cause**: spaCy model loading (first startup)
**Solution**: This is one-time; subsequent loads are fast

## Monitoring & Maintenance

### Key Firestore Collections

```
firestore:
├── known_words/
│   ├── <word1>: {explanation, category, learned_at}
│   └── <word2>: {explanation, category, learned_at}
├── unknown_words/
│   ├── <unknown1>: {added_at}
│   └── <unknown2>: {added_at}
├── needs_review/
│   └── <timestamp>: {prompt, candidates: [...]}
└── solidified_knowledge/
    └── <word>: {deep_explanation, relationships, sources}
```

### Health Checks

Periodically check:
1. **Streamlit Cloud logs** for errors
2. **Error count** in sidebar (should be low)
3. **Firebase read/write usage** - ensure within free tier (~25K reads/writes/day)
4. **Learning progress** - check if unknowns → known_words trends upward

### Cost Tracking

**Firestore (free tier):**
- 50K reads/day
- 20K writes/day
- 1GB storage
- Monitor: Firebase Console → Firestore Usage

**Gemini API (free tier):**
- 20 requests/day
- Automatic fallback to Groq when exceeded

**Groq (free tier):**
- High request limit, sufficient for fallback

## Example Deployment Workflow

```bash
# 1. Make changes locally
echo "GEMINI_API_KEY=your_key" >> .env

# 2. Test locally
streamlit run app.py

# 3. Commit and push
git add -A
git commit -m "Improve learning detection"
git push origin main

# 4. Streamlit Cloud auto-deploys
# Wait ~1-2 minutes for deployment

# 5. Check status
# Visit https://share.streamlit.io/your-username/your-repo-name
# Verify in logs and run test interaction

# 6. Monitor
# Check Firestore for data writes
# Watch sidebar for error count
```

## Production Recommendations

1. **Set up monitoring alerts** for:
   - Error frequency > 5 per hour
   - No learning activity for 2 hours
   - Firestore quota approaching limit

2. **Implement logging** to an external service:
   - Google Cloud Logging
   - Datadog
   - CloudWatch

3. **Backup Firestore** regularly:
   - GCP Console → Firestore → Backups & Schedules
   - Set daily backups with 30-day retention

4. **Version dependencies:**
   - Pin specific versions in `requirements.txt`
   - Test major updates in development before deploying

5. **Scale gradually:**
   - Monitor quota usage
   - Upgrade plans if approaching limits
   - Consider batching learning cycles during peak usage

---

**Questions?** Check the logs in Streamlit Cloud or review the README.md in the repository.
