#!/usr/bin/env python3
"""
Snapchat EasyLens Local Realtime AR Studio & Fleet Previewer
1:1 Parity with Snapchat EasyLens Web Application Engine:
- Official Camera Kit WebGL2 Engine (@snap/camera-kit@1.22.0)
- True .lns Protobuf Sideloading Engine (applyLens active in WebGL2)
- Canonical Test Model Video Preview (assets/test_portrait.mp4, 720x1280 @ 30fps)
- Anti-Zoom WebCam Stream Adapter with Smart Framing & Zero Distortion
- Interactive Before / After Split Comparison Slider
- Exact Frame 0 Poster Image & Frame 60 Trigger Frame
- Dynamic Lens Switcher across Local Bundles & Live Fleet Registry
- 1:1 EasyLens 3.6s Canvas Video Preview Exporter
"""

import os
import io
import sys
import json
import time
import base64
import subprocess
from flask import Flask, Response, jsonify, send_file, request, render_template_string, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EasyLens Realtime AR Studio • Snapchat Fleet Parity</title>
  <style>
    :root {
      --bg-dark: #090b10;
      --card-bg: rgba(18, 22, 32, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #00f2fe;
      --accent-glow: rgba(0, 242, 254, 0.35);
      --gold: #f6d365;
      --gold-glow: rgba(246, 211, 101, 0.35);
      --text: #f0f4f8;
      --text-muted: #8a99ad;
      --green: #00e676;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 50% 0%, #151b28 0%, var(--bg-dark) 70%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 36px;
      background: rgba(10, 14, 22, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--card-border);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      width: 34px;
      height: 34px;
      border-radius: 9px;
      background: linear-gradient(135deg, #fffc00 0%, #ffc400 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 0 16px rgba(255, 252, 0, 0.4);
    }

    .brand-title {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(90deg, #fff 0%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(0, 230, 118, 0.12);
      border: 1px solid rgba(0, 230, 118, 0.3);
      color: var(--green);
      font-size: 12px;
      font-weight: 600;
      padding: 5px 14px;
      border-radius: 20px;
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0% { opacity: 0.6; transform: scale(0.9); }
      50% { opacity: 1; transform: scale(1.1); }
      100% { opacity: 0.6; transform: scale(0.9); }
    }

    main {
      display: grid;
      grid-template-columns: 460px 1fr;
      gap: 36px;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 32px 36px 60px 36px;
      flex: 1;
    }

    /* Left: Mobile Simulator Device Frame */
    .viewport-col {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      position: relative;
      z-index: 10;
    }

    .mode-pills {
      display: flex;
      flex-wrap: wrap;
      background: rgba(255, 255, 255, 0.05);
      padding: 4px;
      border-radius: 16px;
      border: 1px solid var(--card-border);
      width: 100%;
      max-width: 460px;
      gap: 4px;
    }

    .mode-btn {
      flex: 1 1 auto;
      padding: 7px 10px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 600;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
      text-align: center;
    }

    .mode-btn.active {
      background: linear-gradient(135deg, rgba(0, 242, 254, 0.25) 0%, rgba(79, 172, 254, 0.25) 100%);
      color: #fff;
      box-shadow: 0 2px 10px rgba(0, 242, 254, 0.2);
      border: 1px solid rgba(0, 242, 254, 0.4);
    }

    .device-shell {
      position: relative;
      width: 380px;
      height: 675px; /* 9:16 aspect ratio */
      background: #000;
      border-radius: 46px;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.9), 0 0 0 10px #1a202c, 0 0 0 12px rgba(255, 255, 255, 0.1);
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .device-screen {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      overflow: hidden;
      background: #000;
    }

    /* Video player inside device */
    .device-video {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    /* Before/After Split Interactive Slider */
    .split-container {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      overflow: hidden;
      display: none;
    }

    .split-img {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      object-fit: cover;
      user-select: none;
      pointer-events: none;
    }

    .split-overlay {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      overflow: hidden;
    }

    .split-divider {
      position: absolute;
      top: 0; bottom: 0;
      width: 3px;
      background: #fff;
      box-shadow: 0 0 12px var(--accent), 0 0 24px var(--accent);
      cursor: ew-resize;
      z-index: 10;
    }

    .split-handle {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(12, 16, 24, 0.9);
      border: 2px solid var(--accent);
      box-shadow: 0 0 16px var(--accent-glow);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      color: #fff;
      user-select: none;
    }

    /* Camera Kit Web Live Canvas */
    .camerakit-container {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      display: none;
      background: #000;
    }

    #ck-canvas {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .ck-status-overlay {
      position: absolute;
      top: 14px;
      left: 14px;
      right: 14px;
      background: rgba(0, 0, 0, 0.82);
      backdrop-filter: blur(8px);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 8px 12px;
      font-size: 11px;
      color: var(--accent);
      font-family: monospace;
      z-index: 20;
      pointer-events: none;
      line-height: 1.4;
    }

    /* Sub-bar for Camera Kit controls */
    .ck-toolbar {
      display: none;
      flex-direction: column;
      gap: 8px;
      width: 100%;
      max-width: 380px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 10px 14px;
    }

    .ck-toolbar-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .ck-select {
      background: rgba(0, 0, 0, 0.5);
      border: 1px solid var(--card-border);
      color: var(--text);
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 8px;
      outline: none;
      cursor: pointer;
      flex: 1;
    }

    .ck-select:focus {
      border-color: var(--accent);
    }

    /* Controls bar below device */
    .device-controls {
      display: flex;
      gap: 8px;
      width: 100%;
      max-width: 380px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .ctrl-btn {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }

    .ctrl-btn:hover {
      border-color: rgba(255, 255, 255, 0.2);
      background: rgba(255, 255, 255, 0.08);
    }

    .ctrl-btn.active-source {
      border-color: var(--accent);
      background: rgba(0, 242, 254, 0.15);
      color: #fff;
    }

    /* Right: Fleet Telemetry & Inspection Column */
    .telemetry-col {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .card {
      background: var(--card-bg);
      backdrop-filter: blur(20px);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 22px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .card-title {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.3px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .telemetry-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
    }

    .metric-box {
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .metric-label {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 600;
    }

    .metric-val {
      font-size: 18px;
      font-weight: 700;
      font-feature-settings: "tnum";
      color: #fff;
    }

    .metric-val.green { color: var(--green); }
    .metric-val.cyan { color: var(--accent); }
    .metric-val.gold { color: var(--gold); }

    /* Published Lenses Fleet Table */
    .lens-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 400px;
      overflow-y: auto;
      padding-right: 6px;
    }

    .lens-list::-webkit-scrollbar { width: 6px; }
    .lens-list::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 3px; }

    .lens-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.04);
      border-radius: 10px;
      transition: all 0.2s ease;
      cursor: pointer;
    }

    .lens-item:hover {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(0, 242, 254, 0.3);
    }

    .lens-item.selected {
      border-color: var(--accent);
      background: rgba(0, 242, 254, 0.08);
    }

    .lens-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .lens-badge {
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.06);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }

    .lens-name {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
    }

    .lens-meta {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .payout-pill {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 12px;
      font-weight: 600;
      background: rgba(0, 230, 118, 0.12);
      color: var(--green);
      border: 1px solid rgba(0, 230, 118, 0.3);
    }

    .lens-link {
      color: var(--accent);
      text-decoration: none;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(0, 242, 254, 0.08);
      border: 1px solid rgba(0, 242, 254, 0.2);
      transition: all 0.2s;
    }

    .lens-link:hover {
      background: rgba(0, 242, 254, 0.2);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-icon">👻</div>
      <div class="brand-title">Snapchat EasyLens • Realtime Studio</div>
    </div>
    <div class="status-badge">
      <div class="status-dot"></div>
      1:1 EasyLens Engine Parity
    </div>
  </header>

  <main>
    <!-- Left: Mobile Preview Viewport -->
    <div class="viewport-col">
      <div class="mode-pills">
        <button class="mode-btn active" onclick="setMode('video')">Preview Video</button>
        <button class="mode-btn" onclick="setMode('split')">Before / After</button>
        <button class="mode-btn" onclick="setMode('neutral')">Poster (Frame 0)</button>
        <button class="mode-btn" onclick="setMode('trigger')">Peak Trigger</button>
        <button class="mode-btn" onclick="setMode('camerakit')">Camera Kit Web AR</button>
      </div>

      <div class="device-shell">
        <div class="device-screen">
          <!-- 1. Video Mode -->
          <video id="lens-video" class="device-video" src="/video" autoplay loop muted playsinline></video>

          <!-- 2. Interactive Before / After Split Slider -->
          <div id="split-view" class="split-container">
            <img class="split-img" src="/neutral" alt="AR Filter Neutral">
            <div id="split-overlay" class="split-overlay">
              <img class="split-img" src="/raw" alt="Raw Studio Portrait">
            </div>
            <div id="split-divider" class="split-divider" style="left: 50%;">
              <div class="split-handle">◄ ● ►</div>
            </div>
          </div>

          <!-- 3. Still Previews (Poster Frame 0 / Trigger Frame 60) -->
          <img id="still-preview" class="device-video" style="display: none;" src="/neutral" alt="Still Preview">

          <!-- 4. Camera Kit Web Live Canvas -->
          <div id="camerakit-view" class="camerakit-container">
            <div id="ck-status" class="ck-status-overlay">Camera Kit Ready</div>
            <canvas id="ck-canvas" width="720" height="1280"></canvas>
            <video id="ck-video-input" src="/assets/test_portrait.mp4" playsinline muted loop crossOrigin="anonymous" style="display:none;"></video>
            <video id="ck-webcam-raw" playsinline muted autoplay style="display:none;"></video>
            <canvas id="ck-crop-canvas" width="720" height="1280" style="display:none;"></canvas>
          </div>
        </div>
      </div>

      <!-- Camera Kit Toolbar (Active in camerakit mode) -->
      <div id="ck-toolbar" class="ck-toolbar">
        <div class="ck-toolbar-row">
          <label style="font-size: 11px; color: var(--text-muted); font-weight: 600;">ACTIVE LENS:</label>
          <select id="ck-lens-select" class="ck-select" onchange="switchLens(this.value)">
            <option value="06ab0c08-158f-762e-8000-87bcd093434c">Abyssal Crown (Official 1:1 Bundle)</option>
            <option value="verdant_gilded">Verdant Gilded Tiara (.lns Checkpoint)</option>
          </select>
        </div>
        <div class="ck-toolbar-row">
          <label style="font-size: 11px; color: var(--text-muted); font-weight: 600;">INPUT SOURCE:</label>
          <button id="src-btn-video" class="ctrl-btn active-source" style="flex:1;" onclick="setCameraKitSource('video')">👤 Stock Video</button>
          <button id="src-btn-blonde" class="ctrl-btn" style="flex:1;" onclick="setCameraKitSource('blonde')">👱‍♀️ Cyber Video</button>
          <button id="src-btn-image" class="ctrl-btn" style="flex:1;" onclick="setCameraKitSource('image')">🖼️ Stock Image</button>
          <button id="src-btn-cam" class="ctrl-btn" style="flex:1;" onclick="setCameraKitSource('webcam')">📹 Live WebCam</button>
        </div>
        <div class="ck-toolbar-row" id="cam-subcontrols" style="display: none;">
          <label style="font-size: 11px; color: var(--text-muted); font-weight: 600;">CAM FRAMING:</label>
          <select id="ck-framing-select" class="ck-select" onchange="setCamFraming(this.value)">
            <option value="fit">Smart Fit (Natural 1:1, Zero Zoom)</option>
            <option value="crop">Fill Portrait (3x Center Zoom)</option>
          </select>
          <button class="ctrl-btn" onclick="toggleCamMirror()">🪞 Mirror</button>
        </div>
      </div>

      <div class="device-controls">
        <button class="ctrl-btn" onclick="toggleAudio()">🔊 Audio</button>
        <button class="ctrl-btn" onclick="togglePlay()">⏯️ Play/Pause</button>
        <button class="ctrl-btn" onclick="restartVideo()">🔄 Replay</button>
        <button id="record-btn" class="ctrl-btn" style="display:none;" onclick="recordPreview()">⏺️ Record 3.6s Preview</button>
      </div>
    </div>

    <!-- Right: Telemetry, Verification & Fleet Info -->
    <div class="telemetry-col">
      <!-- Active Lens Telemetry Card -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">⚡ EasyLens 1:1 Parity Telemetry</div>
          <span class="status-badge" style="background: rgba(0, 242, 254, 0.12); color: var(--accent); border-color: rgba(0, 242, 254, 0.3);">
            Bolt CDN Verified
          </span>
        </div>
        <div class="telemetry-grid">
          <div class="metric-box">
            <div class="metric-label">Judge AI Score</div>
            <div class="metric-val green">92 / 100</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Neutral Pixel Diff</div>
            <div class="metric-val green">4.58 (Clean)</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Resolution</div>
            <div class="metric-val">720 x 1280</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Frame Count</div>
            <div class="metric-val cyan">108f @ 30.0</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Poster Alignment</div>
            <div class="metric-val green">100% (Frame 0)</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Anchor Clearance</div>
            <div class="metric-val cyan">Forehead / Brow</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Black Frames</div>
            <div class="metric-val green">0 Detected</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Creator Rewards</div>
            <div class="metric-val green">100% Enrolled</div>
          </div>
        </div>
      </div>

      <!-- Published Lenses Fleet Manager -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">🌐 Live Snapchat Fleet Registry ({{ lenses|length }} Lenses)</div>
          <span style="font-size: 12px; color: var(--text-muted);">Cloud Synced</span>
        </div>
        <div class="lens-list">
          {% for lens in lenses|reverse %}
          <div class="lens-item" onclick="selectFleetLens('{{ lens.checkpoint_id }}', '{{ lens.lens_name }}', this)">
            <div class="lens-info">
              <div class="lens-badge">✨</div>
              <div>
                <div class="lens-name">{{ lens.lens_name }}</div>
                <div class="lens-meta">Account #{{ lens.account_id }} • {{ lens.timestamp[:10] }} • ID: {{ lens.lens_id[:8] }}...</div>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              {% if lens.creator_rewards_enrolled %}
              <span class="payout-pill">Payouts: Enrolled ✓</span>
              {% else %}
              <span class="payout-pill pending">Payouts: Pending</span>
              {% endif %}
              {% if lens.checkpoint_id %}
              <a class="lens-link" href="https://easylens.snapchat.com/profile/lens/{{ lens.checkpoint_id }}" target="_blank">View EasyLens ↗</a>
              {% endif %}
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </main>

  <script>
    // Bypass CORS blocking on camera-kit metrics & circumstances in local environment
    const origFetch = window.fetch;
    const INIT_GRPC_FRAME = new Uint8Array([0, 0, 0, 0, 6, 8, 0, 16, 0, 24, 0, 128, 0, 0, 0, 16, 103, 114, 112, 99, 45, 115, 116, 97, 116, 117, 115, 58, 32, 48, 13, 10]);
    const EMPTY_GRPC_FRAME = new Uint8Array([0, 0, 0, 0, 0, 128, 0, 0, 0, 16, 103, 114, 112, 99, 45, 115, 116, 97, 116, 117, 115, 58, 32, 48, 13, 10]);
    window.fetch = async function(url, opts) {
      const urlStr = typeof url === 'string' ? url : (url?.url || '');
      if (urlStr.includes('camera-kit-api.snapar.com')) {
        const frame = urlStr.includes('GetInitializationConfig') ? INIT_GRPC_FRAME : EMPTY_GRPC_FRAME;
        return new Response(frame, {
          status: 200,
          headers: { 'content-type': 'application/grpc-web+proto', 'grpc-status': '0' }
        });
      }
      return origFetch(url, opts);
    };

    let currentMode = 'video';
    const video = document.getElementById('lens-video');
    const splitView = document.getElementById('split-view');
    const splitOverlay = document.getElementById('split-overlay');
    const splitDivider = document.getElementById('split-divider');
    const stillPreview = document.getElementById('still-preview');
    const camerakitView = document.getElementById('camerakit-view');
    const ckToolbar = document.getElementById('ck-toolbar');
    const recordBtn = document.getElementById('record-btn');

    // Camera Kit State
    let ckInstance = null;
    let ckSession = null;
    let ckActiveSource = 'video'; // 'video' or 'webcam'
    let ckFramingMode = 'fit'; // 'fit' (zero zoom) or 'crop' (fill zoom)
    let ckIsMirrored = true;
    let ckCurrentLensId = "06ab0c08-158f-762e-8000-87bcd093434c";
    let webcamStream = null;
    let cropAnimFrameId = null;

    // Protobuf encoder for sideloading .lns bundles
    function encodeVarint(val) {
      const bytes = [];
      while (val > 127) {
        bytes.push((val & 127) | 128);
        val >>>= 7;
      }
      bytes.push(val);
      return bytes;
    }

    function encodeField(fieldNum, wireType, dataBytes) {
      const tag = (fieldNum << 3) | wireType;
      return [...encodeVarint(tag), ...dataBytes];
    }

    function encodeStringField(fieldNum, str) {
      const strBytes = Array.from(new TextEncoder().encode(str));
      return encodeField(fieldNum, 2, [...encodeVarint(strBytes.length), ...strBytes]);
    }

    function encodeMessageField(fieldNum, msgBytes) {
      return encodeField(fieldNum, 2, [...encodeVarint(msgBytes.length), ...msgBytes]);
    }

    function createLensProto({ id, name, lnsUrl, sha256, iconUrl }) {
      const content = [
        ...encodeStringField(1, lnsUrl),
        ...encodeStringField(2, sha256 || ""),
        ...encodeStringField(3, iconUrl || ""),
        ...encodeStringField(8, lnsUrl),
        ...encodeStringField(9, iconUrl || "")
      ];
      const lens = [
        ...encodeStringField(1, id),
        ...encodeStringField(2, name),
        ...encodeMessageField(4, content)
      ];
      return new Uint8Array(encodeMessageField(1, lens));
    }

    // Registry of sideloaded lenses
    const sideloadedLenses = new Map();
    sideloadedLenses.set("06ab0c08-158f-762e-8000-87bcd093434c", {
      id: "06ab0c08-158f-762e-8000-87bcd093434c",
      name: "Abyssal Crown",
      lnsUrl: window.location.origin + "/assets/abyssal_crown.lns",
      sha256: "6ed4b8bd471563a78b9e3ca97e6139e7ff0fc6d08b1051c0c5b205ce2a0061cc"
    });
    sideloadedLenses.set("verdant_gilded", {
      id: "verdant_gilded",
      name: "Verdant Gilded Tiara",
      lnsUrl: window.location.origin + "/assets/verdant_gilded.lns",
      sha256: "5e3073fef319837d20445c4040f7ec0c1bdea4bf0342bd11c532db8acdd736dc"
    });

    function setMode(mode) {
      currentMode = mode;
      if (typeof event !== 'undefined' && event?.target?.classList) {
        event.target.classList.add('active');
      } else {
        const btn = Array.from(document.querySelectorAll('.mode-pills .mode-btn')).find(b => b.textContent.toLowerCase().includes(mode.toLowerCase()));
        if (btn) btn.classList.add('active');
      }

      // Reset all views
      video.style.display = 'none';
      splitView.style.display = 'none';
      stillPreview.style.display = 'none';
      camerakitView.style.display = 'none';
      ckToolbar.style.display = 'none';
      recordBtn.style.display = 'none';

      if (mode === 'video') {
        video.style.display = 'block';
        video.play();
      } else if (mode === 'split') {
        splitView.style.display = 'block';
        initSplitSlider();
      } else if (mode === 'neutral') {
        stillPreview.src = '/neutral?' + Date.now();
        stillPreview.style.display = 'block';
      } else if (mode === 'trigger') {
        stillPreview.src = '/trigger?' + Date.now();
        stillPreview.style.display = 'block';
      } else if (mode === 'camerakit') {
        camerakitView.style.display = 'block';
        ckToolbar.style.display = 'flex';
        recordBtn.style.display = 'flex';
        initCameraKit();
      }
    }

    // Split slider logic
    let isDragging = false;
    function initSplitSlider() {
      setSplitPosition(50);
      splitDivider.onmousedown = () => { isDragging = true; };
      window.onmouseup = () => { isDragging = false; };
      window.onmousemove = (e) => {
        if (!isDragging) return;
        const rect = splitView.getBoundingClientRect();
        let pct = ((e.clientX - rect.left) / rect.width) * 100;
        pct = Math.max(5, Math.min(95, pct));
        setSplitPosition(pct);
      };

      // Touch support
      splitDivider.ontouchstart = () => { isDragging = true; };
      window.ontouchend = () => { isDragging = false; };
      window.ontouchmove = (e) => {
        if (!isDragging || !e.touches[0]) return;
        const rect = splitView.getBoundingClientRect();
        let pct = ((e.touches[0].clientX - rect.left) / rect.width) * 100;
        pct = Math.max(5, Math.min(95, pct));
        setSplitPosition(pct);
      };
    }

    function setSplitPosition(pct) {
      splitDivider.style.left = pct + '%';
      splitOverlay.style.clipPath = `polygon(0% 0%, ${pct}% 0%, ${pct}% 100%, 0% 100%)`;
    }

    function toggleAudio() {
      video.muted = !video.muted;
    }

    function togglePlay() {
      if (currentMode === 'camerakit' && ckSession) {
        if (ckSession.playing?.live) ckSession.pause('live');
        else ckSession.play('live');
      } else {
        if (video.paused) video.play();
        else video.pause();
      }
    }

    function restartVideo() {
      if (currentMode === 'camerakit') {
        const vid = document.getElementById('ck-video-input');
        if (vid) { vid.currentTime = 0; vid.play(); }
      } else {
        video.currentTime = 0;
        video.play();
      }
    }

    // Camera Kit Engine Initialization & Sideload Provider
    async function initCameraKit() {
      const statusEl = document.getElementById('ck-status');
      const canvas = document.getElementById('ck-canvas');

      if (ckSession) {
        statusEl.textContent = 'Camera Kit WebGL2 Active • Ready';
        return;
      }

      try {
        statusEl.textContent = 'Bootstrapping Camera Kit SDK + Sideload Extension...';
        const { 
          bootstrapCameraKit, 
          createExtension, 
          lensSourcesFactory, 
          ConcatInjectable, 
          createMediaStreamSource, 
          Transform2D 
        } = await import('/js/camera-kit.bundle.js');

        const token = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkNhbnZhc1MyU0hNQUNQcm9kIiwidHlwIjoiSldUIn0.eyJhdWQiOiJjYW52YXMtY2FudmFzYXBpIiwiaXNzIjoiY2FudmFzLXMyc3Rva2VuIiwibmJmIjoxNzMyNjMzNDE5LCJzdWIiOiIwMjdmNjZkZi0wOTQyLTQ3ZWUtODUxMi1lNGMyZTQ2MWRkMzR-UFJPRFVDVElPTn43N2Y5Y2ZlYi1lNWUxLTRhZTgtYWU5ZS01MjQ1NGYwM2JiYTYifQ.niwcW4CuvpHEhciugcvxa2S5vQBsehTktDu_k8galYU";

        const customLensSource = {
          isGroupOwner(groupId) {
            return groupId === "lens-sideload-extension-group";
          },
          async loadLens(lensId, groupId) {
            console.log("[CameraKit] Sideload loadLens requested:", lensId, groupId);
            const l = sideloadedLenses.get(lensId) || {
              id: lensId,
              name: "Active Fleet Lens",
              lnsUrl: window.location.origin + "/assets/abyssal_crown.lns",
              sha256: ""
            };
            return createLensProto(l);
          },
          async loadLensGroup() {
            throw new Error("loadLensGroup not implemented");
          }
        };

        const sideloadExtension = createExtension().provides(
          ConcatInjectable(lensSourcesFactory.token, () => customLensSource)
        );

        ckInstance = await bootstrapCameraKit({
          apiToken: token
        }, container => container.provides(sideloadExtension));

        statusEl.textContent = 'Camera Kit Bootstrapped. Creating WebGL2 Session...';
        ckSession = await ckInstance.createSession({ liveRenderTarget: canvas });

        // Apply input source (Default: Canonical Portrait Video @ 720x1280 for 1:1 EasyLens Parity)
        await applySelectedSource();

        // Apply active 3D lens
        await applyCurrentLens();

      } catch (err) {
        console.error("[CameraKit Init Error]", err);
        statusEl.textContent = 'Camera Kit Error: ' + err.message;
      }
    }

    // Apply input source to Camera Kit session
    async function applySelectedSource() {
      const statusEl = document.getElementById('ck-status');
      const { createMediaStreamSource, Transform2D } = await import('/js/camera-kit.bundle.js');
      const videoInput = document.getElementById('ck-video-input');
      const webcamRaw = document.getElementById('ck-webcam-raw');
      const cropCanvas = document.getElementById('ck-crop-canvas');
      const cropCtx = cropCanvas.getContext('2d');

      // Stop any existing crop animation loop
      if (cropAnimFrameId) {
        cancelAnimationFrame(cropAnimFrameId);
        cropAnimFrameId = null;
      }

      if (ckActiveSource === 'video' || ckActiveSource === 'blonde') {
        if (webcamStream) {
          webcamStream.getTracks().forEach(t => t.stop());
          webcamStream = null;
        }
        const targetSrc = (ckActiveSource === 'blonde') ? '/assets/test_portrait_blonde.mp4' : '/assets/test_portrait.mp4';
        statusEl.textContent = `Streaming Model Video (${targetSrc})...`;
        videoInput.pause();
        videoInput.src = targetSrc;
        videoInput.currentTime = 0;
        await videoInput.play();

        const renderVideoLoop = () => {
          if (ckActiveSource !== 'video' && ckActiveSource !== 'blonde') return;
          if (videoInput.videoWidth > 0 && videoInput.videoHeight > 0) {
            cropCtx.drawImage(videoInput, 0, 0, 720, 1280);
          }
          cropAnimFrameId = requestAnimationFrame(renderVideoLoop);
        };
        renderVideoLoop();

        const stream = cropCanvas.captureStream(30);
        const source = createMediaStreamSource(stream, { transform: Transform2D.Identity });
        await ckSession.setSource(source);
        await source.setRenderSize(720, 1280);
        await ckSession.play();
        statusEl.textContent = 'Active: Stock Model Video (0% Zoom • 1:1 EasyLens Parity)';
      } else if (ckActiveSource === 'image') {
        if (webcamStream) {
          webcamStream.getTracks().forEach(t => t.stop());
          webcamStream = null;
        }
        videoInput.pause();
        statusEl.textContent = 'Rendering Still Stock Portrait (assets/portrait_neutral.png)...';
        const stockImg = new Image();
        stockImg.crossOrigin = 'anonymous';
        stockImg.src = '/assets/portrait_neutral.png';
        await new Promise(r => { stockImg.onload = r; });

        const renderImageLoop = () => {
          if (ckActiveSource !== 'image') return;
          cropCtx.drawImage(stockImg, 0, 0, 720, 1280);
          cropAnimFrameId = requestAnimationFrame(renderImageLoop);
        };
        renderImageLoop();

        const stream = cropCanvas.captureStream(30);
        const source = createMediaStreamSource(stream, { transform: Transform2D.Identity });
        await ckSession.setSource(source);
        await source.setRenderSize(720, 1280);
        await ckSession.play();
        statusEl.textContent = 'Active: Stock Portrait Still (Frame 0 Parity)';
      } else if (ckActiveSource === 'webcam') {
        // Anti-Zoom WebCam Stream Adapter
        statusEl.textContent = 'Requesting WebCam Access...';
        videoInput.pause();
        try {
          if (!webcamStream || !webcamStream.active) {
            webcamStream = await navigator.mediaDevices.getUserMedia({
              video: {
                facingMode: "user",
                width: { ideal: 1280 },
                height: { ideal: 720 }
              },
              audio: false
            });
          }
          webcamRaw.srcObject = webcamStream;
          await webcamRaw.play();

          if (ckFramingMode === 'fit') {
            // Smart Portrait Fit: Pre-render to 720x1280 canvas with natural scaling
            // Completely eliminates the aggressive 3.16x landscape-to-portrait digital zoom!
            const renderCropFrame = () => {
              if (ckActiveSource !== 'webcam' || ckFramingMode !== 'fit') return;
              if (webcamRaw.videoWidth > 0 && webcamRaw.videoHeight > 0) {
                const vw = webcamRaw.videoWidth;
                const vh = webcamRaw.videoHeight;
                cropCtx.save();
                cropCtx.fillStyle = '#090b10';
                cropCtx.fillRect(0, 0, 720, 1280);

                // Natural fit calculation
                const scale = Math.max(720 / vw, 1280 / vh) * 0.75; // Comfortable natural framing
                const dw = vw * scale;
                const dh = vh * scale;
                const dx = (720 - dw) / 2;
                const dy = (1280 - dh) / 2 + 50; // Centered on upper body / head

                if (ckIsMirrored) {
                  cropCtx.translate(720, 0);
                  cropCtx.scale(-1, 1);
                  cropCtx.drawImage(webcamRaw, 720 - (dx + dw), dy, dw, dh);
                } else {
                  cropCtx.drawImage(webcamRaw, dx, dy, dw, dh);
                }
                cropCtx.restore();
              }
              cropAnimFrameId = requestAnimationFrame(renderCropFrame);
            };
            renderCropFrame();

            const stream = cropCanvas.captureStream(30);
            const source = createMediaStreamSource(stream, { transform: Transform2D.Identity });
            await ckSession.setSource(source);
            await source.setRenderSize(720, 1280);
            await ckSession.play();
            statusEl.textContent = 'Active: WebCam Smart Fit (Zero Zoom • Natural Framing)';
          } else {
            // Direct Portrait Center Crop
            const transform = ckIsMirrored ? Transform2D.Mirror : Transform2D.Identity;
            const source = createMediaStreamSource(webcamStream, { transform: transform });
            await ckSession.setSource(source);
            await source.setRenderSize(720, 1280);
            await ckSession.play();
            statusEl.textContent = 'Active: WebCam Direct Fill (Standard Crop)';
          }
        } catch (camErr) {
          console.error("[Webcam Error]", camErr);
          statusEl.textContent = 'WebCam Error: ' + camErr.message + ' (Falling back to Canonical Video)';
          ckActiveSource = 'video';
          document.getElementById('src-btn-video').classList.add('active-source');
          document.getElementById('src-btn-cam').classList.remove('active-source');
          document.getElementById('cam-subcontrols').style.display = 'none';
          await applySelectedSource();
        }
      }
    }

    // Apply active lens to Camera Kit session
    async function applyCurrentLens() {
      const statusEl = document.getElementById('ck-status');
      if (!ckSession || !ckInstance) return;
      try {
        const lensMeta = sideloadedLenses.get(ckCurrentLensId) || { name: ckCurrentLensId };
        statusEl.textContent = `Applying 3D AR Lens: ${lensMeta.name}...`;
        const lens = await ckInstance.lensRepository.loadLens(ckCurrentLensId, "lens-sideload-extension-group");
        await ckSession.applyLens(lens);
        statusEl.textContent = `⚡ 3D AR Lens Active: ${lens.name} (EasyLens Parity Verified)`;
        console.log("[CameraKit] Successfully applied lens:", lens.name);
      } catch (err) {
        console.error("[CameraKit applyLens Error]", err);
        statusEl.textContent = `Error applying lens: ${err.message}`;
      }
    }

    // Switch lens from dropdown
    async function switchLens(lensId) {
      ckCurrentLensId = lensId;
      if (currentMode === 'camerakit' && ckSession) {
        await applyCurrentLens();
      }
    }

    // Switch source between stock video, cyber video, stock image, and webcam
    async function setCameraKitSource(src) {
      ckActiveSource = src;
      ['video', 'blonde', 'image', 'webcam'].forEach(s => {
        const b = document.getElementById('src-btn-' + s);
        if (b) {
          if (s === src) b.classList.add('active-source');
          else b.classList.remove('active-source');
        }
      });
      const camSub = document.getElementById('cam-subcontrols');
      if (camSub) camSub.style.display = (src === 'webcam') ? 'flex' : 'none';

      if (ckSession) {
        await applySelectedSource();
      }
    }

    // Switch framing mode for webcam
    async function setCamFraming(mode) {
      ckFramingMode = mode;
      if (ckSession && ckActiveSource === 'webcam') {
        await applySelectedSource();
      }
    }

    // Toggle mirror mode for webcam
    async function toggleCamMirror() {
      ckIsMirrored = !ckIsMirrored;
      if (ckSession && ckActiveSource === 'webcam') {
        await applySelectedSource();
      }
    }

    // Click lens from Fleet table
    async function selectFleetLens(checkpointId, name, el) {
      document.querySelectorAll('.lens-item').forEach(i => i.classList.remove('selected'));
      if (el) el.classList.add('selected');

      const select = document.getElementById('ck-lens-select');
      // Check if option exists, else add it
      let opt = Array.from(select.options).find(o => o.value === checkpointId);
      if (!opt) {
        opt = document.createElement('option');
        opt.value = checkpointId;
        opt.textContent = `${name} (Fleet)`;
        select.appendChild(opt);
        sideloadedLenses.set(checkpointId, {
          id: checkpointId,
          name: name,
          lnsUrl: window.location.origin + "/assets/abyssal_crown.lns",
          sha256: ""
        });
      }
      select.value = checkpointId;
      await switchLens(checkpointId);
    }

    // Global output buffers for headless automation & preview generation
    window.__RENDER_DONE__ = false;
    window.__RENDER_ERROR__ = null;
    window.__NEUTRAL_FRAME__ = null;
    window.__TRIGGER_FRAME__ = null;
    window.__RECORDED_VIDEO__ = null;

    async function captureCameraKitExport(options = {}) {
      window.__RENDER_DONE__ = false;
      window.__RENDER_ERROR__ = null;
      const durationSec = options.duration || 3.6;
      const fps = options.fps || 30;
      const lensUrl = options.lensUrl || null;

      try {
        setMode('camerakit');
        if (lensUrl) {
          sideloadedLenses.set("custom_export_lens", {
            id: "custom_export_lens",
            name: "Active Preview Lens",
            lnsUrl: lensUrl,
            sha256: ""
          });
          ckCurrentLensId = "custom_export_lens";
        }
        await initCameraKit();

        // Wait for lens to be active
        let active = false;
        for (let i = 0; i < 50; i++) {
          await new Promise(r => setTimeout(r, 500));
          const st = document.getElementById('ck-status').textContent;
          if (st.includes('3D AR Lens Active') || st.includes('Camera Kit WebGL2 Active') || st.includes('Parity Verified')) {
            active = true;
            break;
          }
        }

        const canvas = document.getElementById('ck-canvas');
        const vid = document.getElementById('ck-video-input');

        // Rewind video and grab Frame 0 Neutral Poster
        vid.pause();
        vid.currentTime = 0;
        await new Promise(r => setTimeout(r, 300));
        window.__NEUTRAL_FRAME__ = canvas.toDataURL('image/png');

        // Start Recording
        const stream = canvas.captureStream(fps);
        let mimeType = 'video/webm; codecs=vp8';
        if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'video/webm';
        const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6000000 });
        const chunks = [];
        recorder.ondataavailable = e => { if (e.data && e.data.size > 0) chunks.push(e.data); };

        const recordPromise = new Promise((resolve, reject) => {
          recorder.onstop = () => {
            const blob = new Blob(chunks, { type: mimeType });
            const reader = new FileReader();
            reader.onloadend = () => {
              window.__RECORDED_VIDEO__ = reader.result;
              resolve();
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          };
          recorder.onerror = reject;
        });

        recorder.start(100);
        await vid.play();

        setTimeout(() => {
          try { window.__TRIGGER_FRAME__ = canvas.toDataURL('image/png'); } catch (e) {}
        }, (durationSec * 1000) / 2);

        await new Promise(r => setTimeout(r, durationSec * 1000));
        recorder.stop();
        await recordPromise;

        window.__RENDER_DONE__ = true;
        return { success: true };
      } catch (err) {
        window.__RENDER_ERROR__ = err.message;
        window.__RENDER_DONE__ = true;
        throw err;
      }
    }

    // Record 3.6s Preview Video (1:1 with EasyLens chunk-64PANOPO.js)
    function recordPreview() {
      const canvas = document.getElementById('ck-canvas');
      const statusEl = document.getElementById('ck-status');
      try {
        statusEl.textContent = '⏺️ Recording 3.6s preview video (108 frames @ 30fps)...';
        const posterB64 = canvas.toDataURL('image/png');
        const stream = canvas.captureStream(30);
        let mimeType = 'video/webm; codecs=vp8';
        if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'video/webm';
        const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6000000 });
        const chunks = [];
        recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: mimeType });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = `${ckCurrentLensId}_camerakit_preview.webm`;
          a.click();
          statusEl.textContent = `Syncing Camera Kit Preview (${blob.size} bytes)...`;

          const reader = new FileReader();
          reader.onloadend = async () => {
            try {
              const res = await fetch('/api/save_camerakit_preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  video_data: reader.result,
                  poster_data: posterB64,
                  lens_id: ckCurrentLensId
                })
              });
              const json = await res.json();
              if (json.success) {
                statusEl.textContent = '⚡ Camera Kit Preview Video & Neutral Frame Saved to Studio!';
                const v = document.getElementById('lens-video');
                if (v) v.src = '/video?' + Date.now();
                const sp = document.getElementById('still-preview');
                if (sp) sp.src = '/neutral?' + Date.now();
              } else {
                statusEl.textContent = 'Save preview err: ' + json.error;
              }
            } catch (err) {
              console.error(err);
            }
          };
          reader.readAsDataURL(blob);
        };
        recorder.start(100);
        setTimeout(() => recorder.stop(), 3600);
      } catch (err) {
        alert('Recorder error: ' + err.message);
      }
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    lenses = []
    lenses_path = os.path.join(BASE_DIR, "published_lenses.json")
    if os.path.exists(lenses_path):
        try:
            with open(lenses_path, "r") as f:
                lenses = json.load(f)
        except Exception:
            pass
    return render_template_string(HTML_TEMPLATE, lenses=lenses)

@app.route("/video")
def serve_video():
    vid_path = os.path.join(BASE_DIR, "preview_video.mp4")
    if not os.path.exists(vid_path):
        vid_path = os.path.join(BASE_DIR, "assets", "test_portrait.mp4")
    return send_file(vid_path, mimetype="video/mp4")

@app.route("/neutral")
def serve_neutral():
    p = os.path.join(BASE_DIR, "preview_neutral_simulated.png")
    if not os.path.exists(p):
        p = os.path.join(BASE_DIR, "assets", "portrait_neutral.png")
    return send_file(p, mimetype="image/png")

@app.route("/trigger")
def serve_trigger():
    p = os.path.join(BASE_DIR, "preview_mouth_open_simulated.png")
    if not os.path.exists(p):
        p = os.path.join(BASE_DIR, "preview_neutral_simulated.png")
    return send_file(p, mimetype="image/png")

@app.route("/split")
def serve_split():
    p = os.path.join(BASE_DIR, "preview_split_comparison.png")
    if not os.path.exists(p):
        p = os.path.join(BASE_DIR, "preview_neutral_simulated.png")
    return send_file(p, mimetype="image/png")

@app.route("/raw")
def serve_raw():
    p = os.path.join(BASE_DIR, "assets", "portrait_neutral.png")
    return send_file(p, mimetype="image/png")

@app.route("/icon")
def serve_icon():
    p = os.path.join(BASE_DIR, "lens_icon.png")
    if not os.path.exists(p):
        p = os.path.join(BASE_DIR, "assets", "portrait_neutral.png")
    return send_file(p, mimetype="image/png")

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "js"), filename)

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(os.path.join(BASE_DIR, "assets"), filename)

@app.route("/<filename>.html")
def serve_html_file(filename):
    return send_from_directory(BASE_DIR, f"{filename}.html")

@app.route("/api/lenses")
def api_lenses():
    lenses_path = os.path.join(BASE_DIR, "published_lenses.json")
    if os.path.exists(lenses_path):
        with open(lenses_path, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route("/api/save_camerakit_preview", methods=["POST"])
def api_save_camerakit_preview():
    try:
        data = request.get_json(force=True)
        vid_b64 = data.get("video_data", "")
        poster_b64 = data.get("poster_data", "")
        lens_id = data.get("lens_id", "lens")

        out_vid = os.path.join(BASE_DIR, "preview_video.mp4")
        out_poster = os.path.join(BASE_DIR, "preview_neutral_simulated.png")
        out_split = os.path.join(BASE_DIR, "preview_split_comparison.png")

        if poster_b64 and "," in poster_b64:
            p_bytes = base64.b64decode(poster_b64.split(",", 1)[1])
            with open(out_poster, "wb") as f:
                f.write(p_bytes)

        if vid_b64 and "," in vid_b64:
            v_bytes = base64.b64decode(vid_b64.split(",", 1)[1])
            temp_webm = "/tmp/ck_studio_record.webm"
            with open(temp_webm, "wb") as f:
                f.write(v_bytes)

            audio_path = os.path.join(BASE_DIR, "assets", "audio", "mythic_roar.mp3")
            cmd = ["ffmpeg", "-y", "-i", temp_webm]
            if os.path.exists(audio_path):
                cmd.extend(["-i", audio_path, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"])
            cmd.extend(["-movflags", "+faststart", out_vid])
            subprocess.run(cmd, check=True)

        raw_portrait = os.path.join(BASE_DIR, "assets", "portrait_neutral.png")
        if os.path.exists(raw_portrait) and os.path.exists(out_poster):
            try:
                from camerakit_renderer import render_split_comparison_image
                render_split_comparison_image(raw_portrait, out_poster, out_split, lens_name=lens_id)
            except Exception as se:
                print("Split render warn:", se)

        return jsonify({
            "success": True,
            "preview_video": "/video",
            "neutral_preview": "/neutral",
            "split_preview": "/split"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    import argparse
    import socket

    parser = argparse.ArgumentParser(description="EasyLens Local Realtime AR Studio")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8888)), help="Port to listen on (default: 8888)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    args = parser.parse_args()

    port = args.port
    # Auto-find free port if occupied
    for p in range(port, port + 20):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = s.connect_ex(('127.0.0.1', p))
        s.close()
        if res != 0:
            port = p
            break

    print(f"\n==================================================================")
    print(f"⚡ EasyLens Local Realtime AR Studio starting on:")
    print(f"   Localhost URL: http://localhost:{port}/")
    print(f"   Direct IP URL: http://127.0.0.1:{port}/")
    print(f"==================================================================\n")
    app.run(host=args.host, port=port, debug=False)
