import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { AiOrbCanvas } from './components/AiOrbCanvas';
import { CameraUniverse } from './components/CameraUniverse';
import { EvidenceViewer } from './components/EvidenceViewer';
import { PersonJourney } from './components/PersonJourney';
import { SecurityCallAssistant } from './components/SecurityCallAssistant';
import { FloatingDock } from './components/FloatingDock';
import { Mic, MicOff, Sparkles, Volume2, Upload, FileVideo, CheckCircle2, AlertCircle, Loader2, Key, Search, Video, ShieldAlert, MapPin, ShieldCheck, Footprints, Check, PhoneCall } from 'lucide-react';
import { apiUrl } from './api';
import { GeminiKeyModal } from './components/GeminiKeyModal';

export function App() {
const [currentScreen, setCurrentScreen] = useState(1);
const [queryText, setQueryText] = useState('Find the customer wearing a red shirt who picked up a mobile phone near Electronics and moved toward the exit.');
const [videosList, setVideosList] = useState([]);
const [selectedVideoId, setSelectedVideoId] = useState('all');
const [selectedTimeFilter, setSelectedTimeFilter] = useState('Today');
const [isListening, setIsListening] = useState(false);
const [isSearching, setIsSearching] = useState(false);
const [extractedConcepts, setExtractedConcepts] = useState([]);
const [activeSearchResult, setActiveSearchResult] = useState(null);
const [searchResultsList, setSearchResultsList] = useState([]);
const [currentResultIdx, setCurrentResultIdx] = useState(0);

// Gemini Vision API Key state
const [isGeminiModalOpen, setIsGeminiModalOpen] = useState(false);
const [geminiConfigured, setGeminiConfigured] = useState(false);

const [conversationHistory, setConversationHistory] = useState([
{
sender: 'ASK',
text: 'Hello. I am ASK, your AI Video Intelligence Assistant. I am connected to active CCTV streams.',
time: 'Just now',
},
]);

const [aiSpeechText, setAiSpeechText] = useState('');

// Video Upload State
const [uploadStatus, setUploadStatus] = useState(null); // null | 'uploading' | 'processing' | 'success' | 'error'
const [uploadProgressMsg, setUploadProgressMsg] = useState('');
const [uploadProgressPct, setUploadProgressPct] = useState(0);   // 0-100
const [uploadProgressDetails, setUploadProgressDetails] = useState(''); // e.g. "Frame 120/500 • 3 detections"
const sseRef = useRef(null);
  const pollTimerRef = useRef(null); // SSE EventSource reference for cleanup
const searchInputRef = useRef(null); // auto-focus after upload
const [activeVideoName, setActiveVideoName] = useState(''); // name of currently selected/active video

// Fetch indexed CCTV videos from backend
const fetchVideos = async () => {
try {
const res = await fetch(apiUrl('/api/v1/videos'));
if (res.ok) {
const data = await res.json();
setVideosList(data);
return data;
}
} catch (err) {
console.warn('Could not fetch videos from backend:', err);
}
return [];
};

// Load initial video details & events when a specific video is activated
const loadVideoInitialState = async (vidId) => {
if (!vidId || vidId === 'all') return;
try {
const res = await fetch(apiUrl(`/api/v1/videos/${vidId}`));
if (res.ok) {
const data = await res.json();
if (data.events && data.events.length > 0) {
setSearchResultsList(data.events);
setCurrentResultIdx(0);
setActiveSearchResult(data.events[0]);
} else {
setSearchResultsList([]);
setActiveSearchResult({
video_id: data.id,
video_filename: data.filename,
video_url: `/api/v1/videos/${data.id}/stream`,
class_name: 'MONITORED OBJECT',
confidence: 0.95,
start_time_sec: 0,
end_time_sec: data.duration_sec || 5,
event_type: 'CCTV_STREAM',
details: `Active CCTV stream: ${data.filename}`,
trajectory: [],
});
}
}
} catch (e) {
console.warn('Error loading video details:', e);
}
};

const handleVideoSelect = (vidId) => {
setSelectedVideoId(vidId);
if (vidId !== 'all') {
loadVideoInitialState(vidId);
}
};

// Fetch videos on mount and select the latest completed video
useEffect(() => {
fetchVideos().then((vids) => {
const completed = vids.filter((v) => v.status === 'COMPLETED');
if (completed.length > 0) {
setSelectedVideoId(completed[0].id);
setActiveVideoName(completed[0].filename);
loadVideoInitialState(completed[0].id);
}
});

// Check if Gemini Vision API key is configured
fetch(apiUrl('/api/v1/config/gemini'))
.then((r) => r.json())
.then((d) => setGeminiConfigured(Boolean(d.configured)))
.catch(() => {});
}, []);

// Compute selected video object and URL
const selectedVideo =
videosList.find((v) => v.id === selectedVideoId) ||
(activeSearchResult?.video_id ? videosList.find((v) => v.id === activeSearchResult.video_id) : null) ||
videosList.find((v) => v.status === 'COMPLETED');

const currentVideoUrl = activeSearchResult?.video_url
? apiUrl(activeSearchResult.video_url)
: (selectedVideo ? apiUrl(`/api/v1/videos/${selectedVideo.id}/stream`) : '/videos/input/test_cctv.mp4');

// Retail investigation prompts tailored to shopper and loss-prevention scenarios
const suggestions = [
'Find the customer wearing a red shirt who picked up a mobile phone near Electronics and moved toward the exit.',
'Who entered the Electronics aisle carrying a basket and stayed near the mobile section?',
'Show the customer who approached the front counter and left through the exit gate.',
'Find suspicious behavior around the cosmetics section between 6 PM and 7 PM.',
'Track the person wearing a black jacket near the menswear area.',
];

const extractConceptsFromPrompt = (prompt) => {
const upper = prompt.toUpperCase();
const concepts = [];

if (upper.includes('RED SHIRT') || upper.includes('RED')) concepts.push('PERSON • red shirt');
if (upper.includes('MOBILE') || upper.includes('PHONE')) concepts.push('OBJECT • mobile phone');
if (upper.includes('PICKED UP') || upper.includes('HOLDING') || upper.includes('TOOK')) concepts.push('ACTION • picked up');
if (upper.includes('ELECTRONICS')) concepts.push('LOCATION • Electronics');
if (upper.includes('EXIT') || upper.includes('TOWARD EXIT') || upper.includes('TOWARDS EXIT')) concepts.push('MOVEMENT • toward exit');
if (upper.includes('18:00') || upper.includes('6 PM') || upper.includes('7 PM') || upper.includes('19:00')) concepts.push('TIME • 18:00–19:00');

if (upper.includes('PERSON') || upper.includes('CUSTOMER') || upper.includes('WHO')) concepts.push('PERSON • customer');
if (upper.includes('BAG') || upper.includes('BASKET')) concepts.push('OBJECT • basket');
if (upper.includes('CASHIER') || upper.includes('COUNTER')) concepts.push('LOCATION • checkout');
if (upper.includes('COSMETICS') || upper.includes('MAKEUP')) concepts.push('LOCATION • Cosmetics');
if (upper.includes('SUSPICIOUS') || upper.includes('LOITERING')) concepts.push('EVENT • suspicious behavior');

return concepts.length > 0 ? concepts.slice(0, 6) : ['SEARCHING...'];
};


// Voice Recognition setup
const startVoiceInput = () => {
if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
setQueryText('Find people wearing helmets near the main gate');
return;
}

try {
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.continuous = false;
recognition.interimResults = false;

recognition.onstart = () => setIsListening(true);
recognition.onresult = (event) => {
const transcript = event.results[0][0].transcript;
setQueryText(transcript);
setIsListening(false);
};
recognition.onerror = () => setIsListening(false);
recognition.onend = () => setIsListening(false);

recognition.start();
} catch {
setIsListening(false);
setQueryText('Find people wearing helmets near the main gate');
}
};

// Text-To-Speech execution
const speakText = (text) => {
if ('speechSynthesis' in window) {
window.speechSynthesis.cancel();
const utterance = new SpeechSynthesisUtterance(text);
utterance.rate = 1.0;
utterance.pitch = 1.0;
window.speechSynthesis.speak(utterance);
}
};

// Handle Video File Upload to Backend API
  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }

    // Set immediate visual state for the new video
    setActiveVideoName(file.name);
    setUploadStatus('uploading');
    setUploadProgressMsg(`Uploading ${file.name} to server...`);
    setUploadProgressPct(0);
    setUploadProgressDetails('Transferring video file to backend...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(apiUrl('/api/v1/videos/upload'), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      const data = await response.json();
      const uploadedId = data.video_id;

      setUploadStatus('processing');
      setUploadProgressMsg(`Processing YOLO11 pipeline for ${file.name}...`);
      setUploadProgressPct(1);
      setUploadProgressDetails('Initializing frame detection pipeline...');

      // Unified live progress updater for BOTH polling and SSE
      const updateJobProgress = (prog) => {
        if (!prog) return;

        const frame = prog.frame || 0;
        const total = prog.total || 0;
        const tracks = prog.tracks || 0;
        const detections = prog.detections || 0;
        const rawPct = prog.pct !== undefined ? prog.pct : (total > 0 ? (frame / total) * 100 : 0);
        const pct = Math.max(1, Math.min(100, Math.round(rawPct)));

        setUploadProgressPct(pct);

        if (prog.status === 'COMPLETED') {
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          if (sseRef.current) {
            sseRef.current.close();
            sseRef.current = null;
          }
          setUploadStatus('success');
          setUploadProgressMsg(`✓ ${file.name} ready! Type your query below.`);
          setUploadProgressPct(100);
          setUploadProgressDetails(`All ${total || frame} frames analyzed • ${tracks} tracks • ${detections} detections`);

          fetchVideos().then(() => {
            setSelectedVideoId(uploadedId);
            setActiveVideoName(file.name);
            loadVideoInitialState(uploadedId);
            setTimeout(() => {
              searchInputRef.current?.focus();
            }, 300);
            setTimeout(() => setUploadStatus(null), 6000);
          });
        } else if (prog.status && prog.status.startsWith('FAILED')) {
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          if (sseRef.current) {
            sseRef.current.close();
            sseRef.current = null;
          }
          setUploadStatus('error');
          setUploadProgressMsg(`Processing failed: ${prog.status}`);
          setUploadProgressPct(0);
        } else {
          setUploadProgressMsg(`Processing YOLO11 pipeline for ${file.name}...`);
          if (total > 0) {
            setUploadProgressDetails(
              `Frame ${frame}/${total} (${pct}%) • ${detections} detections • ${tracks} active tracks`
            );
          } else {
            setUploadProgressDetails(
              `Processing frame ${frame}... • ${detections} detections • ${tracks} active tracks`
            );
          }
        }
      };

      // 1. High-frequency live poller every 500ms — ALWAYS guarantees live frame updates!
      pollTimerRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(apiUrl(`/api/v1/jobs/${uploadedId}`));
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            updateJobProgress(statusData);
          }
        } catch (err) {
          console.warn('Poll status error:', err);
        }
      }, 500);

      // 2. Also connect SSE for immediate push events
      try {
        const sseUrl = apiUrl(`/api/v1/jobs/${uploadedId}/progress`);
        const es = new EventSource(sseUrl);
        sseRef.current = es;

        es.onmessage = (event) => {
          try {
            const prog = JSON.parse(event.data);
            updateJobProgress(prog);
          } catch {
            /* ignore malformed SSE message */
          }
        };

        es.onerror = () => {
          // SSE dropped or buffered — polling interval continues seamlessly
          if (sseRef.current) {
            es.close();
            sseRef.current = null;
          }
        };
      } catch {
        // SSE not supported
      }

    } catch (err) {
      console.warn('Upload API error:', err);
      setUploadStatus('error');
      setUploadProgressMsg(`Upload failed: ${err.message || 'Server offline'}`);
    }
  };

// Trigger natural language search flow (Screen 1 -> Screen 2 -> Screen 3 -> Screen 4)
const handlePerformSearch = async (promptToSearch) => {
const prompt = promptToSearch || queryText;
if (!prompt || !prompt.trim()) return;  // don't search empty
setQueryText(prompt);

// Screen 2: AI Understands the User
setCurrentScreen(2);
const dynamicSpeech = `I understand. I’m tracing the person, object, zone, and movement described in your retail investigation.`;
setAiSpeechText(dynamicSpeech);
speakText(dynamicSpeech);

// Dynamically extract concepts from user prompt
const concepts = extractConceptsFromPrompt(prompt);
setExtractedConcepts(concepts);

// Attempt backend REST API search with video_id filter if specific video selected
try {
const searchPayload = { query: prompt };
if (selectedVideoId && selectedVideoId !== 'all') {
searchPayload.video_id = selectedVideoId;
}

const response = await fetch(apiUrl('/api/v1/search'), {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify(searchPayload),
});

        if (response.ok) {
          let resData = await response.json();

          // Fallback: If searching a specific video returned 0 matches, search ALL previously processed videos!
          if ((!resData.results || resData.results.length === 0) && selectedVideoId && selectedVideoId !== 'all') {
            try {
              const globalRes = await fetch(apiUrl('/api/v1/search'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: prompt }),
              });
              if (globalRes.ok) {
                const globalData = await globalRes.json();
                if (globalData.results && globalData.results.length > 0) {
                  resData = globalData;
                }
              }
            } catch {
              /* ignore fallback error */
            }
          }

          if (resData.results && resData.results.length > 0) {
            setSearchResultsList(resData.results);
            setCurrentResultIdx(0);
            setActiveSearchResult(resData.results[0]);
            if (resData.results[0].video_id) {
              setSelectedVideoId(resData.results[0].video_id);
              setActiveVideoName(resData.results[0].video_filename);
            }
            const foundSpeech = `Found ${resData.results.length} detection${resData.results.length > 1 ? 's' : ''} matching ${prompt}. Displaying evidence.`;
            setAiSpeechText(foundSpeech);
          } else {
            // No detections found matching the query
            const currentVid = videosList.find((v) => v.id === selectedVideoId) || videosList[0];
            setSearchResultsList([]);
            if (currentVid) {
              setActiveSearchResult({
                video_id: currentVid.id,
                video_filename: currentVid.filename,
                video_url: `/api/v1/videos/${currentVid.id}/stream`,
                class_name: 'NO MATCH',
                confidence: 0.0,
                start_time_sec: 0,
                end_time_sec: currentVid.duration_sec || 10,
                event_type: 'NO_MATCH',
                details: `0 detections matched "${prompt}" in ${currentVid.filename}`,
                trajectory: [],
                is_no_match: true,
              });
              const noMatchSpeech = `I could not find any events matching ${prompt} in the active footage. Showing raw video stream.`;
              setAiSpeechText(noMatchSpeech);
            }
          }
        }
} catch {
// Backend fallback if server is offline
}

// Transition to Screen 3 (Camera Universe Search)
setIsSearching(true);
setTimeout(() => {
setCurrentScreen(3);
}, 2400);
};

// Handle match transition from Camera Universe -> Screen 4 (Evidence Experience)
const handleUniverseTransition = () => {
setIsSearching(false);
setCurrentScreen(4);
};

const handleNextMatch = () => {
if (searchResultsList.length > 0) {
const nextIdx = (currentResultIdx + 1) % searchResultsList.length;
setCurrentResultIdx(nextIdx);
setActiveSearchResult(searchResultsList[nextIdx]);
}
};

// Navigation handlers
const handleNextStep = () => {
if (currentScreen < 8) {
if (currentScreen === 1) handlePerformSearch(queryText);
else setCurrentScreen(currentScreen + 1);
}
};

const handlePrevStep = () => {
if (currentScreen > 1) setCurrentScreen(currentScreen - 1);
};

return (
<div className="app-main-viewport">
{/* Top Ambient Branding Header */}
<header className="ambient-header">
<div className="brand-group">
<div className="brand-orb-mini"></div>
<span className="brand-title">RETAILVISION</span>
<span className="brand-badge mono">STORE 01 • SYSTEM ONLINE</span>
</div>

<div className="header-actions-right">
{/* Gemini Vision API Key Button */}
<button
onClick={() => setIsGeminiModalOpen(true)}
className="gemini-header-btn mono"
style={{
background: geminiConfigured ? 'rgba(16, 185, 129, 0.15)' : 'rgba(6, 182, 212, 0.12)',
border: `1px solid ${geminiConfigured ? 'rgba(16, 185, 129, 0.4)' : 'rgba(6, 182, 212, 0.35)'}`,
color: geminiConfigured ? '#34d399' : '#22d3ee',
borderRadius: '8px',
padding: '6px 12px',
display: 'flex',
alignItems: 'center',
gap: '6px',
fontSize: '11px',
fontWeight: 700,
cursor: 'pointer',
transition: 'all 0.2s ease',
}}
title="Configure Gemini Vision API key for accurate person detection"
>
<Sparkles size={13} />
<span>{geminiConfigured ? 'GEMINI VISION: ACTIVE' : 'CONNECT GEMINI KEY'}</span>
</button>

{/* Quick Header Upload Button */}
<label className="header-upload-btn mono" title="Upload CCTV Video MP4">
<Upload size={14} />
<span>UPLOAD VIDEO</span>
<input
type="file"
accept="video/mp4,video/mkv,video/avi"
style={{ display: 'none' }}
onChange={handleFileUpload}
/>
</label>

<div className="system-live-status">
<span className="live-indicator-dot"></span>
<span className="mono status-text">
{selectedVideo ? `${selectedVideo.filename.length > 20 ? selectedVideo.filename.slice(0, 18) + '...' : selectedVideo.filename} (ONLINE)` : `${videosList.filter((v) => v.status === 'COMPLETED').length || 16} CAMERAS ONLINE`}
</span>
</div>
</div>
</header>

{/* Screen Render Engine */}
<main className="fluid-stage-canvas">
{/* SCREEN 1 & 2: MEET ASK & AI UNDERSTANDS THE USER */}
{currentScreen <= 2 && (
<div className="retail-command-center animated-fade-in">
<aside className="investigation-sidebar">
<div className="sidebar-brand" onClick={() => setCurrentScreen(1)} style={{ cursor: 'pointer' }}>
                <div className="brand-mark" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #0891b2, #3b82f6)', borderRadius: '10px', boxShadow: '0 0 15px rgba(6,182,212,0.4)', width: '36px', height: '36px' }}>
                  <ShieldCheck size={20} color="#fff" />
                </div>
                <div>
                  <div className="sidebar-title" style={{ letterSpacing: '0.5px', fontWeight: 'bold' }}>RetailVision</div>
                  <div className="sidebar-subtitle mono" style={{ color: '#06b6d4', fontSize: '10px' }}>AI COMMAND CENTER</div>
                </div>
              </div>

<nav className="nav-stack">
                <button
                  className={`nav-item ${currentScreen === 1 ? 'active' : ''}`}
                  onClick={() => setCurrentScreen(1)}
                >
                  <Search size={16} className="nav-icon" />
                  <span>Investigate</span>
                </button>
                <button
                  className={`nav-item ${currentScreen === 5 ? 'active' : ''}`}
                  onClick={() => setCurrentScreen(5)}
                >
                  <Video size={16} className="nav-icon" />
                  <span>Live Cameras</span>
                </button>
                <button
                  className={`nav-item ${currentScreen === 4 ? 'active' : ''}`}
                  onClick={() => setCurrentScreen(4)}
                >
                  <ShieldAlert size={16} className="nav-icon" />
                  <span>Evidence Cases</span>
                </button>
                <button
                  className={`nav-item ${currentScreen === 6 ? 'active' : ''}`}
                  onClick={() => setCurrentScreen(6)}
                >
                  <Footprints size={16} className="nav-icon" />
                  <span>Store Journey</span>
                </button>
                  <button
                    className={`nav-item ${currentScreen === 8 ? 'active alert-nav-item' : ''}`}
                    onClick={() => setCurrentScreen(8)}
                    style={{ 
                      borderColor: currentScreen === 8 ? 'rgba(239,68,68,0.8)' : 'rgba(239,68,68,0.3)',
                      background: currentScreen === 8 ? 'rgba(239,68,68,0.2)' : 'rgba(239,68,68,0.06)',
                      marginTop: '4px'
                    }}
                  >
                    <PhoneCall size={16} className="nav-icon" style={{ color: '#f87171' }} />
                    <span style={{ color: '#fca5a5', fontWeight: 700 }}>Call Agent</span>
                    <span className="badge-new-feature">AI CALL</span>
                  </button>
              </nav>

<div className="sidebar-case-card">
<div className="mono case-label">ACTIVE CASE</div>
<div className="case-title">INV-0247</div>
<div className="case-meta">Possible product interaction</div>
<div className="case-tag">Evidence found</div>
</div>
</aside>

<section className="investigation-main-panel">
{currentScreen === 1 && (
<div className="ask-home-content animated-slide-up">
<div className="retail-header-row">
<div>
<div className="mono retail-eyebrow">INVESTIGATION WORKSPACE</div>
<h1 className="ask-hero-heading">What are you looking for?</h1>
</div>
<div className="status-chip mono">Store 01 • Live</div>
</div>

{uploadStatus && (
<div className={`upload-status-toast ${uploadStatus} animated-pop`} style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '6px', minWidth: '340px' }}>
<div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
{uploadStatus === 'uploading' || uploadStatus === 'processing' ? (
<Loader2 size={16} className="spin-icon text-cyan" />
) : uploadStatus === 'success' ? (
<CheckCircle2 size={16} className="text-emerald" />
) : (
<AlertCircle size={16} className="text-red" />
)}
<span className="mono" style={{ flex: 1 }}>{uploadProgressMsg}</span>
{uploadStatus === 'processing' && (
<span className="mono" style={{ color: '#06b6d4', fontSize: '11px', fontWeight: 'bold' }}>
{uploadProgressPct.toFixed(0)}%
</span>
)}
</div>
{uploadStatus === 'processing' && (
<div style={{ width: '100%', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', height: '4px', overflow: 'hidden' }}>
<div style={{ width: `${uploadProgressPct}%`, height: '100%', background: 'linear-gradient(90deg, #0891b2, #06b6d4, #22d3ee)', borderRadius: '4px', transition: 'width 0.5s ease', boxShadow: '0 0 8px rgba(6,182,212,0.6)' }} />
</div>
)}
{uploadProgressDetails && (
<span className="mono" style={{ fontSize: '10px', color: 'rgba(148,163,184,0.8)' }}>{uploadProgressDetails}</span>
)}
</div>
)}

<div className="conversational-input-card">
<button className={`mic-trigger-btn ${isListening ? 'listening' : ''}`} onClick={startVoiceInput} title="Voice input (Speak naturally)">
{isListening ? <MicOff size={20} className="pulse-icon" /> : <Mic size={20} />}
</button>

<input
ref={searchInputRef}
type="text"
className="conversational-text-input"
placeholder="Describe the incident or person you're looking for..."
value={queryText}
onChange={(e) => setQueryText(e.target.value)}
onKeyDown={(e) => e.key === 'Enter' && queryText.trim() && handlePerformSearch()}
/>

<div className="input-filter-actions">
{videosList && videosList.length > 0 && (
<select
value={selectedVideoId}
onChange={(e) => handleVideoSelect(e.target.value)}
className="video-select-chip mono"
style={{
background: 'rgba(15, 23, 42, 0.85)',
color: '#38bdf8',
border: '1px solid rgba(56, 189, 248, 0.35)',
borderRadius: '8px',
padding: '7px 12px',
fontSize: '0.78rem',
fontWeight: '600',
outline: 'none',
cursor: 'pointer',
boxShadow: '0 0 12px rgba(56, 189, 248, 0.15)',
transition: 'all 0.2s ease',
maxWidth: '200px',
}}
title="Choose a previously processed CCTV video to search in"
>
<option value="all" style={{ background: '#0f172a', color: '#e2e8f0' }}>🌐 All Processed Videos</option>
{videosList.map((vid) => (
<option key={vid.id} value={vid.id} style={{ background: '#0f172a', color: '#e2e8f0' }}>
🎥 {vid.filename} {vid.status === 'COMPLETED' ? '✅' : '⏳'}
</option>
))}
</select>
)}

<label className="upload-inline-chip mono" title="Upload new CCTV footage file">
<FileVideo size={14} className="chip-icon" />
<span>UPLOAD</span>
<input type="file" accept="video/mp4,video/mkv,video/avi" style={{ display: 'none' }} onChange={handleFileUpload} />
</label>

<button className="ask-submit-btn" onClick={() => handlePerformSearch()}>
<Sparkles size={16} />
<span>INVESTIGATE</span>
</button>
</div>
</div>

<div className="query-helper-row">
<div className="helper-tag mono">PERSON • red shirt</div>
<div className="helper-tag mono">OBJECT • mobile phone</div>
<div className="helper-tag mono">LOCATION • Electronics</div>
<div className="helper-tag mono">MOVEMENT • toward exit</div>
</div>

<div className="conversation-suggestions-wrapper">
<div className="suggestions-label mono">EXAMPLE INVESTIGATIONS</div>
<div className="suggestions-pills-row">
{suggestions.map((item, idx) => (
<button key={idx} className="suggestion-pill" onClick={() => handlePerformSearch(item)}>
<Sparkles size={12} className="pill-icon" />
<span>{item}</span>
</button>
))}
</div>
</div>
</div>
)}

{currentScreen === 2 && (
<div className="screen-understanding-content animated-pop">
<div className="retail-header-row compact-row">
<div>
<div className="mono retail-eyebrow">INVESTIGATION ANALYSIS</div>
<h2 className="ask-hero-heading small-heading">Your investigation</h2>
</div>
</div>

<div className="ai-speech-response-box">
<Volume2 size={20} className="speech-icon" />
<div className="ai-speech-text">"{aiSpeechText}"</div>
</div>

<div className="investigation-chips-panel">
<div className="concept-extracted-title mono">MATCHED CONDITIONS</div>
<div className="concept-chips-row">
{extractedConcepts.map((concept, idx) => (
<div key={idx} className="concept-chip-glow animated-bounce" style={{ animationDelay: `${idx * 0.2}s` }}>
<span className="dot-spark"></span>
<span className="mono">{concept}</span>
</div>
))}
</div>
</div>

<div className="universe-transition-loader mono">
<span className="spin-loader"></span>
<span>SEARCHING STORE VIDEO FEED...</span>
</div>
</div>
)}
</section>

<aside className="investigation-right-panel">
<div className="right-panel-card summary-card">
<div className="mono panel-label">QUERY</div>
<div className="query-summary">{queryText}</div>
</div>

<div className="right-panel-card match-card">
<div className="mono panel-label">MATCH</div>
<div className="match-score-row">
<span className="match-score">91%</span>
<span className="match-state">Evidence found</span>
</div>
</div>

<div className="right-panel-card">
<div className="mono panel-label">WHY THIS MATCHED</div>
<div className="match-breakdown-list">
<div className="match-breakdown-item"><span className="match-breakdown-check"><Check size={11} strokeWidth={3} /></span> Red shirt</div>
<div className="match-breakdown-item"><span className="match-breakdown-check"><Check size={11} strokeWidth={3} /></span> Mobile phone</div>
<div className="match-breakdown-item"><span className="match-breakdown-check"><Check size={11} strokeWidth={3} /></span> Electronics zone</div>
<div className="match-breakdown-item"><span className="match-breakdown-check"><Check size={11} strokeWidth={3} /></span> Product interaction</div>
<div className="match-breakdown-item"><span className="match-breakdown-check"><Check size={11} strokeWidth={3} /></span> Movement toward exit</div>
</div>
</div>

<div className="right-panel-card">
<div className="mono panel-label">PERSON</div>
<div className="person-record">
<div className="person-id">P07</div>
<div className="person-meta">First seen 18:13:52</div>
<div className="person-meta">Last seen 18:15:41</div>
<div className="person-journey-path mono">Entrance → Electronics → Exit</div>
</div>
</div>

<div className="right-panel-card timeline-mini">
<div className="mono panel-label">EVENT TIMELINE</div>
<div className="mini-timeline">
<div><span>18:13:52</span> Entered Electronics</div>
<div><span>18:14:22</span> Approached mobile section</div>
<div><span>18:14:35</span> Product interaction</div>
<div><span>18:15:03</span> Moved toward exit</div>
</div>
</div>
</aside>
</div>
)}

{/* SCREEN 3: THE CAMERA UNIVERSE & MAGICAL TRANSITION */}
{currentScreen === 3 && (
<div className="screen-universe-view animated-fade-in">
<CameraUniverse
isSearching={isSearching}
activeSearchResult={activeSearchResult}
videosList={videosList}
onTransitionComplete={handleUniverseTransition}
/>
</div>
)}

{/* SCREEN 4 & 5: CCTV EVIDENCE EXPERIENCE & AI EXPLAINS WHAT IT FOUND */}
{(currentScreen === 4 || currentScreen === 5) && (
<div className="screen-evidence-view animated-slide-up">
<EvidenceViewer
searchResult={activeSearchResult}
selectedVideoId={selectedVideoId}
videosList={videosList}
onSelectVideo={handleVideoSelect}
currentVideoUrl={currentVideoUrl}
cameraCode={selectedVideo ? `CAM_${selectedVideo.id.slice(0, 4).toUpperCase()}` : "CAM_01"}
cameraName={activeSearchResult?.video_filename || selectedVideo?.filename || "SURVEILLANCE STREAM"}
timestampStr={activeSearchResult?.start_time_sec !== undefined ? `${Math.floor(activeSearchResult.start_time_sec / 60).toString().padStart(2, '0')}:${Math.floor(activeSearchResult.start_time_sec % 60).toString().padStart(2, '0')}` : "00:00"}
confidence={activeSearchResult?.confidence ? Math.round(activeSearchResult.confidence * 1000) / 10 : 96.4}
targetClass={activeSearchResult?.class_name ? activeSearchResult.class_name.toUpperCase() : (extractedConcepts.join(' + ') || 'OBJECT')}
matchCount={searchResultsList.length || (activeSearchResult ? 1 : 0)}
onTrackPerson={() => setCurrentScreen(6)}
onCallSecurity={() => setCurrentScreen(8)}
onNextMatch={handleNextMatch}
queryText={queryText}
searchResultsList={searchResultsList}
/>
</div>
)}

{/* SCREEN 6: PERSON JOURNEY (SPATIAL MULTI-CAMERA RECONSTRUCTION) */}
{currentScreen === 6 && (
<div className="screen-journey-view animated-slide-up">
<PersonJourney
targetClass={extractedConcepts.join(' ') || activeSearchResult?.class_name || 'PERSON'}
activeSearchResult={activeSearchResult}
currentVideoUrl={currentVideoUrl}
onSelectCheckpoint={(chk) => console.log('Selected checkpoint', chk)}
onCallSecurity={() => setCurrentScreen(8)}
/>
</div>
)}

{/* SCREEN 7: NATURAL AI CONVERSATION & CONTEXT WORKSPACE */}
{currentScreen === 7 && (
<div className="screen-conversation-view animated-slide-up">
<div className="conversation-workspace">
<div className="convo-header">
<div className="convo-title-group">
<div className="ai-orb-mini"></div>
<div>
<h2 className="convo-title">CONTINUOUS INVESTIGATION CONVERSATION</h2>
<div className="convo-subtitle">Context: Target #{activeSearchResult?.track_id || 884} • {extractedConcepts.join(', ') || activeSearchResult?.class_name || 'CCTV'} Detection</div>
</div>
</div>
</div>

{/* Chat Stream View */}
<div className="convo-chat-stream">
{conversationHistory.map((item, idx) => (
<div key={idx} className={`convo-bubble-row ${item.sender === 'ASK' ? 'ask-row' : 'user-row'}`}>
<div className="convo-sender-badge mono">{item.sender}</div>
<div className="convo-bubble-body">{item.text}</div>
</div>
))}
</div>

{/* Dynamic Follow-up Prompt Chips */}
<div className="followup-prompts-bar">
<span className="mono prompt-label">SUGGESTED FOLLOW-UPS:</span>
<div className="prompt-chips">
<button
className="prompt-chip"
onClick={() => {
setConversationHistory((prev) => [
...prev,
{ sender: 'USER', text: 'Where did this person go next?' },
{ sender: 'ASK', text: `Target #${activeSearchResult?.track_id || 884} moved across camera viewpoints in ${selectedVideo?.filename || 'the facility'}.` },
]);
setCurrentScreen(6);
}}
>
"Where did this person go next?"
</button>

<button
className="prompt-chip"
onClick={() => {
setConversationHistory((prev) => [
...prev,
{ sender: 'USER', text: 'Was this person carrying anything?' },
{ sender: 'ASK', text: 'AI Object Analysis confirms target motion pattern and spatial vector signatures.' },
]);
}}
>
"Was this person carrying anything?"
</button>

<button
className="prompt-chip alert-chip"
onClick={() => setCurrentScreen(8)}
>
"Call security and explain what happened."
</button>
</div>
</div>
</div>
</div>
)}

{/* SCREEN 8: AI CALLING ASSISTANT (LIVE SECURITY DISPATCH) */}
{currentScreen === 8 && (
<SecurityCallAssistant
activeSearchResult={activeSearchResult}
currentVideoUrl={currentVideoUrl}
onCloseCall={() => setCurrentScreen(4)}
onNavigateToJourney={() => setCurrentScreen(6)}
/>
)}
</main>

{/* Floating Glass Navigation Dock */}
<FloatingDock
activeScreen={currentScreen}
onNavigate={(screenId) => setCurrentScreen(screenId)}
onPrevStep={handlePrevStep}
onNextStep={handleNextStep}
totalScreens={8}
/>

{/* Gemini Vision API Key Configuration Modal */}
<GeminiKeyModal
isOpen={isGeminiModalOpen}
onClose={() => setIsGeminiModalOpen(false)}
onKeySaved={(cfg) => setGeminiConfigured(cfg)}
/>
</div>
);
}

export default App;
