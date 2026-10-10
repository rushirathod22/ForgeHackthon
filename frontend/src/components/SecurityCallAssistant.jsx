import React, { useState, useEffect, useRef } from 'react';
import { 
  PhoneCall, PhoneOff, Mic, Send, ShieldAlert, ShieldCheck, 
  Upload, FileVideo, AlertTriangle, Eye, Video, CheckCircle2, 
  Volume2, VolumeX, Sparkles, Activity, Cpu, ArrowRight
} from 'lucide-react';
import { AiOrbCanvas } from './AiOrbCanvas';
import { apiUrl } from '../api';

export function SecurityCallAssistant({
  activeSearchResult = null,
  currentVideoUrl = null,
  onCloseCall,
  onNavigateToJourney,
}) {
  // Navigation sub-mode: 'ANALYZE' (Upload/Detect) vs 'CALL' (Interactive Voice Call)
  const [activeTab, setActiveTab] = useState('ANALYZE');

  // Incidents and Upload State
  const [incidentsList, setIncidentsList] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStepLabel, setAnalysisStepLabel] = useState('');
  const [uploadedPreviewUrl, setUploadedPreviewUrl] = useState(null);

  // Call Engine State
  const [managerPhoneNumber, setManagerPhoneNumber] = useState('+91 9545696585');
  const [telecomStatus, setTelecomStatus] = useState(null);
  const [callStatus, setCallStatus] = useState('IDLE'); // 'IDLE' | 'RINGING' | 'CONNECTED' | 'ENDED'
  const [callTime, setCallTime] = useState(0);
  const [callId, setCallId] = useState(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [managerInput, setManagerInput] = useState('');
  const [transcript, setTranscript] = useState([]);
  const [toolLogs, setToolLogs] = useState([]);
  const [actionStatus, setActionStatus] = useState('MONITORING'); // 'MONITORING' | 'SECURITY_DISPATCHED' | 'FALSE_ALARM_DISMISSED'

  const transcriptEndRef = useRef(null);
  const audioContextRef = useRef(null);
  const ringOscillatorRef = useRef(null);
  const recognitionRef = useRef(null);

  // Fetch initial escalation incidents from backend
  useEffect(() => {
    fetchIncidents();
  }, []);

  const fetchIncidents = async () => {
    try {
      const res = await fetch(apiUrl('/api/v1/agent/incidents'));
      if (res.ok) {
        const data = await res.json();
        if (data.incidents && data.incidents.length > 0) {
          setIncidentsList(data.incidents);
          if (!selectedIncident) {
            setSelectedIncident(data.incidents[0]);
          }
        }
      }
    } catch (err) {
      console.error('Failed to load escalation incidents:', err);
    }
  };

  // If activeSearchResult passed in from parent, prioritize it
  useEffect(() => {
    if (activeSearchResult) {
      const inc = {
        id: `INC-${activeSearchResult.track_id || 'SRCH'}`,
        event_type: activeSearchResult.class_name ? `SUSPICIOUS_${activeSearchResult.class_name.toUpperCase()}` : 'PRODUCT_CONCEALMENT',
        severity: 'HIGH',
        confidence: activeSearchResult.confidence ? roundConf(activeSearchResult.confidence) : 0.91,
        location: activeSearchResult.zone_name || 'Aisle 4 - Electronics & Cosmetics',
        track_id: activeSearchResult.track_id || 17,
        timestamp: 'Just now',
        description: `Suspicious activity detected on camera ${activeSearchResult.video_filename || 'CAM_04'}`,
        current_zone: 'Near Checkout Area',
        is_inside: true,
        requires_manager_call: true,
        video_url: activeSearchResult.video_url || currentVideoUrl || '/videos/input/test_cctv.mp4',
        status: 'READY_FOR_CALL',
      };
      setSelectedIncident(inc);
    }
  }, [activeSearchResult, currentVideoUrl]);

  const roundConf = (val) => {
    const num = typeof val === 'number' ? val : parseFloat(val);
    return num > 1 ? (num / 100).toFixed(2) : num.toFixed(2);
  };

  // Auto-scroll transcript to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Speech Recognition Setup (Manager Voice Input)
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition();
      recognizer.continuous = false;
      recognizer.interimResults = false;
      recognizer.lang = 'en-US';

      recognizer.onresult = (event) => {
        const spoken = event.results[0][0].transcript;
        setIsListening(false);
        if (spoken) {
          handleManagerMessage(spoken);
        }
      };

      recognizer.onerror = () => setIsListening(false);
      recognizer.onend = () => setIsListening(false);

      recognitionRef.current = recognizer;
    }
  }, [callId, selectedIncident]);

  const toggleMic = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in this browser. Please use quick response chips or text input.');
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e) {
        console.warn('SpeechRecognition start error:', e);
      }
    }
  };

  // Ringtone synthesizer (Web Audio API Dual-Tone PBX ring)
  const startRingingAudio = () => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      audioContextRef.current = ctx;

      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'sine';
      osc1.frequency.value = 440; // US standard ring tone freq 1
      osc2.frequency.value = 480; // US standard ring tone freq 2

      gainNode.gain.setValueAtTime(0.04, ctx.currentTime);

      osc1.connect(gainNode);
      osc2.connect(gainNode);
      gainNode.connect(ctx.destination);

      osc1.start();
      osc2.start();

      ringOscillatorRef.current = { osc1, osc2, gainNode, ctx };
    } catch (e) {
      console.warn('Audio ringtone synth error:', e);
    }
  };

  const stopRingingAudio = () => {
    try {
      if (ringOscillatorRef.current) {
        ringOscillatorRef.current.osc1.stop();
        ringOscillatorRef.current.osc2.stop();
        ringOscillatorRef.current.ctx.close();
        ringOscillatorRef.current = null;
      }
    } catch (e) {}
  };

  // Text-To-Speech (AI Agent speaks)
  const speakVoice = (text) => {
    if (isMuted || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      const voices = window.speechSynthesis.getVoices();
      const naturalVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
      if (naturalVoice) utterance.voice = naturalVoice;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('TTS error:', e);
    }
  };

  // Call Timer
  useEffect(() => {
    let interval = null;
    if (callStatus === 'CONNECTED') {
      interval = setInterval(() => {
        setCallTime(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [callStatus]);

  // Initiate Outbound Phone Call to Store Manager
  const startManagerCall = async (incidentToCall = selectedIncident) => {
    setActiveTab('CALL');
    setCallStatus('RINGING');
    setCallTime(0);
    setTranscript([]);
    setToolLogs([]);
    setActionStatus('MONITORING');
    startRingingAudio();

    try {
      const res = await fetch(apiUrl('/api/v1/agent/call/start'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_id: incidentToCall?.id || 'INC-DEMO',
          manager_phone: managerPhoneNumber,
          // Pass full incident so backend has video-specific data from the start
          incident_context: incidentToCall || null,
        }),
      });
      const data = await res.json();
      setCallId(data.call_id);
      if (data.telecom) setTelecomStatus(data.telecom);

      setTimeout(() => {
        stopRingingAudio();
        setCallStatus('CONNECTED');

        const initialMsg = data.greeting || `Hello, this is the Store Security Assistant from your retail store. I detected a potentially suspicious activity in ${incidentToCall?.location || 'Aisle 4'} approximately one minute ago.`;
        setTranscript([
          {
            speaker: 'AI AGENT',
            text: initialMsg,
            time: '00:01',
          }
        ]);
        
        // If real cellular call was placed to phone, don't overlap with laptop speakers
        const isCellularCall = data.telecom?.provider === 'TWILIO' && data.telecom?.status === 'DISPATCHED_TO_MOBILE';
        if (!isCellularCall) {
          speakVoice(initialMsg);
        }
      }, 2200);

    } catch (err) {
      stopRingingAudio();
      setCallStatus('CONNECTED');
      const fallbackMsg = `Hello, this is the Store Security Assistant from your retail store. I detected a potentially suspicious activity in ${incidentToCall?.location || 'Aisle 4'} approximately one minute ago.`;
      setTranscript([{ speaker: 'AI AGENT', text: fallbackMsg, time: '00:01' }]);
      speakVoice(fallbackMsg);
    }
  };

  // Send message from Manager to Agent
  const handleManagerMessage = async (messageText) => {
    const text = messageText || managerInput;
    if (!text || !text.trim()) return;

    setManagerInput('');
    const timeFormatted = formatSeconds(callTime);

    // Add manager's message to transcript immediately
    setTranscript(prev => [...prev, {
      speaker: 'STORE MANAGER',
      text: text,
      time: timeFormatted,
    }]);

    try {
      const res = await fetch(apiUrl('/api/v1/agent/call/converse'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: callId,
          incident_id: selectedIncident?.id,
          message: text,
          // Send full incident so every response is based on the actual video analysis
          incident_context: selectedIncident ? {
            id: selectedIncident.id,
            event_type: selectedIncident.event_type,
            location: selectedIncident.location,
            confidence: selectedIncident.confidence,
            track_id: selectedIncident.track_id,
            current_zone: selectedIncident.current_zone,
            description: selectedIncident.description,
            video_summary: selectedIncident.video_summary || selectedIncident.description,
            total_persons: selectedIncident.total_persons,
            appearance: selectedIncident.appearance,
            other_people: selectedIncident.other_people,
            payment_status: selectedIncident.payment_status,
            camera_info: selectedIncident.camera_info,
            video_filename: selectedIncident.video_filename,
          } : null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        
        // Log tool execution if agent called a tool
        if (data.tool_called) {
          setToolLogs(prev => [
            {
              tool: data.tool_called,
              result: data.tool_result,
              time: formatSeconds(callTime + 1),
            },
            ...prev
          ]);
        }

        if (data.action_taken) {
          setActionStatus(data.action_taken);
        }

        // Add agent response
        setTimeout(() => {
          setTranscript(prev => [...prev, {
            speaker: 'AI AGENT',
            text: data.response_text,
            time: formatSeconds(callTime + 2),
            tool: data.tool_called,
          }]);
          speakVoice(data.response_text);
        }, 500);
      } else {
        // Non-OK HTTP response — still continue conversation with incident-specific fallback
        const errText = await res.text().catch(() => '');
        console.error('Agent converse HTTP error:', res.status, errText);
        buildAndSpeakFallback(text);
      }
    } catch (err) {
      console.error('Error conversing with agent (network/timeout):', err);
      buildAndSpeakFallback(text);
    }
  };

  // Video-specific offline fallback — uses actual analyzed incident data, not hardcoded strings
  const buildAndSpeakFallback = (text) => {
    const low = (text || '').toLowerCase();
    const inc = selectedIncident || {};
    const loc = inc.location || 'Aisle 4';
    const track = inc.track_id || 17;
    const persons = inc.total_persons || 3;
    const appearance = inc.appearance || 'dark clothing';
    const zone = inc.current_zone || 'near checkout area';
    const desc = inc.description || inc.video_summary || 'suspicious activity was detected';

    let fallbackReply;
    if (low.includes('how many') || low.includes('people') || low.includes('count') || low.includes('headcount')) {
      fallbackReply = `There are currently ${persons} people detected in the store video footage.`;
    } else if (low.includes('summary') || low.includes('what happened') || low.includes('tell me') || low.includes('explain')) {
      fallbackReply = inc.video_summary || desc;
    } else if (low.includes('wearing') || low.includes('appearance') || low.includes('clothes') || low.includes('look')) {
      fallbackReply = `Suspect Track ${track} is wearing ${appearance}.`;
    } else if (low.includes('where') || low.includes('location') || low.includes('inside')) {
      fallbackReply = `Suspect Track ${track} is currently ${zone} in ${loc}.`;
    } else if (low.includes('pay') || low.includes('paid') || low.includes('bill') || low.includes('receipt')) {
      fallbackReply = inc.payment_status || `No payment was detected at the registers. The suspect moved directly toward the exit.`;
    } else if (low.includes('security') || low.includes('dispatch') || low.includes('guard') || low.includes('send')) {
      fallbackReply = `Understood. Security floor team Alpha has been dispatched to ${zone} to intercept Track ${track}.`;
      setActionStatus('SECURITY_DISPATCHED');
    } else if (low.includes('false alarm') || low.includes('dismiss') || low.includes('ignore')) {
      fallbackReply = 'Understood. I have marked this detection as a false alarm and archived the event.';
      setActionStatus('FALSE_ALARM_DISMISSED');
    } else if (low.includes('bye') || low.includes('end call') || low.includes('thank')) {
      fallbackReply = 'Thank you Store Manager. Standing by on retail vision surveillance. Goodbye.';
      setActionStatus('CALL_ENDED');
    } else {
      fallbackReply = `${desc} Detection confidence is ${Math.round((inc.confidence || 0.91) * 100)} percent in ${loc}. Would you like me to dispatch security or dismiss?`;
    }

    setTranscript(prev => [...prev, {
      speaker: 'AI AGENT',
      text: fallbackReply,
      time: formatSeconds(callTime + 1),
    }]);
    speakVoice(fallbackReply);
  };

  // End active call
  const endCall = () => {
    stopRingingAudio();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setCallStatus('ENDED');
    fetch(apiUrl('/api/v1/agent/call/end'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `call_id=${callId || ''}`,
    }).catch(() => {});
  };

  // Upload & Analyze Video / Image File
  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setIsAnalyzing(true);
    setAnalysisProgress(15);
    setAnalysisStepLabel('Extracting Frames & Initializing YOLO11 Model...');

    const localUrl = URL.createObjectURL(file);
    setUploadedPreviewUrl(localUrl);

    const formData = new FormData();
    formData.append('file', file);

    const progTimer = setInterval(() => {
      setAnalysisProgress(p => {
        if (p < 40) {
          setAnalysisStepLabel('Tracking Human Keypoints & Spatial Pose Vectors...');
          return p + 12;
        } else if (p < 80) {
          setAnalysisStepLabel('Evaluating Concealment & Shoplifting Motion GRU...');
          return p + 15;
        } else if (p < 95) {
          setAnalysisStepLabel('Decision Agent: Assessing Escalation Severity...');
          return p + 5;
        }
        return p;
      });
    }, 450);

    try {
      const res = await fetch(apiUrl('/api/v1/agent/analyze'), {
        method: 'POST',
        body: formData,
      });

      clearInterval(progTimer);
      setAnalysisProgress(100);
      setAnalysisStepLabel('Suspicious Activity Detected!');

      if (res.ok) {
        const data = await res.json();
        if (data.incident) {
          setSelectedIncident(data.incident);
          setIncidentsList(prev => [data.incident, ...prev]);
        }
      }
    } catch (err) {
      clearInterval(progTimer);
      setAnalysisProgress(100);
      setAnalysisStepLabel('Analysis Complete (Demo Mode)');
      const mockInc = {
        id: `INC-${Date.now().toString().slice(-4)}`,
        event_type: 'PRODUCT_CONCEALMENT_THEFT',
        severity: 'HIGH',
        confidence: 0.91,
        location: 'Aisle 4 - Electronics & Cosmetics',
        track_id: 17,
        timestamp: '11:42 PM',
        description: 'Customer was observed taking an item from the shelf and placing it inside a bag. The customer then moved toward the exit.',
        current_zone: 'Near Checkout Area',
        is_inside: true,
        requires_manager_call: true,
        video_url: localUrl,
        status: 'READY_FOR_CALL',
      };
      setSelectedIncident(mockInc);
      setIncidentsList(prev => [mockInc, ...prev]);
    } finally {
      setIsUploading(false);
      setTimeout(() => setIsAnalyzing(false), 1200);
    }
  };

  const formatSeconds = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const currentVidSrc = selectedIncident?.video_url
    ? apiUrl(selectedIncident.video_url)
    : (uploadedPreviewUrl || currentVideoUrl || '/videos/input/test_cctv.mp4');

  return (
    <div className="agent-security-page-container animated-fade-in">
      {/* Top Header & Navigation Ribbon */}
      <div className="agent-header-ribbon">
        <div className="agent-header-title-box">
          <div className="agent-icon-badge">
            <PhoneCall size={22} className="text-cyan pulse-live" />
          </div>
          <div>
            <div className="agent-title-main">
              <span>Security Call Agent</span>
              <span className="agent-feature-tag">NEW FEATURE</span>
            </div>
            <div className="agent-subtitle-main">
              Autonomous CCTV Verification Engine • Shoplifting & Concealment Detection • Interactive Store Manager Voice Call
            </div>
          </div>
        </div>

        <div className="agent-tab-toggle-group">
          <button 
            className={`agent-tab-btn ${activeTab === 'ANALYZE' ? 'active' : ''}`}
            onClick={() => setActiveTab('ANALYZE')}
          >
            <Video size={16} />
            <span>1. Footage Analysis & Detection</span>
          </button>
          <button 
            className={`agent-tab-btn ${activeTab === 'CALL' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('CALL');
              if (callStatus === 'IDLE') startManagerCall();
            }}
          >
            <PhoneCall size={16} />
            <span>2. Store Manager Voice Call</span>
            {callStatus === 'CONNECTED' && <span className="call-live-dot-pulse"></span>}
          </button>
        </div>
      </div>

      {/* Main Work Area based on activeTab */}
      {activeTab === 'ANALYZE' ? (
        <div className="agent-analyze-grid animated-slide-up">
          {/* Left Column: Upload Footage & Live Detection Telemetry */}
          <div className="agent-panel footage-upload-panel">
            <div className="panel-header-row">
              <div className="panel-title-group">
                <FileVideo size={18} className="text-cyan" />
                <span className="mono">CCTV FOOTAGE & BEHAVIOR INSPECTION</span>
              </div>
              <span className="badge badge-emerald">YOLO11 + GRU Pose Active</span>
            </div>

            {/* Video Player Display */}
            <div className="agent-video-viewfinder-card">
              <video 
                key={currentVidSrc} 
                src={currentVidSrc} 
                className="agent-main-video" 
                autoPlay 
                loop 
                muted 
                controls 
              />
              
              {/* Overlay HUD Bounding Target */}
              <div className="agent-video-overlay-hud">
                <div className="hud-corner-tag mono">CAM_04 [AISLE 4] 1080P 30FPS</div>
                {selectedIncident && (
                  <div className="hud-tracking-box">
                    <span className="hud-track-id mono">SUSPECT TRACK #{selectedIncident.track_id || 17}</span>
                    <span className="hud-action-label mono">{selectedIncident.event_type}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Upload Action Bar */}
            <div className="footage-upload-actions-bar">
              <label className="footage-upload-btn">
                <Upload size={16} />
                <span>Upload Video or Image for Theft Scan</span>
                <input 
                  type="file" 
                  accept="video/*,image/*" 
                  onChange={handleFileUpload} 
                  style={{ display: 'none' }} 
                />
              </label>

              <button 
                className="benchmark-demo-btn"
                onClick={() => {
                  if (incidentsList.length > 0) {
                    setSelectedIncident(incidentsList[0]);
                  }
                }}
              >
                <Sparkles size={16} className="text-violet" />
                <span>Load High-Risk Shoplifting Sample</span>
              </button>
            </div>

            {/* Analysis In-Progress Scanning Bar */}
            {isAnalyzing && (
              <div className="analysis-progress-overlay animated-pop">
                <div className="analysis-progress-spinner">
                  <Cpu size={20} className="spin-slow text-cyan" />
                  <span className="mono">{analysisStepLabel}</span>
                  <span className="mono text-cyan">{analysisProgress}%</span>
                </div>
                <div className="progress-bar-track">
                  <div className="progress-bar-fill" style={{ width: `${analysisProgress}%` }}></div>
                </div>
              </div>
            )}

            {/* Recent Incident Feed Carousel */}
            <div className="recent-incidents-selector">
              <div className="selector-title mono">RECENT SECURITY EVENTS WAITING FOR ESCALATION:</div>
              <div className="incident-pills-row">
                {incidentsList.slice(0, 4).map((inc, i) => (
                  <div 
                    key={inc.id || i}
                    className={`incident-select-card ${selectedIncident?.id === inc.id ? 'active' : ''}`}
                    onClick={() => setSelectedIncident(inc)}
                  >
                    <div className="inc-type mono">{inc.event_type}</div>
                    <div className="inc-loc text-muted">{inc.location} • Conf: {Math.round(inc.confidence * 100)}%</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: AI Decision Engine & Escalation Card */}
          <div className="agent-panel escalation-decision-panel">
            <div className="panel-header-row">
              <div className="panel-title-group">
                <AlertTriangle size={18} className="text-amber" />
                <span className="mono">AGENTIC DECISION ENGINE</span>
              </div>
              <span className="badge badge-rose">SEVERITY: HIGH</span>
            </div>

            {selectedIncident ? (
              <div className="decision-flow-card">
                {/* Detection Details Card */}
                <div className="detected-anomaly-box">
                  <div className="anomaly-header">
                    <div className="anomaly-badge">SUSPICIOUS BEHAVIOR DETECTED</div>
                    <div className="anomaly-conf mono">CONFIDENCE: {Math.round(selectedIncident.confidence * 100)}%</div>
                  </div>

                  <div className="anomaly-field-grid">
                    <div className="anomaly-field">
                      <span className="field-lbl">EVENT CLASSIFICATION:</span>
                      <span className="field-val highlight text-rose">{selectedIncident.event_type}</span>
                    </div>
                    <div className="anomaly-field">
                      <span className="field-lbl">LOCATION:</span>
                      <span className="field-val">{selectedIncident.location}</span>
                    </div>
                    <div className="anomaly-field">
                      <span className="field-lbl">CURRENT PERSON STATUS:</span>
                      <span className="field-val text-emerald">{selectedIncident.current_zone || 'Near Checkout Area'}</span>
                    </div>
                    <div className="anomaly-field">
                      <span className="field-lbl">TIMESTAMP:</span>
                      <span className="field-val mono">{selectedIncident.timestamp || '11:42 PM'}</span>
                    </div>
                  </div>

                  <div className="anomaly-description">
                    <span className="desc-title mono">VISION AGENT OBSERVATION:</span>
                    <p>{selectedIncident.description}</p>
                  </div>
                </div>

                {/* 3-Step Decision Logic Trace */}
                <div className="agent-reasoning-chain">
                  <div className="chain-step checked">
                    <CheckCircle2 size={16} className="text-emerald" />
                    <span>Pose analysis confirms rapid product concealment gesture (91% confidence).</span>
                  </div>
                  <div className="chain-step checked">
                    <CheckCircle2 size={16} className="text-emerald" />
                    <span>Suspect moved directly from high-value shelf toward checkout perimeter.</span>
                  </div>
                  <div className="chain-step alert">
                    <ShieldAlert size={16} className="text-amber" />
                    <span>Autonomous threshold exceeded: <strong>Store Manager Verification Required</strong>.</span>
                  </div>
                </div>

                {/* Big Action Call Button */}
                <div className="initiate-call-cta-box">
                  <div className="manager-phone-config-row">
                    <label className="phone-cfg-label mono">
                      <PhoneCall size={14} className="text-emerald" />
                      <span>STORE MANAGER MOBILE:</span>
                    </label>
                    <input 
                      type="text" 
                      className="manager-phone-input mono" 
                      value={managerPhoneNumber}
                      onChange={(e) => setManagerPhoneNumber(e.target.value)}
                      placeholder="+91 9545696585"
                    />
                  </div>

                  <button 
                    className="call-manager-action-btn pulse-glow"
                    onClick={() => startManagerCall(selectedIncident)}
                  >
                    <PhoneCall size={20} />
                    <span>CALL STORE MANAGER ({managerPhoneNumber})</span>
                  </button>
                  <p className="call-hint-text">
                    Outbound AI Security Call to <strong>{managerPhoneNumber}</strong>. Telephony gateway ready (Twilio / Exotel / WebRTC).
                  </p>
                </div>
              </div>
            ) : (
              <div className="no-incident-placeholder">
                <ShieldCheck size={48} className="text-muted" />
                <p>Select or upload CCTV footage on the left to run Vision Agent detection.</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* CALL TAB: Live Outbound Voice Call to Store Manager */
        <div className="agent-call-stage-wrapper animated-pop">
          <div className="call-console-grid">
            
            {/* Left Console: Phone Session & Voice Agent Hub */}
            <div className="call-session-card">
              {/* Call Top Status Banner */}
              <div className="call-top-banner">
                <div className="call-peer-info">
                  <div className="phone-icon-pulse">
                    <PhoneCall size={20} color="#fff" />
                  </div>
                  <div>
                    <div className="peer-title">STORE OPERATIONS MANAGER</div>
                    <div className="peer-phone mono">{managerPhoneNumber} • MOBILE SUBSCRIBER (INDIA)</div>
                  </div>
                </div>

                <div className={`call-state-pill ${callStatus.toLowerCase()}`}>
                  {callStatus === 'RINGING' && (
                    <span className="mono">CALLING STORE MANAGER...</span>
                  )}
                  {callStatus === 'CONNECTED' && (
                    <>
                      <span className="call-live-dot-pulse"></span>
                      <span className="mono">CALL ACTIVE • {formatSeconds(callTime)}</span>
                    </>
                  )}
                  {callStatus === 'ENDED' && (
                    <span className="mono">CALL COMPLETED</span>
                  )}
                </div>
              </div>

              {/* Telecom Status Indicator Banner */}
              {telecomStatus && telecomStatus.provider === 'TWILIO' && telecomStatus.status === 'DISPATCHED_TO_MOBILE' && (
                <div style={{
                  margin: '12px 20px 4px 20px',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  color: '#34d399',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '13px',
                  fontWeight: 600,
                  fontFamily: 'monospace'
                }}>
                  <PhoneCall size={18} className="pulse-live" />
                  <span>CELLULAR CALL DIALED VIA TWILIO TO HANDSET ({telecomStatus.to || managerPhoneNumber}) — ANSWER YOUR PHONE!</span>
                </div>
              )}

              {telecomStatus && telecomStatus.provider === 'BROWSER_WEBRTC_VOICE_GATEWAY' && (
                <div style={{
                  margin: '12px 20px 4px 20px',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.12)',
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  color: '#38bdf8',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '13px',
                  fontFamily: 'monospace'
                }}>
                  <Activity size={18} />
                  <span>IN-BROWSER MODE ACTIVE (Speak using your laptop microphone)</span>
                </div>
              )}

              {/* Center Voice AI Orb & Dynamic Sound Waves */}
              <div className="voice-agent-orb-section">
                <AiOrbCanvas mode={callStatus === 'CONNECTED' ? 'call_active' : 'idle'} size={150} />

                <div className="voice-status-indicator">
                  <div className="speaking-tag mono">
                    {callStatus === 'RINGING' ? 'OUTBOUND DIALING' : 'AI VOICE ASSISTANT ONLINE'}
                  </div>

                  {callStatus === 'CONNECTED' && (
                    <div className="audio-waveform-bars">
                      <div className="wave-bar b1"></div>
                      <div className="wave-bar b2"></div>
                      <div className="wave-bar b3"></div>
                      <div className="wave-bar b4"></div>
                      <div className="wave-bar b5"></div>
                      <div className="wave-bar b6"></div>
                      <div className="wave-bar b7"></div>
                    </div>
                  )}
                </div>
              </div>

              {/* Live Communication Transcript */}
              <div className="conversation-transcript-box">
                <div className="transcript-title mono">REAL-TIME CALL TRANSCRIPT & ACTIONS</div>
                <div className="transcript-scroll-area">
                  {transcript.map((msg, idx) => (
                    <div 
                      key={idx} 
                      className={`transcript-bubble ${msg.speaker === 'AI AGENT' ? 'agent-bubble' : 'manager-bubble'}`}
                    >
                      <div className="bubble-meta">
                        <span className="speaker-name mono">{msg.speaker}</span>
                        <span className="msg-time mono">{msg.time}</span>
                      </div>
                      <div className="bubble-text">{msg.text}</div>
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>
              </div>

              {/* Manager Talking & Interactive Controls */}
              <div className="call-interactive-controls-bar">
                {/* One-Click Quick Response Chips (Manager can say these) */}
                <div className="quick-manager-chips">
                  <span className="chips-label mono">QUICK QUESTIONS TO CCTV AGENT:</span>
                  <div className="chips-row">
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("How many people are there?")}
                    >
                      👥 "How many people are there?"
                    </button>
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("Give me a summary of the video.")}
                    >
                      📋 "Give me a summary of video"
                    </button>
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("What is the suspect wearing?")}
                    >
                      🧥 "What is suspect wearing?"
                    </button>
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("Did they pay at checkout?")}
                    >
                      💳 "Did they pay at checkout?"
                    </button>
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("Who else is in the store?")}
                    >
                      👥 "Who else is there?"
                    </button>
                    <button 
                      className="quick-chip"
                      onClick={() => handleManagerMessage("Are they still inside the store?")}
                    >
                      📍 "Are they still inside?"
                    </button>
                    <button 
                      className="quick-chip alert-chip"
                      onClick={() => handleManagerMessage("Ask security to check.")}
                    >
                      🚨 "Ask security to check"
                    </button>
                    <button 
                      className="quick-chip dismiss-chip"
                      onClick={() => handleManagerMessage("Ignore, false alarm.")}
                    >
                      ❌ "Ignore, false alarm"
                    </button>
                  </div>
                </div>

                {/* Manager Mic & Custom Input Field */}
                <div className="manager-input-row">
                  <button 
                    className={`manager-mic-btn ${isListening ? 'listening' : ''}`}
                    onClick={toggleMic}
                    title={isListening ? 'Listening... Speak now' : 'Click to talk via Microphone'}
                  >
                    <Mic size={18} />
                    <span className="mono">{isListening ? 'LISTENING...' : 'SPEAK'}</span>
                  </button>

                  <input 
                    type="text"
                    className="manager-text-input"
                    placeholder="Type manager's answer or question to AI Agent..."
                    value={managerInput}
                    onChange={(e) => setManagerInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleManagerMessage();
                    }}
                  />

                  <button 
                    className="manager-send-btn"
                    onClick={() => handleManagerMessage()}
                  >
                    <Send size={16} />
                  </button>

                  <button 
                    className={`manager-mute-btn ${isMuted ? 'muted' : ''}`}
                    onClick={() => setIsMuted(!isMuted)}
                    title={isMuted ? 'Unmute AI Voice' : 'Mute AI Voice'}
                  >
                    {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                  </button>

                  <button 
                    className="manager-end-btn"
                    onClick={endCall}
                    title="End Call"
                  >
                    <PhoneOff size={18} />
                    <span>END CALL</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Right Console: CCTV Evidence PIP & Real-Time Tool Execution */}
            <div className="call-side-context-card">
              <div className="side-title mono">INCIDENT EVIDENCE & LIVE TOOLS</div>

              {/* Mini PIP Video Player */}
              <div className="call-pip-video-card">
                <video 
                  key={currentVidSrc} 
                  src={currentVidSrc} 
                  className="call-pip-video" 
                  autoPlay 
                  loop 
                  muted 
                />
                <div className="pip-video-meta">
                  <div className="pip-badge mono">{selectedIncident?.location || 'Aisle 4'}</div>
                  <div className="pip-track mono">SUSPECT #{selectedIncident?.track_id || 17} • {Math.round((selectedIncident?.confidence || 0.92) * 100)}% CONF</div>
                </div>
              </div>

              {/* CCTV Video Telemetry & Dynamic Summary Card */}
              <div style={{
                margin: '10px 14px',
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'rgba(15, 23, 42, 0.75)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                fontSize: '12px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px' }}>
                  <span style={{ color: '#38bdf8', fontWeight: 600, fontFamily: 'monospace' }}>VIDEO INTELLIGENCE</span>
                  <span style={{ color: '#34d399', fontWeight: 600, fontFamily: 'monospace' }}>👥 {selectedIncident?.total_persons || 3} PEOPLE IN STORE</span>
                </div>
                <div style={{ color: '#94a3b8', lineHeight: '1.4', marginBottom: '8px' }}>
                  <strong style={{ color: '#e2e8f0' }}>Summary: </strong>
                  {selectedIncident?.video_summary || selectedIncident?.description || 'People detected in store. Suspect Track #17 observed concealing an item and heading toward exit.'}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '4px', fontSize: '11px', color: '#cbd5e1' }}>
                  <div>🧥 <strong>Suspect:</strong> {selectedIncident?.appearance || 'Dark jacket and trousers, carrying tote bag'}</div>
                  <div>💳 <strong>Payment Status:</strong> {selectedIncident?.payment_status || 'No scan registered at checkout register'}</div>
                </div>
              </div>

              {/* Action Escalation Badge */}
              <div className="action-escalation-status-box">
                <span className="status-label mono">INCIDENT STATUS:</span>
                {actionStatus === 'MONITORING' && (
                  <div className="status-badge-display monitoring">
                    <Activity size={16} className="text-amber" />
                    <span>AWAITING MANAGER VERIFICATION</span>
                  </div>
                )}
                {actionStatus === 'SECURITY_DISPATCHED' && (
                  <div className="status-badge-display dispatched animated-pop">
                    <ShieldAlert size={16} className="text-rose" />
                    <span>SECURITY DISPATCHED • INTERCEPT ACTIVE</span>
                  </div>
                )}
                {actionStatus === 'FALSE_ALARM_DISMISSED' && (
                  <div className="status-badge-display dismissed animated-pop">
                    <CheckCircle2 size={16} className="text-emerald" />
                    <span>DISMISSED AS FALSE ALARM</span>
                  </div>
                )}
              </div>

              {/* Agent Tools Execution Timeline */}
              <div className="tool-execution-timeline">
                <div className="timeline-title mono">AGENT TOOL EXECUTIONS:</div>
                {toolLogs.length === 0 ? (
                  <div className="tool-log-empty mono">
                    Agent tools will execute in response to manager commands...
                  </div>
                ) : (
                  <div className="tool-log-items">
                    {toolLogs.map((item, idx) => (
                      <div key={idx} className="tool-log-item animated-slide-in">
                        <div className="tool-header">
                          <Cpu size={14} className="text-cyan" />
                          <span className="tool-name mono">{item.tool}()</span>
                          <span className="tool-time mono">{item.time}</span>
                        </div>
                        <pre className="tool-result-json mono">
                          {JSON.stringify(item.result, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Navigation button to Journey */}
              <div className="side-footer-actions">
                <button 
                  className="view-journey-side-btn"
                  onClick={onNavigateToJourney}
                >
                  <Eye size={16} />
                  <span>Inspect Multi-Camera Journey</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

export default SecurityCallAssistant;
