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
import io
import zipfile
import re
import time

from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)


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
    <div class="max-w-7xl mx-auto px-6 py-4 flex items-center gap-3">
      <span class="text-2xl">🎬</span>
      <div>
        <h1 class="text-lg font-bold tracking-tight">ScriptToStock</h1>
        <p class="text-xs text-slate-500">AI-powered stock images synced to your audio · Ready for CapCut</p>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-5 gap-8">

    <!-- ── LEFT: Inputs (2/5 width) ── -->
    <div class="lg:col-span-2 space-y-5">

      <!-- API Keys -->
      <div class="bg-slate-900 rounded-2xl border border-slate-800 p-5">
        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">🔑 API Keys</h2>
        <div class="space-y-3">
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs text-slate-400">Claude API Key
                <a href="https://console.anthropic.com" target="_blank" class="text-blue-400 hover:underline ml-1">Get key →</a>
              </label>
              <div class="flex items-center gap-1.5">
                <span id="claudeStatus" class="text-xs px-2 py-0.5 rounded-full border border-slate-700 text-slate-500">Not tested</span>
                <button onclick="testClaudeKey()" class="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-0.5 rounded-lg transition-colors">Test</button>
              </div>
            </div>
            <input type="password" id="claudeKey" placeholder="sk-ant-..."
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"/>
          </div>
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs text-slate-400">Pexels API Key
                <a href="https://www.pexels.com/api/" target="_blank" class="text-blue-400 hover:underline ml-1">Free key →</a>
              </label>
              <div class="flex items-center gap-1.5">
                <span id="pexelsStatus" class="text-xs px-2 py-0.5 rounded-full border border-slate-700 text-slate-500">Not tested</span>
                <button onclick="testPexelsKey()" class="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-0.5 rounded-lg transition-colors">Test</button>
              </div>
            </div>
            <input type="password" id="pexelsKey" placeholder="Your Pexels API key"
              class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"/>
          </div>
          <p class="text-xs text-slate-600">Keys are saved locally in your browser only.</p>
        </div>
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

      <!-- Serverless Warning -->
      <div class="bg-amber-950/50 rounded-xl border border-amber-900/50 p-4 text-xs text-amber-200 space-y-1">
        <p>⏱️ <strong>Processing may take 1–4 minutes.</strong> </p>
        
        <!-- On serverless hosts (Vercel/Netlify), requests timeout after 60s. For long scripts, run locally or use Render/Railway.</p> -->
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
            <span class="font-semibold text-sm">Generating — please wait...</span>
          </div>
        </div>
        <div class="bg-slate-800 rounded-full h-2 mb-3 overflow-hidden">
          <div class="bg-blue-500 h-2 rounded-full animate-pulse" style="width:100%"></div>
        </div>
        <p class="text-xs text-slate-400">This usually takes 1–4 minutes depending on script length and server load.</p>
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
    // Load keys from localStorage
    function loadKeys() {
      const saved = localStorage.getItem('api_keys');
      if (saved) {
        const { claude, pexels } = JSON.parse(saved);
        if (claude) document.getElementById('claudeKey').value = claude;
        if (pexels) document.getElementById('pexelsKey').value = pexels;
      }
    }

    // Save keys to localStorage
    function saveKeys() {
      localStorage.setItem('api_keys', JSON.stringify({
        claude: document.getElementById('claudeKey').value,
        pexels: document.getElementById('pexelsKey').value
      }));
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

    // Test Claude key
    async function testClaudeKey() {
      const key = document.getElementById('claudeKey').value.trim();
      if (!key) {
        document.getElementById('claudeStatus').textContent = 'No key';
        return;
      }
      document.getElementById('claudeStatus').textContent = 'Testing...';
      try {
        const resp = await fetch('/api/test-claude', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ claude_key: key })
        });
        const data = await resp.json();
        document.getElementById('claudeStatus').textContent = data.ok ? '✓ Valid' : '✗ Invalid';
        document.getElementById('claudeStatus').className = data.ok
          ? 'text-xs px-2 py-0.5 rounded-full border border-emerald-700 text-emerald-300'
          : 'text-xs px-2 py-0.5 rounded-full border border-red-700 text-red-300';
      } catch (e) {
        document.getElementById('claudeStatus').textContent = '✗ Error';
        document.getElementById('claudeStatus').className = 'text-xs px-2 py-0.5 rounded-full border border-red-700 text-red-300';
      }
    }

    // Test Pexels key
    async function testPexelsKey() {
      const key = document.getElementById('pexelsKey').value.trim();
      if (!key) {
        document.getElementById('pexelsStatus').textContent = 'No key';
        return;
      }
      document.getElementById('pexelsStatus').textContent = 'Testing...';
      try {
        const resp = await fetch('/api/test-pexels', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pexels_key: key })
        });
        const data = await resp.json();
        document.getElementById('pexelsStatus').textContent = data.ok ? '✓ Valid' : '✗ Invalid';
        document.getElementById('pexelsStatus').className = data.ok
          ? 'text-xs px-2 py-0.5 rounded-full border border-emerald-700 text-emerald-300'
          : 'text-xs px-2 py-0.5 rounded-full border border-red-700 text-red-300';
      } catch (e) {
        document.getElementById('pexelsStatus').textContent = '✗ Error';
        document.getElementById('pexelsStatus').className = 'text-xs px-2 py-0.5 rounded-full border border-red-700 text-red-300';
      }
    }

    // Start generation
    async function startGeneration() {
      saveKeys();

      const title = document.getElementById('title').value.trim();
      const script = document.getElementById('script').value.trim();
      const claudeKey = document.getElementById('claudeKey').value.trim();
      const pexelsKey = document.getElementById('pexelsKey').value.trim();
      const audioFile = document.getElementById('audioFile').files[0];

      if (!script) {
        alert('Please enter a script.');
        return;
      }
      if (!claudeKey) {
        alert('Please enter your Claude API key.');
        return;
      }
      if (!pexelsKey) {
        alert('Please enter your Pexels API key.');
        return;
      }

      // Get audio duration if provided
      let audioDuration = null;
      if (audioFile) {
        try {
          const audio = new Audio(URL.createObjectURL(audioFile));
          await new Promise(resolve => {
            audio.onloadedmetadata = resolve;
          });
          audioDuration = audio.duration;
        } catch (e) {
          console.warn('Could not read audio duration:', e);
        }
      }

      // Show generating state
      document.getElementById('emptyState').classList.add('hidden');
      document.getElementById('successCard').classList.add('hidden');
      document.getElementById('errorCard').classList.add('hidden');
      document.getElementById('generatingCard').classList.remove('hidden');
      document.getElementById('generateBtn').disabled = true;

      try {
        const resp = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title || 'My Video',
            script,
            claude_key: claudeKey,
            pexels_key: pexelsKey,
            audio_duration: audioDuration
          })
        });

        if (!resp.ok) {
          const errorData = await resp.json();
          throw new Error(errorData.error || `HTTP ${resp.status}`);
        }

        // Extract stats from response headers
        const costUsd = resp.headers.get('X-Cost-USD');
        const scenes = resp.headers.get('X-Scenes');
        const videos = resp.headers.get('X-Videos');
        const images = resp.headers.get('X-Images');
        const duration = resp.headers.get('X-Duration');

        // Store the response for download
        window.downloadBlob = await resp.blob();
        window.downloadFilename = extractFilename(resp.headers.get('content-disposition'));

        // Show success state
        document.getElementById('generatingCard').classList.add('hidden');
        document.getElementById('successCard').classList.remove('hidden');

        // Populate stats
        const stats = [
          { label: '🎬 B-rolls', value: scenes || '?' },
          { label: '📽 Videos', value: videos || '?' },
          { label: '🖼 Images', value: images || '?' },
          { label: '⏱ Duration', value: duration ? `${(parseFloat(duration)).toFixed(1)}s` : '?' },
          { label: '💰 Cost', value: costUsd ? `$${costUsd}` : '?' }
        ];

        const statsHtml = stats.map(s =>
          `<div class="border border-emerald-700 rounded p-2"><div class="text-xs text-emerald-400">${s.label}</div><div class="text-sm font-bold">${s.value}</div></div>`
        ).join('');

        document.getElementById('statsContainer').innerHTML = statsHtml;
      } catch (err) {
        document.getElementById('generatingCard').classList.add('hidden');
        document.getElementById('errorCard').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = err.message;
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

    // Extract filename from Content-Disposition header
    function extractFilename(contentDisposition) {
      if (!contentDisposition) return 'capcut_brolls.zip';
      const match = contentDisposition.match(/filename[^;=\n]*=(["\']?)([^"\'\n;]*)\1/i);
      return match ? match[2] : 'capcut_brolls.zip';
    }

    // Reset UI
    function resetUI() {
      document.getElementById('emptyState').classList.remove('hidden');
      document.getElementById('generatingCard').classList.add('hidden');
      document.getElementById('successCard').classList.add('hidden');
      document.getElementById('errorCard').classList.add('hidden');
    }

    // Load keys on page load
    loadKeys();
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


def fetch_pexels_video(query, pexels_key, req_module):
    """
    Search Pexels Videos API and return (bytes, photographer, alt_title).
    Prefers 720p MP4. Returns (None, None, None) if nothing found.
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

            # Pick best MP4 ≤ 720p
            files = [f for f in video.get('video_files', [])
                     if 'mp4' in f.get('file_type', '')]
            files.sort(key=lambda f: f.get('width', 0))
            target = next((f for f in files if f.get('width', 9999) <= 1280), None)
            if not target and files:
                target = files[-1]
            if not target:
                continue

            dl = req.get(target['link'], timeout=60)
            if dl.status_code == 200:
                return dl.content, photographer, alt_title
        except Exception:
            time.sleep(0.3)
    return None, None, None


def fetch_pexels_photo(query, pexels_key, req_module):
    """
    Search Pexels Photos API and return (bytes, photographer, alt_text).
    Returns (None, None, None) if nothing found.
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
            img_url = photo['src'].get('large2x') or photo['src'].get('large') or ''
            alt = photo.get('alt', '') or ''
            photographer = photo.get('photographer', 'Pexels')
            if img_url:
                dl = req.get(img_url, timeout=30)
                if dl.status_code == 200:
                    return dl.content, photographer, alt
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

def generate_brolls(title, script, claude_key, pexels_key, audio_duration):
    """
    Synchronous function: parse script → search pexels → build ZIP.
    Returns: (zip_bytes, metadata_dict)
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

    # ── Step 2: Search Pexels ──────────────────────────────────────────────
    scene_results = []

    for i, broll in enumerate(brolls):
        scene_num = i + 1
        query = str(broll.get('query', 'nature landscape')).strip()
        duration = max(2.0, min(8.0, float(broll.get('duration', 4.0))))
        description = str(broll.get('description', f'B-roll {scene_num}')).strip()
        phrase = str(broll.get('phrase', '')).strip()
        rationale = str(broll.get('rationale', '')).strip()
        timeline_start = float(broll.get('timeline_start', 0.0))

        media_data = None
        photographer = 'Pexels'
        pexels_label = ''
        media_type = 'image'
        ext = '.jpg'

        # ── Try video first ────────────────────────────────────────────────
        vdata, vphoto, vtitle = fetch_pexels_video(query, pexels_key, req)
        if vdata:
            media_data = vdata
            photographer = vphoto or 'Pexels'
            pexels_label = vtitle or description
            media_type = 'video'
            ext = '.mp4'
        else:
            # ── Fall back to photo ─────────────────────────────────────────
            pdata, pphoto, palt = fetch_pexels_photo(query, pexels_key, req)
            if pdata == 'AUTH_ERROR':
                raise Exception('Invalid Pexels API key. Check your key and try again.')
            if pdata:
                media_data = pdata
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
            'success': media_data is not None,
            '_data': media_data,
        }
        scene_results.append(result)

    # ── Step 3: Build ZIP ──────────────────────────────────────────────────
    total_duration = round(total_secs, 2)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for r in scene_results:
            if r['_data']:
                zf.writestr(r['filename'], r['_data'])

        guide = build_guide(title, scene_results, total_duration, audio_duration)
        zf.writestr('CAPCUT_IMPORT_GUIDE.txt', guide)

        clean = [{k: v for k, v in r.items() if not k.startswith('_')} for r in scene_results]
        zf.writestr('scenes_data.json', json.dumps(clean, indent=2))

    zip_bytes = zip_buffer.getvalue()

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

    return zip_bytes, metadata


# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return Response(HTML, mimetype='text/html')


@app.route('/api/test-claude', methods=['POST'])
def test_claude():
    key = (request.json or {}).get('claude_key', '').strip()
    if not key:
        return jsonify({'ok': False, 'error': 'No key provided'})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            messages=[{'role': 'user', 'content': 'Hi'}]
        )
        return jsonify({'ok': True})
    except anthropic.AuthenticationError:
        return jsonify({'ok': False, 'error': 'Invalid API key'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:80]})


@app.route('/api/test-pexels', methods=['POST'])
def test_pexels():
    key = (request.json or {}).get('pexels_key', '').strip()
    if not key:
        return jsonify({'ok': False, 'error': 'No key provided'})
    try:
        import requests as req
        r = req.get(
            'https://api.pexels.com/v1/search?query=nature&per_page=1',
            headers={'Authorization': key},
            timeout=8
        )
        if r.status_code == 200:
            return jsonify({'ok': True})
        elif r.status_code == 401:
            return jsonify({'ok': False, 'error': 'Invalid API key'})
        else:
            return jsonify({'ok': False, 'error': f'Pexels returned {r.status_code}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:80]})


@app.route('/api/generate', methods=['POST'])
def generate():
    """
    Synchronous single endpoint: takes script, API keys, audio duration.
    Returns ZIP file with media + guide + metadata.
    Includes stats as HTTP response headers.
    """
    data = request.json or {}

    title = data.get('title', 'My Video').strip()
    script = data.get('script', '').strip()
    claude_key = data.get('claude_key', '').strip()
    pexels_key = data.get('pexels_key', '').strip()
    audio_duration = data.get('audio_duration')

    # Validation
    if not script:
        return jsonify({'error': 'Please provide a script.'}), 400
    if not claude_key:
        return jsonify({'error': 'Please enter your Claude API key.'}), 400
    if not pexels_key:
        return jsonify({'error': 'Please enter your Pexels API key.'}), 400

    if audio_duration is not None:
        try:
            audio_duration = float(audio_duration)
        except (TypeError, ValueError):
            audio_duration = None

    # Generate
    try:
        zip_bytes, metadata = generate_brolls(title, script, claude_key, pexels_key, audio_duration)
    except Exception as e:
        error_msg = str(e)
        if 'Invalid Claude' in error_msg:
            return jsonify({'error': error_msg}), 401
        elif 'Invalid Pexels' in error_msg:
            return jsonify({'error': error_msg}), 401
        else:
            return jsonify({'error': error_msg}), 500

    # Build filename
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'\s+', '_', safe_title)[:60] or 'capcut_brolls'
    download_name = f"{safe_title}_brolls.zip"

    # Return ZIP with stats in headers
    resp = send_file(
        io.BytesIO(zip_bytes),
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_name
    )
    resp.headers['X-Cost-USD'] = str(metadata['cost_usd'])
    resp.headers['X-Scenes'] = str(metadata['scenes_done'])
    resp.headers['X-Videos'] = str(metadata['video_count'])
    resp.headers['X-Images'] = str(metadata['image_count'])
    resp.headers['X-Duration'] = str(metadata['total_duration'])

    return resp


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
