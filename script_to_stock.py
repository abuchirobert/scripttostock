#!/usr/bin/env python3
"""
ScriptToStock - AI-powered stock image finder for CapCut video creators
SERVERLESS-READY: Single synchronous /api/generate endpoint (no threads, no polling)

SETUP:
  pip install flask anthropic requests pydub

RUN:
  python script_to_stock.py

OPEN IN BROWSER:
  http://localhost:8080
"""

import json
import os
import re
import time
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, request, jsonify, Response, session, redirect

import db
from pages import LOGIN_HTML, ADMIN_HTML

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30 days

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')


# ─────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('username'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Not signed in'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# HTML INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ScriptToStock 🎬</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
  <style>
    @keyframes slide-in {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .slide-in { animation: slide-in 0.3s ease forwards; }
    @keyframes pulse-dot {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }
    .pulse-dot { animation: pulse-dot 1.2s ease infinite; }
    input[type="file"]::file-selector-button {
      background: #334155; color: #cbd5e1; border: none;
      padding: 4px 12px; border-radius: 6px; cursor: pointer;
      margin-right: 10px; font-size: 12px;
    }
    input[type="file"]::file-selector-button:hover { background: #475569; }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
    <div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-2xl">🎬</span>
        <div>
          <h1 class="text-lg font-bold tracking-tight">ScriptToStock</h1>
          <p class="text-xs text-slate-500">AI-powered stock images synced to your audio · Ready for CapCut</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <div class="text-right">
          <div id="accountName" class="text-xs text-slate-400"></div>
          <div id="accountBalance" class="text-sm font-bold text-emerald-300">$—</div>
        </div>
        <a href="/logout" class="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg text-slate-300 transition-colors">Log out</a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-5 gap-8">

    <!-- ── LEFT: Inputs (2/5 width) ── -->
    <div class="lg:col-span-2 space-y-5">

      <!-- Account / Credit -->
      <div class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">💳 Your Credit</h2>
        <div class="flex items-end justify-between mb-3">
          <div>
            <div class="text-xs text-slate-500">Available balance</div>
            <div id="balanceBig" class="text-3xl font-bold text-emerald-300">$—</div>
          </div>
          <div class="text-right text-xs text-slate-500">
            <div id="spentInfo"></div>
            <div id="runsInfo"></div>
          </div>
        </div>
        <div id="lowBalanceWarning" class="hidden bg-red-950/50 border border-red-900/50 rounded-lg p-3 text-xs text-red-200">
          ⚠️ Your balance is exhausted. Contact the admin to top up your credit.
        </div>
        <details class="mt-2">
          <summary class="text-xs text-slate-500 cursor-pointer hover:text-slate-300">Recent usage</summary>
          <div id="usageList" class="mt-2 space-y-1 text-xs text-slate-400 max-h-40 overflow-y-auto"></div>
        </details>
      </div>

      <!-- Project Info -->
      <div class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">📋 Project</h2>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-slate-400 block mb-1">Video Title</label>
            <input type="text" id="title" placeholder="e.g. Top 5 Productivity Hacks"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"/>
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Script / Voiceover Text</label>
            <textarea id="script" rows="10" placeholder="Paste your full video script here..."
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"></textarea>
            <div class="flex justify-between mt-1">
              <span id="wordCount" class="text-xs text-slate-600">0 words</span>
              <span id="estimatedDuration" class="text-xs text-slate-600"></span>
            </div>
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">
              Voiceover Audio
              <span class="text-slate-600 ml-1">(MP3/WAV — used for precise timing sync)</span>
            </label>
            <input type="file" id="audioFile" accept=".mp3,.wav,.m4a,.aac,.ogg"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-400 cursor-pointer"/>
            <p id="audioInfo" class="text-xs text-slate-600 mt-1 hidden"></p>
          </div>
        </div>
      </div>

      <!-- Generate Button -->
      <button id="generateBtn" onclick="startGeneration()"
        class="w-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-bold py-3 rounded-xl text-sm transition-colors flex items-center justify-center gap-2">
        <span>✨</span> Generate CapCut Images
      </button>

      <!-- Timing note -->
      <div class="bg-amber-950/50 rounded-xl border border-amber-900/50 p-4 text-xs text-amber-200 space-y-1">
        <p>⏱️ <strong>Planning takes ~15–30s</strong>, then media downloads directly in your browser.</p>
      </div>

      <!-- Tips -->
      <div class="bg-slate-900/50 rounded-xl border border-slate-800/50 p-4 text-xs text-slate-500 space-y-1">
        <p>💡 <strong class="text-slate-400">Tip:</strong> Upload your voiceover audio for frame-perfect timing.</p>
        <p>💡 Without audio, timing is estimated from word count (~130 wpm).</p>
        <p>💡 Images are sourced from Pexels — free for commercial use.</p>
      </div>
    </div>

    <!-- ── RIGHT: Results (3/5 width) ── -->
    <div class="lg:col-span-3 space-y-4">

      <!-- Empty state -->
      <div id="emptyState" class="bg-slate-900 rounded-2xl border border-slate-800 p-16 text-center">
        <div class="text-5xl mb-4">🖼️</div>
        <h3 class="font-semibold text-slate-300 mb-2">Ready when you are</h3>
        <p class="text-sm text-slate-500">Fill in your script and click Generate.<br/>Your ZIP will be ready to download when processing completes.</p>
      </div>

      <!-- Generating state -->
      <div id="generatingCard" class="hidden bg-slate-900 rounded-2xl border border-slate-800 p-5">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="pulse-dot inline-block w-2 h-2 rounded-full bg-blue-500"></span>
            <span id="generatingLabel" class="font-semibold text-sm">Analyzing your script...</span>
          </div>
          <span id="progressCount" class="text-xs text-slate-500"></span>
        </div>
        <div class="bg-slate-800 rounded-full h-2 mb-3 overflow-hidden">
          <div id="progressBar" class="bg-blue-500 h-2 rounded-full transition-all duration-300" style="width:5%"></div>
        </div>
        <div id="sceneProgress" class="space-y-1 text-xs text-slate-400 max-h-64 overflow-y-auto"></div>
      </div>

      <!-- Success state -->
      <div id="successCard" class="hidden bg-gradient-to-br from-emerald-950 to-emerald-900 rounded-2xl border border-emerald-800 p-5">
        <div class="flex items-center gap-2 mb-4">
          <span class="text-2xl">✅</span>
          <h3 class="font-semibold text-emerald-100">Done! Your B-rolls are ready.</h3>
        </div>
        <button id="downloadBtn" onclick="performDownload()"
          class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2 rounded-lg mb-4 text-sm transition-colors">
          ⬇️ Download ZIP
        </button>
        <div id="statsContainer" class="grid grid-cols-2 gap-2 text-xs text-emerald-200">
          <!-- Stats will be inserted here -->
        </div>
      </div>

      <!-- Error state -->
      <div id="errorCard" class="hidden bg-gradient-to-br from-red-950 to-red-900 rounded-2xl border border-red-800 p-5">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-2xl">❌</span>
          <h3 class="font-semibold text-red-100">Something went wrong</h3>
        </div>
        <p id="errorMessage" class="text-xs text-red-200 mb-3"></p>
        <button onclick="resetUI()"
          class="w-full bg-red-700 hover:bg-red-600 text-white font-bold py-2 rounded-lg text-sm transition-colors">
          Try Again
        </button>
      </div>
    </div>
  </main>

  <script>
    // ── Account / balance ────────────────────────────────────────────────
    async function loadAccount() {
      try {
        const resp = await fetch('/api/me');
        if (resp.status === 401) { window.location.href = '/login'; return; }
        const d = await resp.json();
        document.getElementById('accountName').textContent = d.username;
        document.getElementById('accountBalance').textContent = '$' + d.balance.toFixed(2);
        document.getElementById('balanceBig').textContent = '$' + d.balance.toFixed(2);
        document.getElementById('spentInfo').textContent = 'Spent: $' + d.total_spent.toFixed(2);
        document.getElementById('runsInfo').textContent = 'Runs: ' + d.runs;
        const out = d.balance <= 0;
        document.getElementById('lowBalanceWarning').classList.toggle('hidden', !out);
        document.getElementById('balanceBig').className =
          'text-3xl font-bold ' + (out ? 'text-red-400' : 'text-emerald-300');
        document.getElementById('generateBtn').disabled = out;
        document.getElementById('usageList').innerHTML = (d.usage || []).map(u =>
          `<div class="flex justify-between border-b border-slate-800/50 pb-1">
             <span>${new Date(u.ts * 1000).toLocaleDateString()} · ${u.title || 'Untitled'}</span>
             <span class="text-emerald-400">-$${u.charged_usd.toFixed(4)}</span>
           </div>`).join('') || '<div class="text-slate-600">No runs yet.</div>';
      } catch (e) { console.warn('Account load failed', e); }
    }

    // Update word count and estimated duration
    document.getElementById('script').addEventListener('input', function() {
      const words = this.value.trim().split(/\s+/).filter(w => w).length;
      document.getElementById('wordCount').textContent = words + ' words';
      const secs = (words / 130) * 60;
      const mins = (secs / 60).toFixed(1);
      document.getElementById('estimatedDuration').textContent = `≈ ${mins} min`;
    });

    // Handle audio file
    document.getElementById('audioFile').addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (!file) {
        document.getElementById('audioInfo').classList.add('hidden');
        return;
      }
      document.getElementById('audioInfo').textContent = `✓ ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
      document.getElementById('audioInfo').classList.remove('hidden');
    });

    // ── Generation: plan on server, download + zip in the browser ────────
    function setProgress(pct, label, count) {
      document.getElementById('progressBar').style.width = pct + '%';
      if (label) document.getElementById('generatingLabel').textContent = label;
      document.getElementById('progressCount').textContent = count || '';
    }

    function sceneRow(id, text, state) {
      const icons = { pending: '⏳', ok: '✅', fail: '⚠️' };
      return `<div id="${id}" class="flex items-center gap-2">
        <span>${icons[state] || '⏳'}</span><span class="truncate">${text}</span></div>`;
    }

    async function fetchMedia(url) {
      // Try direct CDN download first (fast, no server load);
      // fall back to the server proxy if CORS blocks it.
      try {
        const r = await fetch(url, { mode: 'cors' });
        if (r.ok) return await r.blob();
        throw new Error('HTTP ' + r.status);
      } catch (e) {
        const r = await fetch('/api/proxy-media?url=' + encodeURIComponent(url));
        if (!r.ok) throw new Error('Proxy failed: HTTP ' + r.status);
        return await r.blob();
      }
    }

    async function startGeneration() {
      const title = document.getElementById('title').value.trim();
      const script = document.getElementById('script').value.trim();
      const audioFile = document.getElementById('audioFile').files[0];

      if (!script) { alert('Please enter a script.'); return; }

      // Get audio duration if provided
      let audioDuration = null;
      if (audioFile) {
        try {
          const audio = new Audio(URL.createObjectURL(audioFile));
          await new Promise(resolve => { audio.onloadedmetadata = resolve; });
          audioDuration = audio.duration;
        } catch (e) { console.warn('Could not read audio duration:', e); }
      }

      // Show generating state
      document.getElementById('emptyState').classList.add('hidden');
      document.getElementById('successCard').classList.add('hidden');
      document.getElementById('errorCard').classList.add('hidden');
      document.getElementById('generatingCard').classList.remove('hidden');
      document.getElementById('sceneProgress').innerHTML = '';
      document.getElementById('generateBtn').disabled = true;
      setProgress(5, 'Analyzing your script with AI...');

      try {
        // ── Step 1: server plans scenes + finds media URLs ──────────────
        const resp = await fetch('/api/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title || 'My Video', script, audio_duration: audioDuration })
        });
        if (resp.status === 401) { window.location.href = '/login'; return; }
        const plan = await resp.json();
        if (!resp.ok) throw new Error(plan.error || `HTTP ${resp.status}`);

        // ── Step 2: browser downloads media directly from Pexels CDN ───
        const scenes = plan.scenes;
        const toFetch = scenes.filter(s => s.success && s.media_url);
        setProgress(15, 'Downloading media in your browser...', `0 / ${toFetch.length}`);
        const progEl = document.getElementById('sceneProgress');
        toFetch.forEach((s, i) => {
          progEl.insertAdjacentHTML('beforeend', sceneRow('sc-' + i, s.filename, 'pending'));
        });

        const zip = new JSZip();
        let done = 0;
        const CONCURRENCY = 4;
        let cursor = 0;
        async function worker() {
          while (cursor < toFetch.length) {
            const i = cursor++;
            const s = toFetch[i];
            try {
              const blob = await fetchMedia(s.media_url);
              zip.file(s.filename, blob, { compression: 'STORE' });
              document.getElementById('sc-' + i).outerHTML = sceneRow('sc-' + i, s.filename, 'ok');
            } catch (e) {
              s.success = false;
              document.getElementById('sc-' + i).outerHTML =
                sceneRow('sc-' + i, s.filename + ' — download failed', 'fail');
            }
            done++;
            setProgress(15 + Math.round((done / toFetch.length) * 75),
              'Downloading media in your browser...', `${done} / ${toFetch.length}`);
          }
        }
        await Promise.all(Array.from({ length: CONCURRENCY }, worker));

        // ── Step 3: build the ZIP client-side ───────────────────────────
        setProgress(92, 'Packaging your ZIP...');
        zip.file('CAPCUT_IMPORT_GUIDE.txt', plan.guide);
        zip.file('scenes_data.json', JSON.stringify(plan.scenes.map(({media_url, ...rest}) => rest), null, 2));
        window.downloadBlob = await zip.generateAsync({ type: 'blob' });
        window.downloadFilename = plan.zip_name || 'capcut_brolls.zip';
        setProgress(100, 'Done!');

        // Show success state
        document.getElementById('generatingCard').classList.add('hidden');
        document.getElementById('successCard').classList.remove('hidden');

        const st = plan.stats;
        const stats = [
          { label: '🎬 B-rolls', value: st.scenes },
          { label: '📽 Videos', value: st.videos },
          { label: '🖼 Images', value: st.images },
          { label: '⏱ Duration', value: `${st.duration.toFixed(1)}s` },
          { label: '💰 Charged', value: `$${st.charged.toFixed(4)}` },
          { label: '💳 Balance left', value: `$${st.balance.toFixed(2)}` }
        ];
        document.getElementById('statsContainer').innerHTML = stats.map(s =>
          `<div class="border border-emerald-700 rounded p-2"><div class="text-xs text-emerald-400">${s.label}</div><div class="text-sm font-bold">${s.value}</div></div>`
        ).join('');
        loadAccount();
      } catch (err) {
        document.getElementById('generatingCard').classList.add('hidden');
        document.getElementById('errorCard').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = err.message;
        loadAccount();
      } finally {
        document.getElementById('generateBtn').disabled = false;
      }
    }

    // Perform download
    function performDownload() {
      if (!window.downloadBlob) return;
      const url = URL.createObjectURL(window.downloadBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = window.downloadFilename || 'capcut_brolls.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    // Reset UI
    function resetUI() {
      document.getElementById('emptyState').classList.remove('hidden');
      document.getElementById('generatingCard').classList.add('hidden');
      document.getElementById('successCard').classList.add('hidden');
      document.getElementById('errorCard').classList.add('hidden');
    }

    loadAccount();
  </script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (pure, unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def make_slug(text, max_len=40):
    """Turn a description into a clean hyphenated filename slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = text[:max_len].rstrip('-')
    return text or 'scene'


def make_filename(cumulative_s, description, pexels_label, duration, ext):
    """
    Build a descriptive timestamped filename.
    e.g. 00m15s_seniors-taking-statins_4.5s.jpg
    """
    mins = int(cumulative_s // 60)
    secs = int(cumulative_s % 60)
    ts = f"{mins:02d}m{secs:02d}s"
    label_text = pexels_label if (pexels_label and len(pexels_label.split()) >= 2) else description
    slug = make_slug(label_text)
    return f"{ts}_{slug}_{duration:.1f}s{ext}"


def find_pexels_video_url(query, pexels_key, req_module):
    """
    Search Pexels Videos API and return (download_url, photographer, alt_title).
    Picks the HIGHEST quality MP4 capped at 1080p. Metadata only — the actual
    file is downloaded by the user's browser straight from the Pexels CDN.
    Returns (None, None, None) if nothing found.
    """
    req = req_module
    fallbacks = [
        query,
        ' '.join(query.split()[:2]) if len(query.split()) > 2 else None,
        query.split()[0],
    ]
    for q in [x for x in fallbacks if x]:
        try:
            url = (
                f"https://api.pexels.com/videos/search"
                f"?query={req.utils.quote(q)}&per_page=5&orientation=landscape"
            )
            r = req.get(url, headers={'Authorization': pexels_key}, timeout=10)
            if r.status_code != 200:
                continue
            videos = r.json().get('videos', [])
            if not videos:
                continue

            video = videos[0]
            photographer = video.get('user', {}).get('name', 'Pexels')
            alt_title = video.get('url', '').rstrip('/').split('/')[-1].replace('-', ' ')

            # Pick HIGHEST quality MP4 capped at 1080p (Full HD)
            files = [f for f in video.get('video_files', [])
                     if 'mp4' in f.get('file_type', '')]
            files.sort(key=lambda f: (f.get('width') or 0) * (f.get('height') or 0))
            capped = [f for f in files
                      if (f.get('height') or 0) <= 1080 and (f.get('width') or 0) <= 1920]
            # Best file within 1080p; if only larger files exist, take the smallest of those
            target = capped[-1] if capped else (files[0] if files else None)
            if not target:
                continue
            return target['link'], photographer, alt_title
        except Exception:
            time.sleep(0.3)
    return None, None, None


def find_pexels_photo_url(query, pexels_key, req_module):
    """
    Search Pexels Photos API and return (download_url, photographer, alt_text).
    Highest quality: original file scaled to 1080p via Pexels CDN params.
    Returns (None, None, None) if nothing found; ('AUTH_ERROR', None, None) on 401.
    """
    req = req_module
    fallbacks = [
        query,
        ' '.join(query.split()[:2]) if len(query.split()) > 2 else None,
        query.split()[0],
        'professional background',
    ]
    for q in [x for x in fallbacks if x]:
        try:
            url = (
                f"https://api.pexels.com/v1/search"
                f"?query={req.utils.quote(q)}&per_page=5&orientation=landscape"
            )
            r = req.get(url, headers={'Authorization': pexels_key}, timeout=10)
            if r.status_code == 401:
                return 'AUTH_ERROR', None, None
            if r.status_code != 200:
                continue
            photos = r.json().get('photos', [])
            if not photos:
                continue
            photo = photos[0]
            # Highest quality: original file scaled to 1080p height via Pexels CDN
            original = photo['src'].get('original') or ''
            if original:
                sep = '&' if '?' in original else '?'
                img_url = f"{original}{sep}auto=compress&cs=tinysrgb&h=1080"
            else:
                img_url = photo['src'].get('large2x') or photo['src'].get('large') or ''
            alt = photo.get('alt', '') or ''
            photographer = photo.get('photographer', 'Pexels')
            if img_url:
                return img_url, photographer, alt
        except Exception:
            time.sleep(0.3)
    return None, None, None


def find_phrase_ratio(script, phrase):
    """
    Find where a phrase appears in the script and return its position as a
    ratio 0.0–1.0 (start → end of script). Tries progressively shorter
    substrings for robustness when Claude paraphrases slightly.
    Returns None if not found.
    """
    if not phrase or not script:
        return None
    script_lower = script.lower()
    phrase_words = phrase.lower().split()
    total_chars = len(script_lower)

    # Try matching 6, 5, 4, 3 consecutive words from the phrase
    for n in range(min(6, len(phrase_words)), 2, -1):
        snippet = ' '.join(phrase_words[:n])
        idx = script_lower.find(snippet)
        if idx != -1:
            return idx / total_chars
    return None


def build_guide(title, scenes, total_duration, audio_duration):
    """Build the human-readable CapCut import guide."""
    video_count = sum(1 for s in scenes if s.get('success') and s.get('media_type') == 'video')
    image_count = sum(1 for s in scenes if s.get('success') and s.get('media_type') == 'image')
    success_count = video_count + image_count

    lines = [
        "=" * 66,
        f"  SCRIPTOSTOCK — CAPCUT B-ROLL IMPORT GUIDE",
        f"  \"{title}\"",
        "=" * 66,
        "",
        "HOW TO USE THESE B-ROLLS IN CAPCUT",
        "-" * 50,
        "  These are OVERLAY B-rolls, not replacement clips.",
        "  Your main timeline = voiceover audio (+ face cam if any).",
        "  B-rolls sit ON TOP of the audio at the times shown below.",
        "",
        "  WORKFLOW:",
        "  1. Open CapCut → New Project → add your voiceover audio",
        "  2. Tap '+' → import all .jpg and .mp4 files from this folder",
        "  3. DRAG each clip to the overlay/PIP track above the audio",
        "  4. Position the clip's START at the timestamp shown below",
        "     (filenames begin with the timestamp for easy sorting)",
        "  5. For .jpg images: set clip duration to the 'Xs' in filename",
        "  6. For .mp4 videos: trim clip to the 'Xs' in filename",
        "  7. Repeat for every B-roll → add music → export 1080p/4K",
        "",
        "  FILENAME KEY:  00m15s_blood-sugar-meter-reading_4.0s.jpg",
        "                 ^^^^^^  ←timeline start    ^^^^  ←duration",
        "",
        "=" * 66,
    ]

    dur_label = f"{total_duration:.1f}s ({total_duration/60:.1f} min)"
    if audio_duration:
        lines += [
            f"  ⏱  AUDIO LENGTH   : {audio_duration:.2f}s",
            f"  🎬  B-ROLLS PLACED : {success_count} clips across the video",
        ]
    else:
        lines += [
            f"  🎬  VIDEO LENGTH   : {dur_label} (estimated)",
            f"  📋  B-ROLLS PLACED : {success_count} clips",
        ]

    lines += [
        f"  📽  VIDEOS        : {video_count}",
        f"  🖼  IMAGES        : {image_count}",
        "=" * 66,
        "",
        "B-ROLL CUE LIST  (chronological order)",
        "-" * 66,
    ]

    for s in scenes:
        start = s.get('timeline_start', 0.0)
        end = round(start + s['duration'], 2)
        mins = int(start // 60)
        secs = start % 60
        mtype = '📽 VIDEO' if s.get('media_type') == 'video' else '🖼 IMAGE'
        if s['success']:
            lines += [
                "",
                f"  ▶  {mins:02d}:{secs:04.1f}   {mtype}",
                f"  File      : {s['filename']}",
                f"  Duration  : {s['duration']:.1f}s  (place at {start:.1f}s → {end:.1f}s)",
                f"  On phrase : \"{s.get('phrase', '')}\"",
                f"  Shows     : {s['description']}",
                f"  Why       : {s.get('rationale', '')}",
                f"  Credit    : {s['photographer']} on Pexels",
            ]
            if s.get('media_type') == 'video':
                lines.append(f"  ⚠ Trim    : Cut video to exactly {s['duration']:.1f}s in CapCut")
        else:
            lines += [
                "",
                f"  ⚠  {mins:02d}:{secs:04.1f}  — No media found for: \"{s['query']}\"",
                f"     Manually add footage here ({s['duration']:.1f}s)",
            ]

    lines += [
        "",
        "=" * 66,
        "  All media sourced from Pexels — free for commercial use.",
        "  License: pexels.com/license",
        "",
        "  Generated by ScriptToStock · Powered by Claude AI",
        "=" * 66,
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# COST CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

COST_INPUT_PER_MTOK = 0.80
COST_OUTPUT_PER_MTOK = 4.00


# ─────────────────────────────────────────────────────────────────────────────
# CORE SYNCHRONOUS GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_plan(title, script, claude_key, pexels_key, audio_duration):
    """
    Parse script with Claude → search Pexels for media URLs (no downloads).
    The browser downloads media directly from the Pexels CDN and builds the
    ZIP client-side, keeping the server fast and light.
    Returns: (scenes_list, guide_text, metadata_dict)
    Raises: Exception with user-facing error message.
    """
    import anthropic
    import requests as req

    # ── Step 1: Parse script with Claude ──────────────────────────────────
    try:
        client = anthropic.Anthropic(api_key=claude_key)
    except anthropic.AuthenticationError:
        raise Exception('Invalid Claude API key. Check your key at console.anthropic.com')

    word_count = len(script.split())
    total_secs = audio_duration if audio_duration else (word_count / 130) * 60
    target_brolls = max(5, min(80, int(total_secs / 30)))

    prompt = f"""You are a world-class video editor with 20+ years of experience and deep expertise in viewer psychology, attention retention, and B-roll selection.

Your job: read this script for "{title}" and identify exactly {target_brolls} B-roll moments that will MAXIMISE viewer retention and engagement.

VIDEO LENGTH: ~{int(total_secs)}s  |  WORDS: {word_count}  |  B-ROLLS TO PLACE: {target_brolls}

━━━ EXPERT PRINCIPLES TO APPLY ━━━

1. NUMBERED LISTS / TIPS — Every single numbered or bulleted point MUST get its own B-roll showing the OUTCOME, not the concept.
   Example: "reduces blood sugar" → query "glucose meter normal reading finger" NOT "diabetes" or "sugar"

2. SHOW THE RESULT, NOT THE TOPIC — Viewers feel the benefit vicariously when they see the end state.
   "improves sleep" → sleeping person peaceful bedroom soft light
   "boosts energy" → energetic person running sunrise outdoors

3. EMOTIONAL HOOKS — Match the psychological trigger precisely.
   Fear → dark, urgent imagery.  Desire → aspirational, bright.  Curiosity → close-up details.  Relief → calm, open spaces.

4. PATTERN INTERRUPT every 30–45 seconds — Switch from wide shots to close-ups, from indoor to outdoor, from people to objects. Resets viewer attention.

5. SOCIAL PROOF MOMENTS — When a claim or statistic is made, show professional/scientific/authoritative imagery (lab coats, charts, research).

6. SPECIFICITY IS EVERYTHING — Never use generic queries. Be hyper-specific.
   BAD: "healthy food"   GOOD: "colorful vegetables chopping board kitchen"
   BAD: "exercise"       GOOD: "elderly woman swimming pool water"
   BAD: "technology"     GOOD: "scientist examining DNA sequence screen"

7. VARY EVERY SHOT — No two consecutive B-rolls should share the same setting, subject, or visual style.

━━━ OUTPUT FORMAT ━━━
Return ONLY a valid JSON array — no markdown, no explanation, no text outside the brackets:
[
  {{
    "cue": 1,
    "phrase": "5–8 word exact or near-exact quote from the script where this B-roll starts",
    "description": "Precise visual description of what the B-roll should show",
    "rationale": "One sentence: WHY this visual maximises retention at this moment",
    "query": "hyper-specific Pexels search query (3-5 words)",
    "duration": 4.0
  }}
]

Rules:
- "phrase" must be a real substring from the script so timestamps can be calculated
- "duration" is how long the B-roll clip shows on screen (3–7 seconds typical)
- Output exactly {target_brolls} cue objects
- Do NOT repeat any query

Script:
{script}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.RateLimitError:
        raise Exception('Claude rate limit hit. Wait a moment and try again.')
    except anthropic.APIError as e:
        raise Exception(f'Claude API error: {str(e)[:80]}')

    raw = message.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    raw = raw.strip()

    brolls = None

    try:
        brolls = json.loads(raw)
    except json.JSONDecodeError:
        pass

    if brolls is None:
        m = re.search(r'\[[\s\S]*\]', raw)
        if m:
            try:
                brolls = json.loads(m.group())
            except json.JSONDecodeError:
                pass

    if brolls is None:
        objs = re.findall(
            r'\{\s*"cue"\s*:\s*\d+[\s\S]*?"duration"\s*:\s*[\d.]+\s*\}',
            raw
        )
        if objs:
            try:
                brolls = [json.loads(o) for o in objs]
            except json.JSONDecodeError:
                pass

    if not brolls:
        preview = raw[:300].replace('\n', ' ')
        raise Exception(f'Could not parse Claude response. Preview: "{preview}"')

    # ── Cost tracking ──────────────────────────────────────────────────────
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    cost_usd = (
        (input_tokens / 1_000_000) * COST_INPUT_PER_MTOK +
        (output_tokens / 1_000_000) * COST_OUTPUT_PER_MTOK
    )

    # ── Calculate timeline_start for each B-roll ──────────────────────────
    for broll in brolls:
        phrase = str(broll.get('phrase', ''))
        ratio = find_phrase_ratio(script, phrase)
        if ratio is None:
            ratio = (broll.get('cue', 1) - 1) / max(len(brolls), 1)
        broll['timeline_start'] = round(ratio * total_secs, 2)

    brolls.sort(key=lambda b: b['timeline_start'])

    # ── Step 2: Search Pexels for media URLs (metadata only, fast) ────────
    scene_results = []

    for i, broll in enumerate(brolls):
        scene_num = i + 1
        query = str(broll.get('query', 'nature landscape')).strip()
        duration = max(2.0, min(8.0, float(broll.get('duration', 4.0))))
        description = str(broll.get('description', f'B-roll {scene_num}')).strip()
        phrase = str(broll.get('phrase', '')).strip()
        rationale = str(broll.get('rationale', '')).strip()
        timeline_start = float(broll.get('timeline_start', 0.0))

        media_url = None
        photographer = 'Pexels'
        pexels_label = ''
        media_type = 'image'
        ext = '.jpg'

        # ── Try video first ────────────────────────────────────────────────
        vurl, vphoto, vtitle = find_pexels_video_url(query, pexels_key, req)
        if vurl:
            media_url = vurl
            photographer = vphoto or 'Pexels'
            pexels_label = vtitle or description
            media_type = 'video'
            ext = '.mp4'
        else:
            # ── Fall back to photo ─────────────────────────────────────────
            purl, pphoto, palt = find_pexels_photo_url(query, pexels_key, req)
            if purl == 'AUTH_ERROR':
                raise Exception('Pexels API key is invalid. Ask the admin to update it.')
            if purl:
                media_url = purl
                photographer = pphoto or 'Pexels'
                pexels_label = palt or description
                media_type = 'image'
                ext = '.jpg'

        filename = make_filename(timeline_start, description, pexels_label, duration, ext)

        result = {
            'scene': scene_num,
            'phrase': phrase,
            'description': description,
            'rationale': rationale,
            'query': query,
            'duration': round(duration, 2),
            'filename': filename,
            'media_type': media_type,
            'photographer': photographer,
            'pexels_label': pexels_label,
            'timeline_start': round(timeline_start, 2),
            'success': media_url is not None,
            'media_url': media_url,
        }
        scene_results.append(result)

    # ── Step 3: Build guide + metadata (ZIP is built in the browser) ──────
    total_duration = round(total_secs, 2)
    guide = build_guide(title, scene_results, total_duration, audio_duration)

    success_count = sum(1 for r in scene_results if r['success'])
    video_count = sum(1 for r in scene_results if r['success'] and r['media_type'] == 'video')
    image_count = success_count - video_count

    metadata = {
        'cost_usd': round(cost_usd, 5),
        'total_duration': total_duration,
        'scenes_done': len(scene_results),
        'video_count': video_count,
        'image_count': image_count,
    }

    return scene_results, guide, metadata


# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

# ── Pages ────────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return Response(HTML, mimetype='text/html')


@app.route('/login')
def login_page():
    if session.get('is_admin'):
        return redirect('/admin')
    if session.get('username'):
        return redirect('/')
    return Response(LOGIN_HTML, mimetype='text/html')


@app.route('/admin')
@admin_required
def admin_page():
    return Response(ADMIN_HTML, mimetype='text/html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ── Auth API ─────────────────────────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Admin login (credentials from environment)
    if ADMIN_PASSWORD and username == ADMIN_USERNAME.lower() and password == ADMIN_PASSWORD:
        session.permanent = True
        session['username'] = username
        session['is_admin'] = True
        return jsonify({'ok': True, 'is_admin': True})

    # Regular user login
    user = db.verify_user(username, password)
    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401
    if not user.get('active', False):
        return jsonify({'error': 'Your access has been revoked. Contact the admin.'}), 403

    session.permanent = True
    session['username'] = user['username']
    session['is_admin'] = False
    return jsonify({'ok': True, 'is_admin': False})


@app.route('/api/me')
@login_required
def api_me():
    username = session['username']
    if session.get('is_admin'):
        return jsonify({'username': username, 'is_admin': True,
                        'balance': 0.0, 'total_spent': 0.0, 'runs': 0, 'usage': []})
    user = db.get_user(username)
    if not user or not user.get('active', False):
        session.clear()
        return jsonify({'error': 'Account not found or revoked'}), 401
    return jsonify({
        'username': username,
        'is_admin': False,
        'balance': round(user.get('balance_usd', 0.0), 4),
        'total_spent': round(user.get('total_spent_usd', 0.0), 4),
        'runs': user.get('runs', 0),
        'usage': db.get_usage(username, limit=15),
    })


# ── Generation API ───────────────────────────────────────────────────────────

@app.route('/api/plan', methods=['POST'])
@login_required
def api_plan():
    """
    Plan endpoint: Claude parse + Pexels URL search only (fast, small JSON).
    Media download + ZIP packaging happen in the user's browser.
    Charges the user actual Claude cost × markup.
    """
    username = session['username']
    is_admin = session.get('is_admin', False)

    # ── Gate: active user with balance ────────────────────────────────────
    if not is_admin:
        user = db.get_user(username)
        if not user or not user.get('active', False):
            session.clear()
            return jsonify({'error': 'Your access has been revoked. Contact the admin.'}), 403
        if user.get('balance_usd', 0.0) <= 0:
            return jsonify({'error': 'Your credit is exhausted. Contact the admin to top up.'}), 402

    # ── Resolve API keys (admin-managed; users never see them) ────────────
    settings = db.get_settings()
    claude_key = settings['claude_key']
    pexels_key = settings['pexels_key']
    if not claude_key or not pexels_key:
        return jsonify({'error': 'The service is not configured yet (missing API keys). Contact the admin.'}), 503

    data = request.json or {}
    title = (data.get('title') or 'My Video').strip()
    script = (data.get('script') or '').strip()
    audio_duration = data.get('audio_duration')

    if not script:
        return jsonify({'error': 'Please provide a script.'}), 400

    if audio_duration is not None:
        try:
            audio_duration = float(audio_duration)
        except (TypeError, ValueError):
            audio_duration = None

    # ── Generate the plan ─────────────────────────────────────────────────
    try:
        scenes, guide, metadata = generate_plan(title, script, claude_key, pexels_key, audio_duration)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # ── Charge the user (actual cost × markup); admin runs are free ───────
    charged = 0.0
    balance = 0.0
    if not is_admin:
        charged = round(metadata['cost_usd'] * settings['markup'], 4)
        db.charge_user(username, metadata['cost_usd'], charged, title, metadata)
        user = db.get_user(username)
        balance = round(user.get('balance_usd', 0.0), 4)

    # ── Build ZIP filename ────────────────────────────────────────────────
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'\s+', '_', safe_title)[:60] or 'capcut_brolls'

    return jsonify({
        'scenes': scenes,
        'guide': guide,
        'zip_name': f"{safe_title}_brolls.zip",
        'stats': {
            'scenes': metadata['scenes_done'],
            'videos': metadata['video_count'],
            'images': metadata['image_count'],
            'duration': metadata['total_duration'],
            'charged': charged,
            'balance': balance,
        },
    })


ALLOWED_PROXY_HOSTS = ('.pexels.com', 'pexels.com')


@app.route('/api/proxy-media')
@login_required
def proxy_media():
    """
    Fallback media proxy for the rare case the browser can't fetch a Pexels
    CDN file directly (CORS). Restricted to pexels.com hosts.
    """
    url = request.args.get('url', '')
    host = urlparse(url).hostname or ''
    if not (host == 'pexels.com' or host.endswith('.pexels.com')):
        return jsonify({'error': 'Invalid media host'}), 400
    try:
        import requests as req
        r = req.get(url, timeout=60)
        if r.status_code != 200:
            return jsonify({'error': f'Upstream returned {r.status_code}'}), 502
        ctype = r.headers.get('Content-Type', 'application/octet-stream')
        return Response(r.content, mimetype=ctype)
    except Exception as e:
        return jsonify({'error': str(e)[:100]}), 502


# ── Admin API ────────────────────────────────────────────────────────────────

@app.route('/api/admin/overview')
@admin_required
def admin_overview():
    settings = db.get_settings()
    return jsonify({
        'users': [{
            'username': u['username'],
            'balance_usd': round(u.get('balance_usd', 0.0), 4),
            'total_spent_usd': round(u.get('total_spent_usd', 0.0), 4),
            'runs': u.get('runs', 0),
            'active': u.get('active', False),
        } for u in db.list_users()],
        'settings': {
            'markup': settings['markup'],
            'claude_key_set': bool(settings['claude_key']),
            'pexels_key_set': bool(settings['pexels_key']),
        },
        'totals': db.totals(),
    })


@app.route('/api/admin/usage')
@admin_required
def admin_usage():
    username = request.args.get('username') or None
    return jsonify({'usage': db.get_usage(username, limit=100)})


@app.route('/api/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.json or {}
    try:
        db.create_user(
            data.get('username', ''),
            data.get('password', ''),
            balance_usd=float(data.get('credit') or 0),
        )
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/admin/users/<username>/credit', methods=['POST'])
@admin_required
def admin_add_credit(username):
    amount = (request.json or {}).get('amount')
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount'}), 400
    if not db.get_user(username):
        return jsonify({'error': 'User not found'}), 404
    db.add_credit(username, amount)
    return jsonify({'ok': True})


@app.route('/api/admin/users/<username>/toggle', methods=['POST'])
@admin_required
def admin_toggle_user(username):
    user = db.get_user(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    db.set_user_active(username, not user.get('active', False))
    return jsonify({'ok': True})


@app.route('/api/admin/users/<username>/password', methods=['POST'])
@admin_required
def admin_set_password(username):
    password = (request.json or {}).get('password') or ''
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    if not db.get_user(username):
        return jsonify({'error': 'User not found'}), 404
    db.set_user_password(username, password)
    return jsonify({'ok': True})


@app.route('/api/admin/users/<username>', methods=['DELETE'])
@admin_required
def admin_delete_user(username):
    if not db.get_user(username):
        return jsonify({'error': 'User not found'}), 404
    db.delete_user(username)
    return jsonify({'ok': True})


@app.route('/api/admin/settings', methods=['POST'])
@admin_required
def admin_settings():
    data = request.json or {}
    db.update_settings(
        claude_key=data.get('claude_key'),
        pexels_key=data.get('pexels_key'),
        markup=data.get('markup'),
    )
    return jsonify({'ok': True})


@app.route('/api/admin/test-keys', methods=['POST'])
@admin_required
def admin_test_keys():
    settings = db.get_settings()
    result = {'claude': {'ok': False, 'error': 'Not set'},
              'pexels': {'ok': False, 'error': 'Not set'}}

    if settings['claude_key']:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings['claude_key'])
            client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=10,
                messages=[{'role': 'user', 'content': 'Hi'}]
            )
            result['claude'] = {'ok': True, 'error': ''}
        except Exception as e:
            result['claude'] = {'ok': False, 'error': str(e)[:60]}

    if settings['pexels_key']:
        try:
            import requests as req
            r = req.get(
                'https://api.pexels.com/v1/search?query=nature&per_page=1',
                headers={'Authorization': settings['pexels_key']},
                timeout=8
            )
            result['pexels'] = ({'ok': True, 'error': ''} if r.status_code == 200
                                else {'ok': False, 'error': f'HTTP {r.status_code}'})
        except Exception as e:
            result['pexels'] = {'ok': False, 'error': str(e)[:60]}

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print("=" * 52)
    print("  🎬  ScriptToStock is running!")
    print()
    print("  Open in your browser:")
    print("  ➜  http://localhost:8080")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 52)
    print()
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
