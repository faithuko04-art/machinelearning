# 🧠 Advanced Learning System - User Guide

## What's New

Your AI has 2 new learning modes that make it smarter over time:

---

## 1. ⏱️ Automatic Quick Learning (Every 60 seconds)

**How it works:**
- Every 60 seconds, the AI automatically learns from unknown concepts
- Uses **Groq** for fast, efficient learning (1-2 seconds per concept)
- No action needed - it happens in the background!

**What you see:**
- Small countdown timer in the sidebar showing seconds until next learning
- Progress bar filling up
- Status shows how many concepts were learned in the last cycle

**Learning Priority:**
- Top 3 unknown concepts per cycle
- Incorporates web research
- Auto-categorizes knowledge (Factual, Conceptual, Procedural, Adversarial)

---

## 2. 🧠 Deep Learning - Manual Trigger

**When to use:**
- Click **"🧠 Deep Learn"** button to do comprehensive learning right now
- Best after getting answers you like - reinforces good knowledge
- Expands existing knowledge on known topics

**What it does:**

### For Unknown Concepts:
- Uses **Gemini** for highest quality research (tries first)
- Falls back to **Groq** if Gemini is unavailable or errors
- Creates detailed explanations with practical applications
- Maps relationships to other concepts (hypernyms, hyponyms, etc.)

### For Known Concepts:
- **Deepens** existing knowledge with:
  - More detailed explanations
  - Practical applications
  - Related concepts
  - Common misconceptions
- Expands knowledge into subtopics and relationships

**Expected Duration:** 10-30 seconds depending on concept count

---

## 3. 👍 / 👎 Feedback Buttons (Now with Rethinking!)

**When you click 👎 (thumbs down):**
1. Triggers **immediate research** on your question
2. AI researches the topic using web search
3. **Gemini** synthesizes a corrected answer (with fallback to **Groq**)
4. Shows you the corrected answer with sources
5. **Learns from the mistake** for future use

**The Gemini→Groq Fallback:**
```
If Gemini fails (404, unavailable, etc):
  → Falls back to Groq automatically
  → Still gets you a corrected answer
  → No interruption to the learning flow
```

---

## Learning Speed Timeline

```
User asks question
    ↓
AI responds
    ↓
Every 60 seconds automatically:
    → Quick Learn (Groq) learns top unknowns
    ↓
User clicking 👎:
    → Immediate Rethink (Gemini→Groq) with research
    ↓
User clicking 🧠 Deep Learn:
    → Comprehensive expansion of both known & unknown
```

---

## Backend Changes Summary

### New Files:
- **`logic/advanced_learning.py`** - Manages all learning cycles

### Updated Files:
- **`logic/rethink.py`** - Now handles Gemini→Groq fallback, returns strings
- **`app.py`** - Added countdown timer, learning controls, feedback wiring

### Key Features:
✅ 1-minute automatic learning cycle  
✅ Manual Deep Learning trigger  
✅ Gemini→Groq fallback for errors  
✅ Fixed 👎 feedback to trigger rethinking  
✅ Learning status tracking  
✅ Research integration for corrections  

---

## Testing the System

### Quick Test:
1. Ask a question → Get an answer
2. Click 👎 if the answer needs fixing
3. Watch the AI research and correct itself
4. Check the sidebar countdown timer

### Deep Learning Test:
1. Click 🧠 Deep Learn button
2. Watch sidebar show "Learning..." status
3. Check toast notification for results (e.g., "Learned 2 unknowns, deepened 3 concepts")

### Automatic Learning:
1. Watch the countdown timer
2. When it hits 0, it automatically learns from unknowns
3. Sidebar updates with new status

---

## API Usage (Groq vs Gemini)

**Groq:**
- ⚡ Ultra-fast (1-2s responses)
- For quick categorization and pattern learning
- Triggers every 60 seconds automatically

**Gemini:**
- 🎯 Highest quality research
- For correcting mistakes (user feedback)
- For deep learning expansions
- Falls back automatically if unavailable

---

## Your .env Configuration

Make sure you have these set:
```bash
GEMINI_API_KEY=your_key        # For quality research & corrections
GROQ_API_KEY=your_key          # For fast learning cycles
GEMINI_MODEL=gemini-2.5-flash-lite  # Your allowed model
```

---

## Common Questions

**Q: Why does learning happen so slowly?**  
A: Learning happens EVERY 60 SECONDS automatically! But it only learns 3 concepts per cycle to stay efficient. Click 🧠 Deep Learn to force comprehensive learning right now.

**Q: What if Gemini fails or is unavailable?**  
A: The system automatically falls back to Groq. The correction still happens, just potentially with different synthesized responses.

**Q: Does the 👎 button work now?**  
A: Yes! Fixed and fully functional. It now:
- Researches your question
- Synthesizes a corrected answer
- Uses Gemini→Groq fallback
- Logs the correction for learning

**Q: Can I turn off automatic learning?**  
A: Not yet, but you can just use the Quick Learn / Deep Learn buttons manually.

---

## That's it! 🚀

Your AI is now learning actively:
- **Every 60 seconds**: Automatically learns unknowns (Groq)
- **On feedback (👎)**: Immediately rethinks with research (Gemini→Groq)
- **On Deep Learn**: Comprehensively expands knowledge (Gemini→Groq)

Enjoy the smarter AI!
