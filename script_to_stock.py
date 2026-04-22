#!/usr/bin/env python3
"""
ScriptToStock - AI-powered stock image finder for CapCut video creators

SETUP:
  pip install flask anthropic requests pydub

RUN:
  python script_to_stock.py

OPEN IN BROWSER:
  http://localhost:5000
"""

import json
import io
import zipfile
import re
import threading
import uuid
import os
import tempfile
import time

from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

# In-memory job store
jobs = {}
job_lock = threading.Lock()


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
            <textarea id="script" rows="10" placeholder="Paste your full video script here...

Example:
Did you know that 90% of information transmitted to the brain is visual? That's why great stock footage can make or break your video. In this video, I'm going to show you five powerful techniques to boost your productivity starting today. First up: time blocking. By dividing your day into focused chunks, you eliminate decision fatigue and get into a flow state faster..."
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
        <p class="text-sm text-slate-500">Fill in your script and click Generate.<br/>Your scenes will appear here as they're processed.</p>
      </div>

      <!-- Progress card -->
      <div id="progressCard" class="hidden bg-slate-900 rounded-2xl border border-slate-800 p-5">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="pulse-dot inline-block w-2 h-2 rounded-full bg-blue-500"></span>
            <span class="font-semibold text-sm" id="progressTitle">Processing...</span>
          </div>
          <span id="progressBadge" class="text-xs bg-blue-900/50 text-blue-300 border border-blue-700 px-2 py-1 rounded-full font-mono">0%</span>
        </div>
        <div class="bg-slate-800 rounded-full h-1.5 mb-3 overflow-hidden">
          <div id="progressBar" class="bg-blue-500 h-1.5 rounded-full transition-all duration-500" style="width:0%"></div>
        </div>
        <p id="progressMessage" class="text-xs text-slate-400">Starting up...</p>

        <!-- Stage indicators -->
        <div class="flex items-center gap-2 mt-4">
          <div id="stage-parse" class="flex items-center gap-1 text-xs px-2 py-1 rounded-full border border-slate-700 text-slate-500">
            <span>🧠</span><span>Parsing</span>
          </div>
          <div class="text-slate-700">→</div>
          <div id="stage-search" class="flex items-center gap-1 text-xs px-2 py-1 rounded-full border border-slate-700 text-slate-500">
            <span>🔍</span><span>Searching</span>
          </div>
          <div class="text-slate-700">→</div>
          <div id="stage-pack" class="flex items-center gap-1 text-xs px-2 py-1 rounded-full border border-slate-700 text-slate-500">
            <span>📦</span><span>Packaging</span>
          </div>
        </div>
      </div>

      <!-- Cost widget -->
      <div id="costWidget" class="hidden bg-slate-900 rounded-2xl border border-slate-800 p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-sm text-slate-300">
            <span>💰</span>
            <span class="font-semibold">API Cost (Claude Haiku)</span>
          </div>
          <span id="costAmount" class="font-mono font-bold text-emerald-400 text-sm">$0.00000</span>
        </div>
        <div class="flex items-center gap-4 mt-2 text-xs text-slate-500">
          <span>Input: <span id="inputTokens" class="text-slate-400">—</span> tokens</span>
          <span>Output: <span id="outputTokens" class="text-slate-400">—</span> tokens</span>
          <span class="ml-auto text-slate-600">~$0.80/$4.00 per MTok</span>
        </div>
      </div>

      <!-- Download card -->
      <div id="downloadCard" class="hidden bg-emerald-950/40 rounded-2xl border border-emerald-700/50 p-5">
        <div class="flex items-center gap-4">
          <div class="text-4xl">✅</div>
          <div class="flex-1">
            <h2 class="font-bold text-emerald-300">CapCut Package Ready!</h2>
            <p id="downloadSubtext" class="text-sm text-slate-400 mt-0.5"></p>
          </div>
          <button id="downloadBtn"
            class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-5 py-2.5 rounded-xl text-sm transition-colors whitespace-nowrap">
            Download ZIP 📦
          </button>
        </div>
        <div class="mt-4 bg-slate-900/50 rounded-xl p-3 text-xs text-slate-400 space-y-1">
          <p class="font-semibold text-slate-300">How to import into CapCut:</p>
          <p>1. Unzip the file — filenames already have timestamps so they sort in order</p>
          <p>2. In CapCut tap <strong>+</strong> → Import all <strong>.jpg</strong> and <strong>.mp4</strong> files</p>
          <p>3. Images: set clip duration from filename (e.g. <code class="bg-slate-800 px-1 rounded">00m15s_doctors-hospital_4.5s.jpg</code> = 4.5s)</p>
          <p>4. Videos: trim each clip to the duration in its filename</p>
          <p>5. Add your voiceover → export!</p>
        </div>
      </div>

      <!-- Error card -->
      <div id="errorCard" class="hidden bg-red-950/40 rounded-2xl border border-red-700/50 p-5">
        <div class="flex items-start gap-3">
          <div class="text-2xl">❌</div>
          <div>
            <h2 class="font-semibold text-red-300">Something went wrong</h2>
            <p id="errorMessage" class="text-sm text-slate-400 mt-1"></p>
            <button onclick="resetUI()" class="mt-3 text-xs text-blue-400 hover:underline">Try again</button>
          </div>
        </div>
      </div>

      <!-- Scene cards container -->
      <div id="scenesContainer" class="space-y-3"></div>

    </div>
  </main>

  <script>
    let currentJobId = null;
    let pollInterval = null;
    let audioDuration = null;

    // ── API key testers ──
    function setKeyStatus(id, state, msg) {
      const el = document.getElementById(id);
      const styles = {
        ok:      'border-emerald-600 text-emerald-400 bg-emerald-900/30',
        error:   'border-red-600 text-red-400 bg-red-900/30',
        testing: 'border-blue-700 text-blue-400 bg-blue-900/20',
        none:    'border-slate-700 text-slate-500',
      };
      el.className = `text-xs px-2 py-0.5 rounded-full border transition-all ${styles[state] || styles.none}`;
      el.textContent = msg;
    }

    async function testClaudeKey() {
      const key = document.getElementById('claudeKey').value.trim();
      if (!key) { setKeyStatus('claudeStatus', 'error', 'Enter a key first'); return; }
      setKeyStatus('claudeStatus', 'testing', 'Testing...');
      try {
        const r = await fetch('/api/test-claude', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({claude_key: key})
        });
        const d = await r.json();
        if (d.ok) {
          setKeyStatus('claudeStatus', 'ok', '✓ Connected');
          localStorage.setItem('sts_claude', key);
        } else {
          setKeyStatus('claudeStatus', 'error', '✗ ' + (d.error || 'Invalid key'));
        }
      } catch(e) {
        setKeyStatus('claudeStatus', 'error', '✗ Network error');
      }
    }

    async function testPexelsKey() {
      const key = document.getElementById('pexelsKey').value.trim();
      if (!key) { setKeyStatus('pexelsStatus', 'error', 'Enter a key first'); return; }
      setKeyStatus('pexelsStatus', 'testing', 'Testing...');
      try {
        const r = await fetch('/api/test-pexels', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({pexels_key: key})
        });
        const d = await r.json();
        if (d.ok) {
          setKeyStatus('pexelsStatus', 'ok', '✓ Connected');
          localStorage.setItem('sts_pexels', key);
        } else {
          setKeyStatus('pexelsStatus', 'error', '✗ ' + (d.error || 'Invalid key'));
        }
      } catch(e) {
        setKeyStatus('pexelsStatus', 'error', '✗ Network error');
      }
    }

    // ── Init ──
    window.onload = function() {
      document.getElementById('claudeKey').value = localStorage.getItem('sts_claude') || '';
      document.getElementById('pexelsKey').value = localStorage.getItem('sts_pexels') || '';

      document.getElementById('script').addEventListener('input', updateWordCount);
      document.getElementById('audioFile').addEventListener('change', handleAudioFile);
    };

    function updateWordCount() {
      const text = document.getElementById('script').value.trim();
      const words = text ? text.split(/\s+/).length : 0;
      document.getElementById('wordCount').textContent = words + ' words';
      if (!audioDuration && words > 0) {
        const estSecs = (words / 130) * 60;
        document.getElementById('estimatedDuration').textContent =
          'Est. ' + estSecs.toFixed(0) + 's without audio';
      }
    }

    function handleAudioFile(e) {
      const file = e.target.files[0];
      if (!file) { audioDuration = null; return; }

      const audio = new Audio();
      audio.onloadedmetadata = function() {
        audioDuration = audio.duration;
        const mins = Math.floor(audioDuration / 60);
        const secs = (audioDuration % 60).toFixed(1);
        const info = document.getElementById('audioInfo');
        info.textContent = `✅ Audio detected: ${mins > 0 ? mins + 'm ' : ''}${secs}s — timing will be synced precisely`;
        info.classList.remove('hidden');
        document.getElementById('estimatedDuration').textContent = '';
      };
      audio.onerror = function() {
        document.getElementById('audioInfo').textContent = '⚠️ Could not read audio duration. Timing will be estimated.';
        document.getElementById('audioInfo').classList.remove('hidden');
        audioDuration = null;
      };
      audio.src = URL.createObjectURL(file);
    }

    // ── Main generation ──
    async function startGeneration() {
      const script    = document.getElementById('script').value.trim();
      const claudeKey = document.getElementById('claudeKey').value.trim();
      const pexelsKey = document.getElementById('pexelsKey').value.trim();
      const title     = document.getElementById('title').value.trim() || 'My Video';

      if (!script)    { showAlert('Please paste your video script.'); return; }
      if (!claudeKey) { showAlert('Please enter your Claude API key.'); return; }
      if (!pexelsKey) { showAlert('Please enter your Pexels API key.'); return; }

      // Save keys
      localStorage.setItem('sts_claude', claudeKey);
      localStorage.setItem('sts_pexels', pexelsKey);

      // Prepare UI
      document.getElementById('emptyState').classList.add('hidden');
      document.getElementById('progressCard').classList.remove('hidden');
      document.getElementById('downloadCard').classList.add('hidden');
      document.getElementById('errorCard').classList.add('hidden');
      document.getElementById('scenesContainer').innerHTML = '';
      setStage('parse');

      const btn = document.getElementById('generateBtn');
      btn.disabled = true;
      btn.innerHTML = '<span class="pulse-dot inline-block w-2 h-2 rounded-full bg-white mr-2"></span> Processing...';

      try {
        const payload = {
          title,
          script,
          claude_key: claudeKey,
          pexels_key: pexelsKey,
          audio_duration: audioDuration  // null if no audio uploaded
        };

        const resp = await fetch('/api/start', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (data.error) { showError(data.error); resetBtn(); return; }

        currentJobId = data.job_id;
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollStatus, 1500);

      } catch(err) {
        showError('Network error: ' + err.message);
        resetBtn();
      }
    }

    async function pollStatus() {
      if (!currentJobId) return;
      try {
        const resp = await fetch('/api/status/' + currentJobId);
        const data = await resp.json();
        updateUI(data);
        if (data.status === 'complete' || data.status === 'error') {
          clearInterval(pollInterval); pollInterval = null;
        }
      } catch(e) { console.warn('poll error', e); }
    }

    function updateUI(data) {
      // Progress bar
      const progress = calcProgress(data);
      document.getElementById('progressBar').style.width = progress + '%';
      document.getElementById('progressBadge').textContent = progress + '%';
      document.getElementById('progressMessage').textContent = data.message || '';

      // Stage highlights
      if (data.status === 'parsing') setStage('parse');
      else if (data.status === 'searching') setStage('search');
      else if (data.status === 'packaging') setStage('pack');

      // Add new scene cards
      const container = document.getElementById('scenesContainer');
      const existing = container.children.length;
      if (data.scenes && data.scenes.length > existing) {
        for (let i = existing; i < data.scenes.length; i++) {
          const card = makeSceneCard(data.scenes[i]);
          container.appendChild(card);
        }
      }

      // Update cost widget whenever we have token data
      if (data.cost_usd !== undefined) {
        document.getElementById('costWidget').classList.remove('hidden');
        document.getElementById('costAmount').textContent = '$' + data.cost_usd.toFixed(5);
        document.getElementById('inputTokens').textContent = (data.input_tokens || 0).toLocaleString();
        document.getElementById('outputTokens').textContent = (data.output_tokens || 0).toLocaleString();
      }

      if (data.status === 'complete') {
        document.getElementById('progressCard').classList.add('hidden');
        document.getElementById('downloadCard').classList.remove('hidden');
        const scenes  = data.scenes || [];
        const videos  = scenes.filter(s => s.success && s.media_type === 'video').length;
        const images  = scenes.filter(s => s.success && s.media_type === 'image').length;
        const dur     = data.total_duration || 0;
        document.getElementById('downloadSubtext').textContent =
          `${videos} videos · ${images} images · ${dur.toFixed(1)}s · Synced to timeline`;
        document.getElementById('downloadBtn').onclick = () => {
          window.location.href = '/api/download/' + currentJobId;
        };
        resetBtn();
      }

      if (data.status === 'error') {
        document.getElementById('progressCard').classList.add('hidden');
        showError(data.message);
        resetBtn();
      }
    }

    function calcProgress(data) {
      if (data.status === 'complete') return 100;
      if (data.status === 'parsing') return 10;
      if (data.status === 'packaging') return 95;
      if (data.status === 'searching' && data.total_scenes) {
        return Math.min(15 + Math.round((data.scenes_done / data.total_scenes) * 75), 94);
      }
      return 5;
    }

    function makeSceneCard(s) {
      const div = document.createElement('div');
      div.className = 'slide-in bg-slate-900 rounded-xl border border-slate-800 p-4';
      const isVideo   = s.media_type === 'video';
      const icon      = s.success ? (isVideo ? '🎬' : '🖼️') : '⚠️';
      const typeBadge = s.success
        ? (isVideo
            ? `<span class="text-xs bg-purple-900/50 text-purple-300 border border-purple-800 px-1.5 py-0.5 rounded-full">VIDEO</span>`
            : `<span class="text-xs bg-slate-700/80 text-slate-300 border border-slate-600 px-1.5 py-0.5 rounded-full">IMAGE</span>`)
        : '';
      const tsBadge  = `<span class="text-xs bg-amber-900/40 text-amber-300 border border-amber-800 px-1.5 py-0.5 rounded-full font-mono">${formatTime(s.timeline_start || 0)}</span>`;
      const durBadge = `<span class="text-xs bg-blue-900/50 text-blue-300 border border-blue-800 px-1.5 py-0.5 rounded-full">${s.duration.toFixed(1)}s</span>`;
      const credit   = s.success
        ? `${isVideo ? '🎥' : '📷'} ${s.photographer}`
        : '⚠️ No media found';
      const phraseHtml = s.phrase
        ? `<p class="text-xs text-slate-500 mt-1 italic border-l-2 border-slate-700 pl-2">"${s.phrase}"</p>`
        : '';
      const rationaleHtml = s.rationale
        ? `<p class="text-xs text-emerald-600 mt-1">💡 ${s.rationale}</p>`
        : '';
      div.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="text-xl mt-0.5">${icon}</div>
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-1.5 mb-1.5">${tsBadge}${typeBadge}${durBadge}</div>
            <p class="text-sm text-slate-200 leading-snug font-medium">${s.description}</p>
            ${phraseHtml}
            ${rationaleHtml}
            <p class="text-xs text-slate-500 mt-1.5">Search: <em>"${s.query}"</em> · ${credit}</p>
            <p class="text-xs text-slate-700 mt-0.5 font-mono truncate">${s.filename}</p>
          </div>
        </div>`;
      return div;
    }

    function formatTime(secs) {
      const m = Math.floor(secs / 60).toString().padStart(2, '0');
      const s = Math.floor(secs % 60).toString().padStart(2, '0');
      return m + ':' + s;
    }

    function setStage(active) {
      const stages = ['parse', 'search', 'pack'];
      stages.forEach(s => {
        const el = document.getElementById('stage-' + s);
        if (!el) return;
        if (s === active) {
          el.className = 'flex items-center gap-1 text-xs px-2 py-1 rounded-full border border-blue-500 text-blue-300 bg-blue-900/30';
        } else {
          el.className = 'flex items-center gap-1 text-xs px-2 py-1 rounded-full border border-slate-700 text-slate-500';
        }
      });
    }

    function showError(msg) {
      document.getElementById('errorCard').classList.remove('hidden');
      document.getElementById('errorMessage').textContent = msg;
    }

    function showAlert(msg) {
      // Simple inline alert without browser dialog
      const el = document.createElement('div');
      el.className = 'fixed top-4 right-4 bg-amber-900/90 border border-amber-600 text-amber-200 text-sm px-4 py-3 rounded-xl z-50 slide-in';
      el.textContent = '⚠️ ' + msg;
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 4000);
    }

    function resetBtn() {
      const btn = document.getElementById('generateBtn');
      btn.disabled = false;
      btn.innerHTML = '<span>✨</span> Generate CapCut Images';
    }

    function resetUI() {
      document.getElementById('errorCard').classList.add('hidden');
      document.getElementById('emptyState').classList.remove('hidden');
    }
  </script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# JOB HELPERS
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# FILENAME + MEDIA HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_slug(text, max_len=40):
    """Turn a description into a clean hyphenated filename slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)       # strip punctuation
    text = re.sub(r'\s+', '-', text)               # spaces → hyphens
    text = text[:max_len].rstrip('-')
    return text or 'scene'


def make_filename(cumulative_s, description, pexels_label, duration, ext):
    """
    Build a descriptive timestamped filename.
    e.g. 00m15s_seniors-taking-statins_4.5s.jpg
    Uses pexels_label (alt text / title) when available, otherwise description.
    """
    mins = int(cumulative_s // 60)
    secs = int(cumulative_s % 60)
    ts   = f"{mins:02d}m{secs:02d}s"
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
            alt_title    = video.get('url', '').rstrip('/').split('/')[-1].replace('-', ' ')

            # Pick best MP4 ≤ 720p (keeps file size sane)
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
            alt     = photo.get('alt', '') or ''
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
    ratio 0.0–1.0 (start → end of script).  Tries progressively shorter
    substrings for robustness when Claude paraphrases slightly.
    Returns None if not found.
    """
    if not phrase or not script:
        return None
    script_lower = script.lower()
    phrase_words  = phrase.lower().split()
    total_chars   = len(script_lower)

    # Try matching 6, 5, 4, 3 consecutive words from the phrase
    for n in range(min(6, len(phrase_words)), 2, -1):
        snippet = ' '.join(phrase_words[:n])
        idx = script_lower.find(snippet)
        if idx != -1:
            return idx / total_chars   # character-based ratio (accurate enough)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# COST CONSTANTS  (Haiku 4.5 — check console.anthropic.com for latest)
# ─────────────────────────────────────────────────────────────────────────────
COST_INPUT_PER_MTOK  = 0.80   # USD per 1M input tokens
COST_OUTPUT_PER_MTOK = 4.00   # USD per 1M output tokens


def update_job(job_id, **kwargs):
    with job_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# CORE PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def process_job(job_id, title, script, claude_key, pexels_key, audio_duration):
    """Runs in background thread: parse → search → download → zip."""
    try:

        # ── Step 1: Parse script with Claude ──────────────────────────────────
        update_job(job_id, status='parsing', message='🧠 Analyzing script with Claude AI...')

        import anthropic
        client = anthropic.Anthropic(api_key=claude_key)

        word_count    = len(script.split())
        # Total video seconds (use audio if available, else estimate at 130wpm)
        total_secs    = audio_duration if audio_duration else (word_count / 130) * 60
        # Target 2 B-rolls per 60 seconds → 1 every ~30 s. Cap 5–80.
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

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$',           '', raw, flags=re.MULTILINE)
        raw = raw.strip()

        brolls = None

        # Attempt 1: parse whole response
        try:
            brolls = json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Attempt 2: greedy outer-bracket extract
        if brolls is None:
            m = re.search(r'\[[\s\S]*\]', raw)
            if m:
                try:
                    brolls = json.loads(m.group())
                except json.JSONDecodeError:
                    pass

        # Attempt 3: salvage complete objects even if array is truncated
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
            update_job(job_id, status='error',
                       message=f'Could not parse Claude response. Preview: "{preview}"')
            return

        # ── Cost tracking ──────────────────────────────────────────────────────
        input_tokens  = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost_usd      = (
            (input_tokens  / 1_000_000) * COST_INPUT_PER_MTOK +
            (output_tokens / 1_000_000) * COST_OUTPUT_PER_MTOK
        )

        # ── Calculate timeline_start for each B-roll via phrase position ───────
        # Phrases anchor each B-roll to the exact word in the script.
        for broll in brolls:
            phrase = str(broll.get('phrase', ''))
            ratio  = find_phrase_ratio(script, phrase)
            if ratio is None:
                # Fallback: distribute evenly based on cue order
                ratio = (broll.get('cue', 1) - 1) / max(len(brolls), 1)
            broll['timeline_start'] = round(ratio * total_secs, 2)

        # Sort by timeline position (Claude should output in order, but ensure it)
        brolls.sort(key=lambda b: b['timeline_start'])

        update_job(job_id,
                   status='searching',
                   message=f'🎬 Identified {len(brolls)} B-roll cues. Searching Pexels...',
                   total_scenes=len(brolls),
                   scenes_done=0,
                   scenes=[],
                   cost_usd=round(cost_usd, 5),
                   input_tokens=input_tokens,
                   output_tokens=output_tokens)

        # ── Step 2: Search Pexels (video-first, then photo) ───────────────────
        import requests as req

        scene_results = []

        for i, broll in enumerate(brolls):
            scene_num   = i + 1
            query       = str(broll.get('query',       'nature landscape')).strip()
            duration    = max(2.0, min(8.0, float(broll.get('duration', 4.0))))
            description = str(broll.get('description', f'B-roll {scene_num}')).strip()
            phrase      = str(broll.get('phrase',      '')).strip()
            rationale   = str(broll.get('rationale',   '')).strip()
            timeline_start = float(broll.get('timeline_start', 0.0))

            update_job(job_id,
                       message=f'🎬 Searching: "{query}" ({scene_num}/{len(brolls)})',
                       scenes_done=i)

            media_data   = None
            photographer = 'Pexels'
            pexels_label = ''
            media_type   = 'image'    # 'image' or 'video'
            ext          = '.jpg'

            # ── Try video first ───────────────────────────────────────────────
            vdata, vphoto, vtitle = fetch_pexels_video(query, pexels_key, req)
            if vdata:
                media_data   = vdata
                photographer = vphoto or 'Pexels'
                pexels_label = vtitle or description
                media_type   = 'video'
                ext          = '.mp4'
            else:
                # ── Fall back to photo ────────────────────────────────────────
                pdata, pphoto, palt = fetch_pexels_photo(query, pexels_key, req)
                if pdata == 'AUTH_ERROR':
                    update_job(job_id, status='error',
                               message='Invalid Pexels API key. Check your key and try again.')
                    return
                if pdata:
                    media_data   = pdata
                    photographer = pphoto or 'Pexels'
                    pexels_label = palt or description
                    media_type   = 'image'
                    ext          = '.jpg'

            # Filename uses timeline_start (accurate) and description-based slug
            filename = make_filename(timeline_start, description, pexels_label, duration, ext)

            result = {
                'scene':          scene_num,
                'phrase':         phrase,
                'description':    description,
                'rationale':      rationale,
                'query':          query,
                'duration':       round(duration, 2),
                'filename':       filename,
                'media_type':     media_type,
                'photographer':   photographer,
                'pexels_label':   pexels_label,
                'timeline_start': round(timeline_start, 2),
                'success':        media_data is not None,
                '_data':          media_data,
            }
            scene_results.append(result)

            # Push to frontend (no raw bytes)
            frontend = {k: v for k, v in result.items() if not k.startswith('_')}
            with job_lock:
                jobs[job_id]['scenes'].append(frontend)
                jobs[job_id]['scenes_done'] = scene_num

        # ── Step 3: Build ZIP ─────────────────────────────────────────────────
        update_job(job_id, status='packaging', message='📦 Building your CapCut ZIP package...')

        total_duration = round(total_secs, 2)   # = the audio duration (or estimate)
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

            # Media files
            for r in scene_results:
                if r['_data']:
                    zf.writestr(r['filename'], r['_data'])

            # Human-readable import guide
            guide = build_guide(title, scene_results, total_duration, audio_duration)
            zf.writestr('CAPCUT_IMPORT_GUIDE.txt', guide)

            # Machine-readable scene data
            clean = [{k: v for k, v in r.items() if not k.startswith('_')} for r in scene_results]
            zf.writestr('scenes_data.json', json.dumps(clean, indent=2))

        # Save to temp file
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip', prefix=f'sts_{job_id}_')
        os.close(tmp_fd)
        with open(tmp_path, 'wb') as f:
            f.write(zip_buffer.getvalue())

        success_count = sum(1 for r in scene_results if r['success'])
        video_count   = sum(1 for r in scene_results if r['success'] and r['media_type'] == 'video')
        image_count   = success_count - video_count

        update_job(job_id,
                   status='complete',
                   message=f'✅ Done! {video_count} videos + {image_count} images packaged.',
                   zip_path=tmp_path,
                   total_duration=total_duration,
                   scenes_done=len(scene_results),
                   cost_usd=round(cost_usd, 5))

    except anthropic.AuthenticationError:
        update_job(job_id, status='error',
                   message='Invalid Claude API key. Check your key at console.anthropic.com')
    except anthropic.RateLimitError:
        update_job(job_id, status='error',
                   message='Claude rate limit hit. Wait a moment and try again.')
    except Exception as e:
        update_job(job_id, status='error', message=f'Unexpected error: {str(e)}')


def build_guide(title, scenes, total_duration, audio_duration):
    """Build the human-readable CapCut import guide."""
    video_count   = sum(1 for s in scenes if s.get('success') and s.get('media_type') == 'video')
    image_count   = sum(1 for s in scenes if s.get('success') and s.get('media_type') == 'image')
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
        end   = round(start + s['duration'], 2)
        mins  = int(start // 60)
        secs  = start % 60
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


@app.route('/api/start', methods=['POST'])
def start_job():
    data = request.json or {}

    title         = data.get('title', 'My Video').strip()
    script        = data.get('script', '').strip()
    claude_key    = data.get('claude_key', '').strip()
    pexels_key    = data.get('pexels_key', '').strip()
    audio_duration = data.get('audio_duration')  # float or None

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

    job_id = uuid.uuid4().hex[:10]

    with job_lock:
        jobs[job_id] = {
            'status':         'starting',
            'message':        'Initializing...',
            'scenes':         [],
            'total_scenes':   0,
            'scenes_done':    0,
            'zip_path':       None,
            'total_duration': 0,
            'title':          title,
        }

    t = threading.Thread(
        target=process_job,
        args=(job_id, title, script, claude_key, pexels_key, audio_duration),
        daemon=True
    )
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>')
def job_status(job_id):
    with job_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    # Strip internal field
    return jsonify({k: v for k, v in job.items() if k != 'zip_path'})


@app.route('/api/download/<job_id>')
def download_zip(job_id):
    with job_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if job.get('status') != 'complete':
        return jsonify({'error': 'Job is not complete yet.'}), 400

    zip_path = job.get('zip_path')
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': 'ZIP file missing. Please regenerate.'}), 404

    # Build filename from video title — strip chars not safe in filenames
    raw_title = job.get('title', 'capcut_brolls')
    safe_title = re.sub(r'[^\w\s-]', '', raw_title).strip()
    safe_title = re.sub(r'\s+', '_', safe_title)[:60] or 'capcut_brolls'
    download_name = f"{safe_title}_brolls.zip"

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_name
    )


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
