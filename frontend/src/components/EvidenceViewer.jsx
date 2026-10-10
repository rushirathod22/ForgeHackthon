import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Play, Pause, RotateCcw, Eye, PhoneCall, Sparkles, Footprints, ChevronRight, Film, MapPin, AlertCircle, Loader2 } from 'lucide-react';
import { apiUrl } from '../api';

// Event type visual configuration
const EVENT_TYPE_CONFIG = {
  SHOPLIFTING_CONCEALMENT: { label: '🚨 SHOPLIFTING', color: '#ef4444', bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.5)' },
  SUSPICIOUS_ENTRY_UNGUARDED: { label: '🚨 SUSPICIOUS ENTRY', color: '#ef4444', bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.5)' },
  GUARD_ABSENT: { label: '⚠️ GUARD ABSENT', color: '#f97316', bg: 'rgba(249,115,22,0.15)', border: 'rgba(249,115,22,0.5)' },
  ZONE_INTRUSION: { label: '🛡️ ZONE INTRUSION', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.4)' },
  LOITERING: { label: '⏱️ LOITERING', color: '#eab308', bg: 'rgba(234,179,8,0.12)', border: 'rgba(234,179,8,0.4)' },
  FAST_MOVEMENT: { label: '⚡ FAST MOVEMENT', color: '#a78bfa', bg: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.4)' },
  STOPPED_VEHICLE: { label: '🚗 STOPPED', color: '#60a5fa', bg: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.4)' },
  OBJECT_TRACKED: { label: '🎯 TRACKED', color: '#06b6d4', bg: 'rgba(6,182,212,0.1)', border: 'rgba(6,182,212,0.3)' },
};

// Attribute badge color mapping
const ATTR_COLOR_MAP = {
  black: '#1e293b', white: '#f1f5f9', gray: '#64748b', grey: '#64748b',
  red: '#ef4444', blue: '#3b82f6', green: '#22c55e', yellow: '#eab308',
  orange: '#f97316', purple: '#a855f7', pink: '#ec4899', silver: '#94a3b8',
  cyan: '#06b6d4',
};

const formatSec = (sec) => {
  if (sec === undefined || sec === null || isNaN(sec)) return '00:00';
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
};

// ── Box colours ──────────────────────────────────────────────────────────────
const MATCHED_COLOR = '#06b6d4';   // cyan  — matched query target
const CONTEXT_COLOR = '#94a3b8';   // slate — other detected objects

// Class → default colour for context boxes
const CLASS_COLOR_MAP = {
  person:     '#a78bfa',
  car:        '#34d399',
  truck:      '#fb923c',
  bus:        '#fbbf24',
  motorcycle: '#f472b6',
  bicycle:    '#38bdf8',
};

// Color for the target class bounding box reticle
const CLASS_COLORS = {
  person:     '#06b6d4', // electric cyan
  car:        '#38bdf8', // sky blue
  truck:      '#818cf8', // indigo
  bus:        '#fbbf24',
  motorcycle: '#f472b6',
  bicycle:    '#38bdf8',
};

export function EvidenceViewer({
  searchResult = null,
  selectedVideoId = 'all',
  videosList = [],
  onSelectVideo = null,
  currentVideoUrl = null,
  cameraCode = 'CAM_01',
  cameraName = 'SURVEILLANCE CHECKPOINT',
  timestampStr = '00:00',
  confidence = 90.0,
  targetClass = 'TARGET OBJECT',
  trackId = 1,
  matchCount = 0,
  clipUrl = '/videos/input/test_cctv.mp4',
  onTrackPerson,
  onCallSecurity,
  onNextMatch,
  // query context for multi-track highlighting
  queryText = '',
  searchResultsList = [],
}) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTimelineIndex, setActiveTimelineIndex] = useState(0);
  const [showAIBox, setShowAIBox] = useState(true);
  const videoRef = useRef(null);

  // All tracks for the current video (fetched from /api/v1/videos/{id}/tracks)
  const [allTracks, setAllTracks]     = useState([]);
  const [videoNativeW, setVideoNativeW] = useState(1920);
  const [videoNativeH, setVideoNativeH] = useState(1080);

  // Reprocess state
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [reprocessToast, setReprocessToast] = useState('');

  // Determine whether this is a real match or a "no match found" fallback
  const isNoMatch = !searchResult || Boolean(searchResult.is_no_match) || searchResult.event_type === 'NO_MATCH' || matchCount === 0;

  // Current video record in videosList
  const currentVidObj = videosList.find((v) => v.id === (searchResult?.video_id || selectedVideoId)) || videosList[0];

  // Resolved event type styling
  const eventTypeCfg = EVENT_TYPE_CONFIG[searchResult?.event_type] || EVENT_TYPE_CONFIG.OBJECT_TRACKED;

  // Detected visual attribute tags from result
  const visualAttrs = searchResult?.visual_attributes || [];

  // Derived values from searchResult prop if present
  const filenameForCode = searchResult?.video_filename || currentVidObj?.filename;
  const displayCamCode = filenameForCode
    ? `CAM_${filenameForCode.slice(0, 8).toUpperCase()}`
    : cameraCode;
  const displayCamName = searchResult?.video_filename || currentVidObj?.filename || cameraName;
  const displayClass = isNoMatch ? 'NO MATCH' : (searchResult?.class_name ? searchResult.class_name.toUpperCase() : targetClass);
  const displayConf = isNoMatch ? '0.0' : (searchResult?.confidence ? (searchResult.confidence * 100).toFixed(1) : confidence);
  const displayTrack = isNoMatch ? '--' : (searchResult?.track_id || trackId);
  const displayTime = isNoMatch ? '00:00' : (searchResult?.start_time_sec !== undefined
    ? `${Math.floor(searchResult.start_time_sec / 60).toString().padStart(2, '0')}:${Math.floor(searchResult.start_time_sec % 60).toString().padStart(2, '0')}`
    : timestampStr);

  const countDisplay = isNoMatch ? '0 matches' : `${matchCount} match${matchCount === 1 ? '' : 'es'}`;

  // Direct video stream URL from backend API for the active video
  const displayVideoSrc = searchResult?.video_url
    ? apiUrl(searchResult.video_url)
    : (searchResult?.clip_url
      ? apiUrl(searchResult.clip_url)
      : (currentVideoUrl || (currentVidObj ? apiUrl(`/api/v1/videos/${currentVidObj.id}/stream`) : apiUrl(clipUrl))));

  // Dynamic timeline events calculated from the actual detection or stream
  const startSec = isNoMatch ? 0.0 : (searchResult?.start_time_sec ?? 0.0);
  const endSec = isNoMatch ? (currentVidObj?.duration_sec || 10.0) : (searchResult?.end_time_sec ?? (startSec + 3.0));
  const peakSec = Math.round(((startSec + endSec) / 2) * 100) / 100;

  const handleReprocessWithGemini = async () => {
    const vidId = searchResult?.video_id || (selectedVideoId !== 'all' ? selectedVideoId : currentVidObj?.id);
    if (!vidId) return;
    setIsReprocessing(true);
    setReprocessToast('⏳ Queuing video for Gemini Vision re-analysis...');
    try {
      const res = await fetch(apiUrl(`/api/v1/videos/${vidId}/reprocess`), { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setReprocessToast('✓ Reprocessing queued with Gemini Vision! Check back in ~30s.');
        setTimeout(() => setReprocessToast(''), 7000);
      } else {
        setReprocessToast(`Error: ${data.detail || 'Could not queue'}`);
      }
    } catch (err) {
      setReprocessToast(`Error: ${err.message}`);
    } finally {
      setIsReprocessing(false);
    }
  };

  const timelineEvents = isNoMatch
    ? [
        {
          time: '00:00',
          seconds: 0,
          label: 'STREAM LOADED',
          detail: `CCTV video stream loaded for ${displayCamName}.`,
          active: true,
        },
        {
          time: formatSec(endSec),
          seconds: endSec,
          label: 'SEARCH EVALUATION',
          detail: `0 detections matched query "${queryText || 'search'}" in this footage.`,
        },
      ]
    : [
        {
          time: formatSec(startSec),
          seconds: startSec,
          label: `${displayClass} ENTERED FRAME`,
          detail: `Detected at timestamp ${startSec.toFixed(1)}s (Track #${displayTrack})`,
        },
        {
          time: formatSec(peakSec),
          seconds: peakSec,
          label: `${displayClass} IDENTIFIED`,
          detail: `Match confidence: ${displayConf}%${searchResult?.similarity ? ` • Vector similarity: ${(searchResult.similarity * 100).toFixed(1)}%` : ''}`,
          active: true,
        },
        {
          time: formatSec(endSec),
          seconds: endSec,
          label: `${searchResult?.event_type || 'ACTIVITY'} RECORDED`,
          detail: searchResult?.details || `Object motion path tracked across ${displayCamCode}`,
        },
      ];

  // When search result or video source changes, safely seek video to detection timestamp
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const targetTime = Math.max(0, (searchResult?.start_time_sec ?? 0) - 0.2);

    const seekAndPlay = () => {
      try {
        video.currentTime = targetTime;
        video.play().catch(() => {});
      } catch (err) {
        console.warn('Playback error:', err);
      }
    };

    video.addEventListener('loadedmetadata', seekAndPlay);
    if (video.readyState >= 1) {
      seekAndPlay();
    }
    setIsPlaying(true);
    setActiveTimelineIndex(0);

    return () => {
      video.removeEventListener('loadedmetadata', seekAndPlay);
    };
  }, [displayVideoSrc, searchResult?.start_time_sec]);

  const canvasRef = useRef(null);
  const [showTrail, setShowTrail] = useState(true);
  const [showContextTracks, setShowContextTracks] = useState(false);
  // ── Click-to-mark target zone (e.g. user clicks on stairs) ──────────────────
  const [isMarkingTarget, setIsMarkingTarget] = useState(false);
  // targetZone: {x, y} in video native coords (0..videoNativeW / 0..videoNativeH)
  const [targetZone, setTargetZone] = useState(null);

  // Tracks heading toward the targetZone (computed from trajectory vectors)
  // Returns a Set<track_id> of tracks whose net displacement points toward targetZone.
  const targetHeadingTrackIds = useMemo(() => {
    if (!targetZone || allTracks.length === 0) return null;
    const result = new Set();
    const APPROACH_RADIUS = Math.max(videoNativeW, videoNativeH) * 0.20; // 20% of frame
    for (const track of allTracks) {
      if (!track.trajectory || track.trajectory.length < 3) continue;
      const first = track.trajectory[0];
      const last  = track.trajectory[track.trajectory.length - 1];
      // Vector from first → last (net displacement)
      const dx = last.x - first.x;
      const dy = last.y - first.y;
      // Vector from first → target
      const tx = targetZone.x - first.x;
      const ty = targetZone.y - first.y;
      // Dot product: positive = generally heading toward target
      const dot = dx * tx + dy * ty;
      // Final distance to target
      const distEnd = Math.hypot(last.x - targetZone.x, last.y - targetZone.y);
      if (dot > 0 && distEnd < APPROACH_RADIUS) {
        result.add(track.track_id);
      }
    }
    return result;
  }, [targetZone, allTracks, videoNativeW, videoNativeH]);

  // ── Matched track IDs for canvas highlighting ─────────────────────────────
  // Must be AFTER targetHeadingTrackIds so we can reference it.
  const MAX_HIGHLIGHTED = 5;
  const matchedTrackIds = useMemo(() => {
    // When there is no match for the search query, do NOT highlight arbitrary tracks as "MATCH"
    if (isNoMatch) {
      return new Set();
    }
    // When user has clicked a target zone: use direction-based filter
    if (targetHeadingTrackIds !== null) {
      const s = new Set(targetHeadingTrackIds);
      if (searchResult?.track_id != null) s.add(searchResult.track_id);
      return s;
    }
    // Otherwise: top-N results from search by score
    const topResults = [...searchResultsList]
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, MAX_HIGHLIGHTED);
    const s = new Set(topResults.map((r) => r.track_id).filter((id) => id != null));
    if (searchResult?.track_id != null) s.add(searchResult.track_id);

    return s;
  }, [targetHeadingTrackIds, searchResultsList, searchResult?.track_id, isNoMatch]);

  // Handle click on canvas in marking mode
  const handleCanvasClick = useCallback((e) => {
    if (!isMarkingTarget) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;
    // Convert display coords → native video coords
    const vx = (clickX / rect.width)  * videoNativeW;
    const vy = (clickY / rect.height) * videoNativeH;
    setTargetZone({ x: vx, y: vy });
    setIsMarkingTarget(false);
  }, [isMarkingTarget, videoNativeW, videoNativeH]);

  // ── Fetch all tracks when video changes ───────────────────────────────────
  useEffect(() => {
    const vidId = searchResult?.video_id || (selectedVideoId !== 'all' ? selectedVideoId : currentVidObj?.id);
    if (!vidId) {
      setAllTracks([]);
      return;
    }
    fetch(apiUrl(`/api/v1/videos/${vidId}/tracks`))
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setAllTracks(data.tracks || []);
          setVideoNativeW(data.video_width  || 1920);
          setVideoNativeH(data.video_height || 1080);
        }
      })
      .catch((err) => console.warn('Could not fetch tracks:', err));
  }, [searchResult?.video_id, selectedVideoId, currentVidObj?.id]);

  // Handle video time update to sync timeline status
  const handleTimeUpdate = (e) => {
    const t = e.target.currentTime;
    setCurrentTime(t);

    // Update active timeline step
    if (t >= endSec) setActiveTimelineIndex(2);
    else if (t >= peakSec) setActiveTimelineIndex(1);
    else setActiveTimelineIndex(0);
  };

  // ── Helper: interpolate a track's position at time t ─────────────────────
  const interpTrack = useCallback((trajectory, curT) => {
    if (!trajectory || trajectory.length === 0) return null;
    let pPrev = null;
    let pNext = null;
    for (let i = 0; i < trajectory.length; i++) {
      if (trajectory[i].t <= curT) pPrev = trajectory[i];
      else { pNext = trajectory[i]; break; }
    }
    if (!pPrev && !pNext) return null;

    let x, y, w, h, active;
    const GAP = 1.5; // seconds grace period after track ends
    if (pPrev && pNext) {
      const span = pNext.t - pPrev.t;
      const ratio = span > 0.001 ? Math.max(0, Math.min(1, (curT - pPrev.t) / span)) : 0;
      x = pPrev.x + (pNext.x - pPrev.x) * ratio;
      y = pPrev.y + (pNext.y - pPrev.y) * ratio;
      w = (pPrev.w || 120) + ((pNext.w || 120) - (pPrev.w || 120)) * ratio;
      h = (pPrev.h || 140) + ((pNext.h || 140) - (pPrev.h || 140)) * ratio;
      active = true;
    } else if (pPrev) {
      x = pPrev.x; y = pPrev.y; w = pPrev.w || 120; h = pPrev.h || 140;
      active = curT - pPrev.t <= GAP;
    } else {
      x = pNext.x; y = pNext.y; w = pNext.w || 120; h = pNext.h || 140;
      active = pNext.t - curT <= GAP;
    }
    return active ? { x, y, w, h } : null;
  }, []);

  // ── Draw corner reticle on canvas ─────────────────────────────────────────
  const drawReticle = useCallback((ctx, bx, by, bw, bh, color, lineW = 3) => {
    const cLen = Math.min(16, bw / 3);
    ctx.strokeStyle = color;
    ctx.lineWidth = lineW;
    // TL
    ctx.beginPath(); ctx.moveTo(bx, by + cLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cLen, by); ctx.stroke();
    // TR
    ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cLen); ctx.stroke();
    // BL
    ctx.beginPath(); ctx.moveTo(bx, by + bh - cLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + cLen, by + bh); ctx.stroke();
    // BR
    ctx.beginPath(); ctx.moveTo(bx + bw - cLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - cLen); ctx.stroke();
  }, []);

  // ── Main 60fps canvas render loop ─────────────────────────────────────────
  useEffect(() => {
    let animId;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const ctx = canvas.getContext('2d');

    const renderFrame = () => {
      // Sync canvas size to video element
      const rect = video.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        if (canvas.width !== Math.round(rect.width) || canvas.height !== Math.round(rect.height)) {
          canvas.width  = Math.round(rect.width);
          canvas.height = Math.round(rect.height);
        }
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!showAIBox) { animId = requestAnimationFrame(renderFrame); return; }

      const curT   = video.currentTime;
      const scaleX = canvas.width  / videoNativeW;
      const scaleY = canvas.height / videoNativeH;

      // ── Pass 1: context tracks (optional, very faint) ────────────────────
      // Only drawn when user explicitly toggles "SHOW ALL"
      // Rendered as tiny corner marks only — NO fill, NO label → cannot be
      // confused with matched (cyan) tracks.
      if (showContextTracks) {
        for (const track of allTracks) {
          if (matchedTrackIds.has(track.track_id)) continue;
          const pos = interpTrack(track.trajectory, curT);
          if (!pos) continue;

          const bw = Math.max(24, pos.w * scaleX);
          const bh = Math.max(24, pos.h * scaleY);
          const bx = pos.x * scaleX - bw / 2;
          const by = pos.y * scaleY - bh / 2;

          // Very faint 1px dashed border only — no fill, no label
          ctx.strokeStyle = 'rgba(148,163,184,0.20)';
          ctx.lineWidth = 0.8;
          ctx.setLineDash([3, 6]);
          ctx.strokeRect(bx, by, bw, bh);
          ctx.setLineDash([]);
        }
      }

      // ── Pass 2: draw matched (highlighted) tracks ─────────────────────────
      for (const track of allTracks) {
        if (!matchedTrackIds.has(track.track_id)) continue;
        const pos = interpTrack(track.trajectory, curT);
        if (!pos) continue;

        const bw = Math.max(40, pos.w * scaleX);
        const bh = Math.max(40, pos.h * scaleY);
        const cx = pos.x * scaleX;
        const cy = pos.y * scaleY;
        const bx = cx - bw / 2;
        const by = cy - bh / 2;

        // Trail
        if (showTrail && track.trajectory.length > 1) {
          ctx.beginPath();
          ctx.strokeStyle = MATCHED_COLOR + 'aa';
          ctx.lineWidth = 2;
          ctx.setLineDash([5, 5]);
          let started = false;
          for (const pt of track.trajectory) {
            if (pt.t <= curT && curT - pt.t <= 6.0) {
              const px = pt.x * scaleX;
              const py = pt.y * scaleY;
              if (!started) { ctx.moveTo(px, py); started = true; }
              else ctx.lineTo(px, py);
            }
          }
          if (started) { ctx.lineTo(cx, cy); ctx.stroke(); }
          ctx.setLineDash([]);
        }

        // Glow fill
        ctx.fillStyle = 'rgba(6, 182, 212, 0.13)';
        ctx.fillRect(bx, by, bw, bh);

        // Bright outline
        ctx.strokeStyle = MATCHED_COLOR;
        ctx.lineWidth = 2;
        ctx.strokeRect(bx, by, bw, bh);

        // Corner reticles
        drawReticle(ctx, bx, by, bw, bh, '#22d3ee', 3);

        // Header label badge
        const isActiveResult = track.track_id === searchResult?.track_id;
        const isActualMatch = !isNoMatch && (isActiveResult || searchResultsList.some((r) => r.track_id === track.track_id));
        const labelText = isActiveResult
          ? `✦ TARGET: ${track.class_name.toUpperCase()} • TRACK #${track.track_id}`
          : isActualMatch
            ? `◉ MATCH: ${track.class_name.toUpperCase()} #${track.track_id}`
            : `◉ TRACK #${track.track_id}`;
        ctx.font = 'bold 11px Inter, monospace';
        const textW = ctx.measureText(labelText).width;
        ctx.fillStyle = isActualMatch || isActiveResult ? MATCHED_COLOR : 'rgba(100, 116, 139, 0.9)';
        ctx.fillRect(bx, Math.max(0, by - 22), textW + 16, 20);
        ctx.fillStyle = isActualMatch || isActiveResult ? '#020617' : '#ffffff';
        ctx.fillText(labelText, bx + 8, Math.max(14, by - 6));

        // Sub-label (only for primary active result)
        if (isActiveResult) {
          const subText = `CONF: ${displayConf}% • LOCKED`;
          ctx.font = '10px monospace';
          const subW = ctx.measureText(subText).width;
          ctx.fillStyle = 'rgba(15,23,42,0.85)';
          ctx.fillRect(bx, by + bh + 3, subW + 12, 17);
          ctx.fillStyle = '#38bdf8';
          ctx.fillText(subText, bx + 6, by + bh + 15);
        }
      }

      // ── Fallback: if no allTracks yet, draw single-track from searchResult ─
      if (allTracks.length === 0 && searchResult?.trajectory?.length > 0) {
        const pos = interpTrack(searchResult.trajectory, curT);
        if (pos) {
          const bw = Math.max(40, pos.w * scaleX);
          const bh = Math.max(40, pos.h * scaleY);
          const bx = pos.x * scaleX - bw / 2;
          const by = pos.y * scaleY - bh / 2;
          ctx.strokeStyle = MATCHED_COLOR; ctx.lineWidth = 2;
          ctx.strokeRect(bx, by, bw, bh);
          ctx.fillStyle = 'rgba(6,182,212,0.13)'; ctx.fillRect(bx, by, bw, bh);
          drawReticle(ctx, bx, by, bw, bh, '#22d3ee', 3);
        }
      }

      // ── Draw target zone crosshair (if user marked a destination) ─────────────
      if (targetZone) {
        const tx = targetZone.x * scaleX;
        const ty = targetZone.y * scaleY;
        const R  = 22;

        // Pulsing outer glow circle
        ctx.save();
        ctx.beginPath();
        ctx.arc(tx, ty, R + 6, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(236,72,153,0.35)';
        ctx.lineWidth = 8;
        ctx.stroke();

        // Inner solid circle
        ctx.beginPath();
        ctx.arc(tx, ty, R, 0, Math.PI * 2);
        ctx.strokeStyle = '#ec4899';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.fillStyle = 'rgba(236,72,153,0.18)';
        ctx.fill();

        // Crosshair lines
        ctx.strokeStyle = '#ec4899';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(tx - R - 10, ty); ctx.lineTo(tx + R + 10, ty); ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(tx, ty - R - 10); ctx.lineTo(tx, ty + R + 10); ctx.stroke();

        // Label
        ctx.font = 'bold 10px monospace';
        ctx.fillStyle = '#ec4899';
        ctx.fillText('📍 DESTINATION', tx + R + 4, ty - 6);
        const matchCount = matchedTrackIds.size;
        ctx.fillStyle = 'rgba(236,72,153,0.9)';
        ctx.fillText(`${matchCount} track${matchCount !== 1 ? 's' : ''} heading here`, tx + R + 4, ty + 8);
        ctx.restore();
      }

      animId = requestAnimationFrame(renderFrame);
    };

    animId = requestAnimationFrame(renderFrame);
    return () => cancelAnimationFrame(animId);
  }, [showAIBox, showTrail, showContextTracks, targetZone, searchResult, allTracks, matchedTrackIds,
      videoNativeW, videoNativeH, displayClass, displayTrack, displayConf,
      interpTrack, drawReticle]);

  // Click timeline step to seek video to exact timestamp
  const handleTimelineClick = (index, seconds) => {
    setActiveTimelineIndex(index);
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) videoRef.current.pause();
      else videoRef.current.play();
      setIsPlaying(!isPlaying);
    }
  };

  return (
    <div className="evidence-experience-container">
      {/* Top Evidence HUD Header */}
      <div className="evidence-hud-header">
        <div className="hud-left">
          {/* Event type badge — color coded by severity */}
          <div
            className="hud-badge-gold"
            style={{
              background: eventTypeCfg.bg,
              border: `1px solid ${eventTypeCfg.border}`,
              color: eventTypeCfg.color,
            }}
          >
            <Sparkles size={14} />
            <span>{eventTypeCfg.label}</span>
          </div>
          <div className="hud-target-title">{displayClass}</div>

          {/* Why matched? — split into queried-matched vs. other attributes */}
          {(searchResult?.matched_attrs?.length > 0 || visualAttrs.length > 0) && (() => {
            const matchedSet = new Set(searchResult?.matched_attrs ?? []);
            const otherAttrs = visualAttrs.filter((a) => !matchedSet.has(a));
            return (
              <div style={{ marginTop: '6px' }}>
                {matchedSet.size > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                    <span style={{ fontSize: '9px', fontFamily: 'monospace', color: '#22d3ee', fontWeight: 700, letterSpacing: '0.05em', marginRight: 2 }}>✓ MATCHED:</span>
                    {[...matchedSet].map((attr) => {
                      const baseColor = attr.replace(/_shirt|_pants|_jacket|_dress/, '');
                      const bg = ATTR_COLOR_MAP[baseColor] ?? '#06b6d4';
                      return (
                        <span key={attr} style={{
                          display: 'inline-flex', alignItems: 'center', gap: '3px',
                          padding: '2px 8px', borderRadius: '12px',
                          fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold',
                          letterSpacing: '0.04em', textTransform: 'uppercase',
                          border: `1px solid ${bg}88`, background: `${bg}33`,
                          color: baseColor === 'black' ? '#94a3b8' : bg,
                          boxShadow: `0 0 6px ${bg}44`,
                        }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: bg, flexShrink: 0 }} />
                          {attr.replace(/_/g, '\u00A0')}
                        </span>
                      );
                    })}
                  </div>
                )}
                {otherAttrs.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center', marginTop: '3px' }}>
                    <span style={{ fontSize: '9px', fontFamily: 'monospace', color: '#475569', fontWeight: 700, letterSpacing: '0.05em', marginRight: 2 }}>DETECTED:</span>
                    {otherAttrs.map((attr, i) => {
                      const baseColor = attr.replace(/_shirt|_pants|_jacket|_dress/, '');
                      const bg = ATTR_COLOR_MAP[baseColor];
                      return (
                        <span key={i} style={{
                          display: 'inline-flex', alignItems: 'center', gap: '3px',
                          padding: '2px 7px', borderRadius: '12px',
                          fontSize: '9px', fontFamily: 'monospace', fontWeight: 'bold',
                          letterSpacing: '0.04em', textTransform: 'uppercase',
                          border: `1px solid ${bg || '#64748b'}44`,
                          background: `${bg || '#64748b'}11`,
                          color: '#475569',
                        }}>
                          {bg && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: bg, opacity: 0.5, flexShrink: 0 }} />}
                          {attr.replace(/_/g, '\u00A0')}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })()}

        </div>

        <div className="hud-right">
          {videosList && videosList.length > 0 && onSelectVideo && (
            <div className="meta-tag mono" style={{ borderColor: 'rgba(6, 182, 212, 0.4)', padding: '2px 8px' }}>
              <span>ACTIVE CAMERA:</span>
              <select
                style={{
                  background: 'transparent',
                  color: '#06B6D4',
                  border: 'none',
                  outline: 'none',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontFamily: 'inherit',
                  maxWidth: '190px',
                  fontWeight: 'bold',
                }}
                value={selectedVideoId || ''}
                onChange={(e) => onSelectVideo(e.target.value)}
              >
                <option value="all" style={{ background: '#0f172a', color: '#f8fafc' }}>
                  🌐 All Cameras
                </option>
                {videosList.map((v) => (
                  <option key={v.id} value={v.id} style={{ background: '#0f172a', color: '#f8fafc' }}>
                    📹 {v.filename}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="meta-tag mono">
            <span>FOUND:</span> <strong style={{ color: isNoMatch ? '#f87171' : '#06B6D4' }}>{countDisplay}</strong>
            {matchedTrackIds.size > 0 && !isNoMatch && (
              <span style={{ marginLeft: '6px', fontSize: '9px', color: '#22d3ee', background: 'rgba(6,182,212,0.12)', padding: '1px 5px', borderRadius: '4px', fontWeight: 'bold' }}>
                🎯 {matchedTrackIds.size} ON CANVAS
              </span>
            )}
          </div>
          <div className="meta-tag mono">
            <span>FILE:</span> {displayCamName.length > 22 ? `${displayCamName.slice(0, 20)}...` : displayCamName}
          </div>
          <div className="meta-tag mono">
            <span>TIMESTAMP:</span> {displayTime} ({currentTime.toFixed(1)}s)
          </div>
          <div className="meta-tag mono conf-tag">
            <span>CONFIDENCE:</span> {displayConf}%
          </div>
          {searchResult?.similarity > 0 && (
            <div className="meta-tag mono" style={{ borderColor: 'rgba(6, 182, 212, 0.5)', color: '#06b6d4' }}>
              <span>VECTOR SIM:</span> {(searchResult.similarity * 100).toFixed(1)}%
            </div>
          )}
          {visualAttrs.length > 0 && (
            <div className="meta-tag mono" style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              <span>TAGS:</span>
              {visualAttrs.map((tag) => {
                const isMatched = searchResult?.matched_attrs?.includes(tag);
                return (
                  <span
                    key={tag}
                    style={{
                      background: isMatched ? 'rgba(6,182,212,0.25)' : 'rgba(255,255,255,0.06)',
                      color: isMatched ? '#22d3ee' : '#94a3b8',
                      border: `1px solid ${isMatched ? '#06b6d4' : '#334155'}`,
                      borderRadius: '4px',
                      padding: '1px 5px',
                      fontSize: '10px',
                      fontWeight: isMatched ? 700 : 500,
                    }}
                  >
                    {isMatched ? '✓ ' : ''}{tag.replace(/_/g, ' ')}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* No Match Info Banner */}
      {isNoMatch && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          color: '#fca5a5',
          padding: '10px 16px',
          borderRadius: '8px',
          marginBottom: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.85rem',
          flexWrap: 'wrap',
          gap: '8px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertCircle size={18} color="#ef4444" />
            <span>
              No detections matched <strong>"{queryText || 'query'}"</strong> in <em>{displayCamName}</em>. Showing raw video stream for manual review.
            </span>
          </div>
          <button
            onClick={handleReprocessWithGemini}
            disabled={isReprocessing}
            style={{
              background: '#06b6d4',
              color: '#020617',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 12px',
              fontWeight: 700,
              fontSize: '0.78rem',
              cursor: isReprocessing ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            {isReprocessing ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            <span>{isReprocessing ? 'Reprocessing...' : 'Re-analyze with Gemini Vision'}</span>
          </button>
        </div>
      )}

      {/* Reprocess Status Notification Toast */}
      {reprocessToast && (
        <div style={{
          background: 'rgba(6, 182, 212, 0.15)',
          border: '1px solid rgba(6, 182, 212, 0.4)',
          color: '#22d3ee',
          padding: '8px 14px',
          borderRadius: '6px',
          marginBottom: '10px',
          fontSize: '0.82rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <Sparkles size={14} />
          <span>{reprocessToast}</span>
        </div>
      )}

      {/* Main CCTV Evidence Stage */}
      <div className="evidence-video-stage">
        <video
          key={displayVideoSrc}
          ref={videoRef}
          className="evidence-video-element"
          src={displayVideoSrc}
          autoPlay
          loop
          muted
          playsInline
          onTimeUpdate={handleTimeUpdate}
        />

        {/* 60 FPS HTML5 Canvas Overlay for Live Tracking Reticle & Trajectory Trail */}
        <canvas
          ref={canvasRef}
          className="live-tracker-canvas"
          onClick={handleCanvasClick}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: isMarkingTarget ? 'auto' : 'none',
            cursor: isMarkingTarget ? 'crosshair' : 'default',
            zIndex: 10,
          }}
        />

        {/* Marking mode overlay hint */}
        {isMarkingTarget && (
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(236,72,153,0.9)',
            color: '#fff', padding: '10px 20px', borderRadius: '8px',
            fontFamily: 'monospace', fontSize: '13px', fontWeight: 'bold',
            pointerEvents: 'none', zIndex: 20, letterSpacing: '0.05em',
            border: '1px solid rgba(255,255,255,0.3)',
            boxShadow: '0 0 30px rgba(236,72,153,0.6)',
          }}>
            📍 CLICK EXACTLY WHERE THE DESTINATION IS
          </div>
        )}

        {/* Video Control Bar Overlay */}
        <div className="video-minimal-controls">
          <button className="control-btn" onClick={togglePlay}>
            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="control-btn" onClick={() => (videoRef.current.currentTime = startSec)}>
            <RotateCcw size={16} />
          </button>
          <div className="video-rec-badge mono">
            <span className="rec-dot"></span> TIME: {formatSec(currentTime)} / {formatSec(endSec + 2)} • TRACK #{displayTrack}
          </div>
          <button
            className={`control-btn toggle-box ${showAIBox ? 'active' : ''}`}
            onClick={() => setShowAIBox(!showAIBox)}
            title="Toggle Live AI Target Reticle"
          >
            <Eye size={14} />
            <span>AI RETICLE</span>
          </button>
          <button
            className={`control-btn toggle-box ${showTrail ? 'active' : ''}`}
            onClick={() => setShowTrail(!showTrail)}
            title="Toggle Trajectory Motion Trail"
          >
            <Footprints size={14} />
            <span>TRAIL</span>
          </button>
          <button
            className={`control-btn toggle-box ${showContextTracks ? 'active' : ''}`}
            onClick={() => setShowContextTracks(!showContextTracks)}
            title="Show all detected objects as faint outlines"
            style={{ opacity: 0.7 }}
          >
            <Eye size={14} />
            <span>SHOW ALL</span>
          </button>

          {/* MARK ZONE: user clicks on the video to set a destination target */}
          {!targetZone ? (
            <button
              className={`control-btn toggle-box ${isMarkingTarget ? 'active' : ''}`}
              onClick={() => setIsMarkingTarget(!isMarkingTarget)}
              title="Click on the video to mark a destination (e.g. stairs)"
              style={{
                borderColor: isMarkingTarget ? '#ec4899' : undefined,
                color: isMarkingTarget ? '#ec4899' : undefined,
                animation: isMarkingTarget ? 'pulse 1s infinite' : 'none',
              }}
            >
              <MapPin size={14} />
              <span>{isMarkingTarget ? 'CLICK TARGET…' : 'MARK ZONE'}</span>
            </button>
          ) : (
            <button
              className="control-btn toggle-box active"
              onClick={() => { setTargetZone(null); setIsMarkingTarget(false); }}
              title="Clear the marked destination zone"
              style={{ borderColor: '#ec4899', color: '#ec4899' }}
            >
              <MapPin size={14} />
              <span>CLEAR ZONE ({matchedTrackIds.size})</span>
            </button>
          )}
        </div>
      </div>

      {/* Intelligent Event Timeline */}
      <div className="intelligent-timeline-wrapper">
        <div className="timeline-title mono">
          OBJECT DETECTION TIMELINE (CLICK ANY STEP TO JUMP VIDEO TO THAT SECOND)
        </div>
        <div className="timeline-track">
          {timelineEvents.map((evt, idx) => (
            <div
              key={idx}
              className={`timeline-step ${activeTimelineIndex === idx ? 'active-step' : ''}`}
              onClick={() => handleTimelineClick(idx, evt.seconds)}
              style={{ cursor: 'pointer' }}
            >
              <div className="step-marker">
                <div className="marker-dot"></div>
              </div>
              <div className="step-time mono">{evt.time}</div>
              <div className="step-label">{evt.label}</div>
              <div className="step-detail">{evt.detail}</div>
            </div>
          ))}
        </div>
      </div>

      {/* AI Explanation Integrated Section */}
      <div className="ai-integrated-explanation">
        <div className="ai-explanation-avatar">
          <div className="mini-orb-pulse"></div>
          <span className="mono">ASK</span>
        </div>

        <div className="ai-explanation-content">
          {isNoMatch ? (
            <p className="explanation-text">
              "I scanned this footage for <strong>"{queryText || 'your query'}"</strong>, but found <strong>0 matches</strong> in <em>{displayCamName}</em>. Showing the full CCTV stream for manual inspection. You can re-analyze with Gemini Vision or pick another camera above."
            </p>
          ) : (
            <p className="explanation-text">
              "I found <strong>{countDisplay}</strong> in this video. <strong>{displayClass}</strong> (Track #{displayTrack}) was detected between <strong>{formatSec(startSec)}</strong> and <strong>{formatSec(endSec)}</strong> with <strong>{displayConf}% confidence</strong>."
            </p>
          )}

          <div className="natural-next-actions">
            <span className="action-label mono">RECOMMENDED NEXT ACTIONS:</span>
            <div className="action-buttons-row">
              {isNoMatch ? (
                <button className="action-chip primary" onClick={handleReprocessWithGemini} disabled={isReprocessing}>
                  <Sparkles size={14} />
                  <span>{isReprocessing ? 'RE-ANALYZING...' : 'RE-ANALYZE WITH GEMINI VISION'}</span>
                </button>
              ) : (
                <button className="action-chip primary" onClick={onTrackPerson}>
                  <Footprints size={14} />
                  <span>TRACK THIS OBJECT</span>
                </button>
              )}

              {matchCount > 1 && (
                <button className="action-chip" onClick={onNextMatch}>
                  <ChevronRight size={14} />
                  <span>NEXT MATCH ({matchCount} total)</span>
                </button>
              )}

              {/* Clip download — only shown when a valid clip actually exists on the server */}
              {searchResult?.clip_url && (
                <a
                  href={apiUrl(searchResult.clip_url)}
                  download
                  className="action-chip"
                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  title="Download event clip"
                >
                  <Film size={14} />
                  <span>SAVE CLIP</span>
                </a>
              )}

              <button className="action-chip alert-action" onClick={onCallSecurity}>
                <PhoneCall size={14} />
                <span>CALL SECURITY</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EvidenceViewer;
