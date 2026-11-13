import { useEffect, useRef, useState } from 'react'
import {
  Activity, AudioLines, ArrowDownToLine, ArrowRight, BadgeCheck, Check, ChevronDown, Download,
  CircleHelp, Clock3, FileImage, FileText, Fingerprint, History, Languages, LoaderCircle, Settings, UserRound,
  LockKeyhole, LogOut, Mic, Plus, Radio, ScanLine, Shield, ShieldAlert, ShieldCheck, Sparkles,
  Trash2, Upload, Volume2, X,
} from 'lucide-react'
import { AccountPage, RecoveryPage, SitePage } from './Pages.jsx'

const modes = [
  { id: 'audio', title: 'Voice check', sub: 'Detect synthetic speech', icon: AudioLines },
  { id: 'text', title: 'Claim check', sub: 'Verify text claims', icon: FileText },
  { id: 'image', title: 'Screenshot', sub: 'Extract & check text', icon: FileImage },
]

async function request(path, options) {
  const response = await fetch(path, { credentials: 'include', ...options })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.detail || 'Something went wrong. Please try again.')
    error.status = response.status
    throw error
  }
  return data
}

async function sourceFileDetails(file) {
  if (!file) return {}
  let source_sha256
  try {
    if (globalThis.crypto?.subtle) {
      const digest = await globalThis.crypto.subtle.digest('SHA-256', await file.arrayBuffer())
      source_sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
    }
  } catch { /* Provenance hashing is optional; analysis still runs if unavailable. */ }
  return { source_filename: file.name, source_content_type: file.type, source_sha256, source_bytes: file.size }
}

function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [session, setSession] = useState({ loading: true, user: null })
  const navigate = (next, replace = false) => {
    if (replace) window.history.replaceState({}, '', next)
    else if (window.location.pathname !== next) window.history.pushState({}, '', next)
    setPath(next.split('?')[0])
  }
  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])
  useEffect(() => {
    request('/api/auth/me').then((user) => setSession({ loading: false, user })).catch(() => setSession({ loading: false, user: null }))
  }, [])
  useEffect(() => { if (session.user && ['/login', '/register'].includes(path)) navigate('/', true) }, [session.user, path])
  useEffect(() => {
    const titles = { '/': 'Workspace', '/profile': 'Profile', '/settings': 'Account settings', '/help': 'Help', '/about': 'About', '/contact': 'Contact', '/privacy': 'Privacy', '/terms': 'Terms', '/faq': 'FAQ', '/login': 'Log in', '/register': 'Create account', '/forgot-password': 'Password recovery', '/reset-password': 'Reset password' }
    document.title = `${titles[path] || 'Page not found'} · VoiceShield`
  }, [path])
  if (session.loading) return <div className="auth-loading"><LoaderCircle className="spin" size={19} /> Checking your session…</div>
  const onAuthenticated = (user) => { navigate('/', true); setSession({ loading: false, user }) }
  const onSessionExpired = () => { navigate('/login', true); setSession({ loading: false, user: null }) }
  if (path === '/forgot-password' || path === '/reset-password') return <RecoveryPage path={path} navigate={navigate} />
  if (['/about', '/help', '/privacy', '/terms', '/faq', '/contact', '/not-found'].includes(path)) return <SitePage path={path} navigate={navigate} onSessionExpired={onSessionExpired} />
  if (!session.user && ['/profile', '/settings'].includes(path)) return <AuthPage path="/login" navigate={navigate} onAuthenticated={onAuthenticated} />
  if (session.user && ['/profile', '/settings'].includes(path)) return <AccountPage path={path} user={session.user} navigate={navigate} onUserUpdated={(user) => setSession({ loading: false, user })} onAccountDeleted={onSessionExpired} />
  if (path === '/login' || path === '/register') {
    if (session.user) return <Workspace user={session.user} navigate={navigate} onSessionExpired={onSessionExpired} />
    return <AuthPage path={path} navigate={navigate} onAuthenticated={onAuthenticated} />
  }
  if (path !== '/') return <SitePage path="/not-found" navigate={navigate} onSessionExpired={onSessionExpired} />
  if (!session.user) return <AuthPage path="/login" navigate={navigate} onAuthenticated={onAuthenticated} />
  return <Workspace user={session.user} navigate={navigate} onSessionExpired={onSessionExpired} />
}

function AuthPage({ path, navigate, onAuthenticated }) {
  const mode = path === '/register' ? 'register' : 'login'
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const changeMode = (nextMode) => { setError(''); navigate(nextMode === 'register' ? '/register' : '/login') }
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const body = mode === 'register' ? { full_name: fullName, email, password } : { email, password }
      const user = await request(`/api/auth/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      onAuthenticated(user)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <main className="auth-shell"><a className="brand auth-brand" href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}><span className="brand-mark"><Shield size={20} strokeWidth={2.2} /><span className="brand-spark">✳</span></span><span>voice<span className="brand-bold">shield</span></span></a><section className="auth-card"><span className="section-kicker">SECURE FORENSIC WORKSPACE</span><h1>{mode === 'login' ? 'Welcome back.' : 'Create your account.'}</h1><p className="auth-subtitle">{mode === 'login' ? 'Sign in to continue to your private analysis workspace.' : 'Your saved checks will be private to your account.'}</p><div className="auth-tabs"><button type="button" className={mode === 'login' ? 'selected' : ''} onClick={() => changeMode('login')}>Log in</button><button type="button" className={mode === 'register' ? 'selected' : ''} onClick={() => changeMode('register')}>Create account</button></div><form onSubmit={submit} className="auth-form">{mode === 'register' && <label>Full name<input autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} required maxLength={100} /></label>}<label>Email address<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={254} /></label><label>Password<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={mode === 'register' ? 10 : 1} maxLength={128} />{mode === 'register' && <small>Use at least 10 characters.</small>}</label>{error && <div role="alert" className="error-banner"><ShieldAlert size={16} />{error}</div>}<button className="analyze-button auth-submit" disabled={busy}>{busy ? <><LoaderCircle className="spin" size={16} /> Working…</> : mode === 'login' ? <>Log in <ArrowRight size={16} /></> : <>Create account <ArrowRight size={16} /></>}</button></form>{mode === 'login' && <button className="auth-forgot" onClick={() => navigate('/forgot-password')}>Forgot your password?</button>}<p className="auth-privacy"><LockKeyhole size={13} /> Passwords are stored as salted hashes. Sessions use secure HTTP-only cookies.</p></section><span className="auth-footer">VoiceShield · Private research workspace</span></main>
}

function Workspace({ user, navigate, onSessionExpired }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState(null)
  const [health, setHealth] = useState(null)
  const [recording, setRecording] = useState(false)
  const [language, setLanguage] = useState('auto')
  const [ocrText, setOcrText] = useState('')
  const [ocrConfidence, setOcrConfidence] = useState(null)
  const [ocrBusy, setOcrBusy] = useState(false)
  const [audioUrl, setAudioUrl] = useState('')
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyKind, setHistoryKind] = useState('all')
  const [historySort, setHistorySort] = useState('newest')
  const [activeNav, setActiveNav] = useState('new')
  const [historyHasMore, setHistoryHasMore] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [deletingId, setDeletingId] = useState(null)
  const [pdfBusy, setPdfBusy] = useState(false)
  const inputRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const historyRequestRef = useRef(0)

  const refreshHistory = async (append = false) => {
    const requestId = ++historyRequestRef.current
    setHistoryLoading(true)
    setHistoryError('')
    const params = new URLSearchParams({ limit: '100', skip: String(append ? history.length : 0), sort: historySort })
    if (historyKind !== 'all') params.set('kind', historyKind)
    if (historyQuery.trim()) params.set('q', historyQuery.trim())
    try {
      const response = await fetch(`/api/history?${params}`, { credentials: 'include' })
      const data = await response.json().catch(() => [])
      if (!response.ok) { const err = new Error(data.detail || 'History could not be loaded.'); err.status = response.status; throw err }
      if (requestId === historyRequestRef.current) {
        setHistory((current) => append ? [...current, ...data] : data)
        setHistoryHasMore(response.headers.get('X-Has-More') === 'true')
      }
    } catch (err) { if (err.status === 401) onSessionExpired(); else if (requestId === historyRequestRef.current) setHistoryError(err.message) }
    finally { if (requestId === historyRequestRef.current) setHistoryLoading(false) }
  }
  useEffect(() => {
    request('/api/health').then((data) => { setHealth(data); setApiOnline(true) }).catch(() => setApiOnline(false))
  }, [])
  useEffect(() => { const timer = setTimeout(() => refreshHistory(false), 250); return () => clearTimeout(timer) }, [historyQuery, historyKind, historySort])
  useEffect(() => {
    if (!file || mode !== 'audio') { setAudioUrl(''); return }
    const url = URL.createObjectURL(file)
    setAudioUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file, mode])

  const chooseMode = (id) => { setMode(id); setActiveNav(id); setFile(null); setOcrText(''); setOcrConfidence(null); setResult(null); setError('') }
  const setSelectedFile = (candidate) => {
    setError('')
    if (!candidate) { setFile(null); setOcrText(''); setOcrConfidence(null); return }
    setFile(null); setOcrText(''); setOcrConfidence(null)
    const audio = mode === 'audio'
    const maxBytes = audio ? 20_000_000 : 8_000_000
    const allowed = audio ? ['audio/wav', 'audio/x-wav', 'audio/wave', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/webm', 'audio/ogg', 'audio/flac', 'application/octet-stream'] : ['image/png', 'image/jpeg', 'image/webp']
    const extensions = audio ? /\.(wav|mp3|m4a|mp4|webm|ogg|flac)$/i : /\.(png|jpe?g|webp)$/i
    if (candidate.size > maxBytes) { setError(`This file exceeds the ${audio ? '20 MB audio' : '8 MB image'} limit.`); return }
    if ((candidate.type && !allowed.includes(candidate.type)) || (!candidate.type && !extensions.test(candidate.name))) { setError(`Choose a supported ${audio ? 'audio file (WAV, MP3, M4A, WebM, OGG, FLAC)' : 'image (PNG, JPEG, WebP)'}.`); return }
    setFile(candidate); setOcrText(''); setOcrConfidence(null)
  }
  const downloadReport = async (id) => {
    setPdfBusy(true); setError('')
    try {
      const response = await fetch(`/api/reports/${id}/pdf`, { credentials: 'include' })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        const failure = new Error(body.detail || 'The report could not be downloaded.')
        failure.status = response.status
        throw failure
      }
      const blobUrl = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = blobUrl
      anchor.download = `VoiceShield-Report-${id}.pdf`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
    } catch (err) { if (err.status === 401) onSessionExpired(); else setError(err.message) } finally { setPdfBusy(false) }
  }
  const deleteReport = async (id) => {
    if (!window.confirm(`Delete investigation #${id} and its saved evidence? This cannot be undone.`)) return
    setDeletingId(id); setError('')
    try { await request(`/api/history/${id}`, { method: 'DELETE' }); setHistory((items) => items.filter((item) => item.id !== id)); if (result?.id === id) setResult(null) }
    catch (err) { if (err.status === 401) onSessionExpired(); else setError(err.message) }
    finally { setDeletingId(null) }
  }
  const logout = async () => { try { await request('/api/auth/logout', { method: 'POST' }); onSessionExpired() } catch (err) { if (err.status === 401) onSessionExpired(); else setError(`Could not sign out: ${err.message}`) } }
  const submit = async (event) => {
    event?.preventDefault()
    setBusy(true); setError(''); setResult(null)
    try {
      let data
      if (mode === 'text') {
        if (text.trim().length < 8) throw new Error('Add a little more text so there is something to review.')
        data = await request('/api/analyze/text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language }) })
      } else if (mode === 'image' && ocrText) {
        const source = await sourceFileDetails(file)
        data = await request('/api/analyze/text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: ocrText, language, kind: 'image', ocr_confidence: ocrConfidence, ...source }) })
      } else {
        if (!file) throw new Error(`Choose a ${mode === 'audio' ? 'voice recording' : 'screenshot'} first.`)
        const body = new FormData(); body.append('file', file)
        data = await request(`/api/analyze/${mode}`, { method: 'POST', body })
      }
      setResult(data); refreshHistory()
    } catch (err) { if (err.status === 401) onSessionExpired(); else setError(err.message) } finally { setBusy(false) }
  }
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => event.data.size && chunksRef.current.push(event.data)
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        setFile(new File([blob], 'voice-recording.webm', { type: blob.type }))
        stream.getTracks().forEach((track) => track.stop())
      }
      recorder.start(); recorderRef.current = recorder; setRecording(true)
    } catch { setError('Microphone access was unavailable. You can upload an audio file instead.') }
  }
  const stopRecording = () => { recorderRef.current?.stop(); setRecording(false) }

  const extractScreenshot = async () => {
    if (!file) { setError('Choose a screenshot to extract text.'); return }
    setOcrBusy(true); setError('')
    try {
      const body = new FormData(); body.append('file', file); body.append('language', language)
      const result = await request('/api/ocr', { method: 'POST', body })
      setOcrText(result.text || ''); setOcrConfidence(result.confidence)
      if (!result.text) setError('No readable text was found. Try a clearer image or another OCR language.')
    } catch (err) { if (err.status === 401) onSessionExpired(); else setError(err.message) } finally { setOcrBusy(false) }
  }
  const visibleHistory = history

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" onClick={(event) => { event.preventDefault(); navigate('/') }} aria-label="VoiceShield home"><span className="brand-mark"><Shield size={20} strokeWidth={2.2} /><span className="brand-spark">✳</span></span><span>voice<span className="brand-bold">shield</span></span></a>
      <div className="side-label">WORKSPACE</div>
      <button className={`nav-item ${activeNav === 'new' ? 'active' : ''}`} onClick={() => { chooseMode('text'); setActiveNav('new'); document.querySelector('.analyzer-card')?.scrollIntoView({ behavior: 'smooth' }) }}><ScanLine size={17} /><span>New analysis</span><span className="nav-shortcut">↵</span></button>
      <button className={`nav-item ${activeNav === 'history' ? 'active' : ''}`} onClick={() => { setActiveNav('history'); document.getElementById('recent')?.scrollIntoView({ behavior: 'smooth' }) }}><History size={17} /><span>Analysis history</span></button>
      <div className="side-divider" />
      <div className="side-label">TOOLS</div>
      {modes.map(({ id, title, icon: Icon }) => <button key={id} className={`nav-item ${activeNav === id ? 'active' : ''}`} onClick={() => chooseMode(id)}><Icon size={17} /><span>{title}</span></button>)}
      <button className="nav-item profile-nav" onClick={() => navigate('/profile')}><UserRound size={17} /><span>Profile</span></button>
      <div className="sidebar-bottom"><div className="privacy-card"><span className="privacy-icon"><LockKeyhole size={16} /></span><div><strong>Your checks stay private</strong><p>Only your account can access its history.</p></div></div><div className="profile"><div className="avatar">{user.full_name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</div><div className="profile-name"><strong>{user.full_name}</strong><span>{user.email}</span></div><button className="logout-button" type="button" onClick={logout} title="Log out" aria-label="Log out"><LogOut size={15} /></button></div></div>
    </aside>

    <main className="main-content" id="top">
      <header className="topbar"><div className="breadcrumbs"><span>VoiceShield</span><span className="crumb-slash">/</span><strong>Forensic workspace</strong></div><div className="top-actions"><span className={`api-status ${apiOnline === false || health?.database === 'unavailable' ? 'offline' : ''}`}><span className="status-dot" />{apiOnline === false ? 'API offline' : health ? `API ${health.status} · DB ${health.database}` : 'Checking services'}</span><button type="button" className="top-user" onClick={() => navigate('/profile')} title="Open profile"><span className="top-avatar">{user.full_name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</span><span>{user.full_name}</span></button><button className="mobile-logout" type="button" onClick={logout} aria-label="Log out" title="Log out"><LogOut size={16} /></button><button className="help-button" type="button" onClick={() => navigate('/help')} title="Help and support" aria-label="Help and support"><CircleHelp size={18} /></button></div></header>
      <div className="page-wrap">
        <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" />DIGITAL FORENSICS · EVIDENCE DESK</div><h1>Investigate with <span>evidence.</span></h1><p className="page-subtitle">Screen a voice recording, verify a claim, or inspect text from a screenshot.</p></div><div className="privacy-pill"><Shield size={14} /> Private workspace</div></section>

        <section className="workspace-grid">
          <div className="analyzer-card">
            <div className="card-heading"><div><span className="section-kicker">START AN INVESTIGATION</span><h2>Choose your evidence source</h2></div><span className="step-label"><span>01</span> SELECT</span></div>
            <div className="mode-tabs" role="tablist" aria-label="Analysis type">{modes.map(({ id, title, sub, icon: Icon }) => <button role="tab" aria-selected={mode === id} key={id} onClick={() => chooseMode(id)} className={`mode-tab ${mode === id ? 'selected' : ''}`}><Icon size={18} strokeWidth={1.8} /><span className="mode-copy"><strong>{title}</strong><small>{sub}</small></span></button>)}</div>
            <form onSubmit={submit}>
      {(mode === 'text' || (mode === 'image' && ocrText)) ? <div className="text-entry"><label htmlFor="claim-input" className="input-label">{mode === 'image' ? 'REVIEW OCR TEXT BEFORE ANALYSIS' : 'CLAIM OR MESSAGE'}</label><textarea id="claim-input" required value={mode === 'image' ? ocrText : text} onChange={(e) => mode === 'image' ? setOcrText(e.target.value) : setText(e.target.value)} maxLength={12000} placeholder={'Paste a claim or message to inspect…'} /><div className="input-footer"><span>{mode === 'image' ? `OCR confidence ${ocrConfidence == null ? 'unavailable' : `${Math.round(ocrConfidence * 100)}%`}` : 'If configured, claim text is sent to Google Fact Check; review metadata is saved locally'}</span><span>{(mode === 'image' ? ocrText : text).length.toLocaleString()} / 12,000</span></div></div> : <div className="file-entry">
                <input ref={inputRef} type="file" hidden accept={mode === 'audio' ? 'audio/wav,audio/mpeg,audio/mp4,audio/webm,audio/ogg,audio/flac,.wav,.mp3,.m4a,.webm,.ogg,.flac' : 'image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp'} onChange={(e) => { setSelectedFile(e.target.files?.[0] || null); e.target.value = '' }} />
                {file ? <div className="selected-file"><span className="file-icon">{mode === 'audio' ? <Volume2 size={19} /> : <FileImage size={19} />}</span><div className="file-meta"><strong>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(2)} MB · Ready to analyze</small></div><button type="button" className="remove-file" onClick={() => setSelectedFile(null)} aria-label="Remove file"><X size={16} /></button></div> : <button className="drop-zone" type="button" onClick={() => inputRef.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) setSelectedFile(e.dataTransfer.files[0]) }}><span className="upload-icon">{mode === 'audio' ? <AudioLines size={21} /> : <Upload size={20} />}</span><strong>Drop your {mode === 'audio' ? 'audio file' : 'screenshot'} here</strong><span>or <b>browse files</b></span><small>{mode === 'audio' ? 'WAV, MP3, M4A, WebM · max 20 MB' : 'PNG, JPG, WebP · max 8 MB'}</small></button>}
                {mode === 'audio' && <>{file && <audio className="audio-preview" controls src={audioUrl} /> }<div className="record-row"><span>Record a voice note or choose an audio file.</span><button type="button" onClick={recording ? stopRecording : startRecording} className={`record-button ${recording ? 'recording' : ''}`}><span className="record-dot" />{recording ? 'Stop recording' : 'Record audio'}</button></div></>}
                {mode === 'image' && file && <button type="button" className="analyze-button ocr-button" onClick={extractScreenshot} disabled={ocrBusy}>{ocrBusy ? 'Extracting text…' : 'Extract text for review'} <ScanLine size={15} /></button>}
              </div>}
              {(mode === 'text' || mode === 'image') && <label className="language-select">Analysis language<select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="auto">Automatic (may be ambiguous)</option><option value="en">English</option><option value="hi">Hindi</option><option value="mr">Marathi</option></select></label>}
              {error && <div role="alert" className="error-banner"><ShieldAlert size={16} /><span>{error}</span><button type="button" onClick={mode === 'image' && file && !ocrText ? extractScreenshot : submit} disabled={busy || ocrBusy}>Retry</button></div>}
              <div className="submit-row"><span className="safe-note"><LockKeyhole size={13} /> Private to your account</span><button className="analyze-button" disabled={busy || (mode === 'image' && !ocrText)}>{busy ? <><LoaderCircle className="spin" size={16} /> Analyzing…</> : <>Analyze {mode === 'audio' ? 'voice' : mode === 'image' ? 'extracted claim' : 'claim'} <ArrowRight size={16} /></>}</button></div>
            </form>
            <div className="card-bottom-note"><Sparkles size={14} /><span>Results show available evidence and clearly mark model limitations.</span><a href="#about" title="Learn how analysis works"><CircleHelp size={14} /></a></div>
          </div>

          <aside className="how-card"><div className="how-top"><div className="how-icon"><Fingerprint size={20} /></div><span className="how-tag"><span /> SYSTEM STATUS</span></div><h3>Every signal has a source.</h3><p>Configured checkpoints load when first used. Predictions are screening signals, not proof.</p><div className="service-list">{[['Database', health?.database], ['Voice spoof detector', health?.models?.audio], ['English claim model', health?.models?.english], ['Hindi/Marathi model', health?.models?.multilingual?.hi], ['Screenshot OCR', health?.ocr], ['Publisher fact checks', health?.fact_check]].map(([name, state]) => <div className="service-row" key={name}><span className={`service-dot ${state === 'ready' || state === 'installed' ? 'ready' : ''}`} /><span>{name}</span><b title={state || 'checking'}>{state || 'checking'}</b></div>)}</div><div className="how-footer"><ShieldCheck size={15} /><span>Evidence and model outputs stay distinct</span></div></aside>
        </section>

        {result && <ResultCard result={result} onDismiss={() => setResult(null)} onDownload={() => downloadReport(result.id)} onDelete={() => deleteReport(result.id)} pdfBusy={pdfBusy} deleting={deletingId === result.id} />}

        <section className="workspace-stats" aria-label="Recent record counts"><div><strong>{history.length}</strong><span>records loaded</span></div><div><strong>{history.filter((item) => item.kind === 'audio').length}</strong><span>voice reviews</span></div><div><strong>{history.filter((item) => item.kind === 'text').length}</strong><span>claim reviews</span></div><div><strong>{history.filter((item) => item.kind === 'image').length}</strong><span>screenshots</span></div><small>Counts reflect the most recent 100 records.</small></section>
        <section className="about-strip" id="about"><span className="section-kicker">HOW VOICESHIELD WORKS</span><p>VoiceShield runs public community checkpoints for audio spoof screening and English/Hindi/Marathi fake-pattern classification. Screenshots are read with OCR and sent through the text workflow. Published fact-check reviews are separate evidence. Model predictions are screening signals, not proof that a claim is true or audio is manipulated.</p><p id="privacy">If configured, claim text is sent to Google Fact Check Tools for review matching. Reports are saved to your account; evidence excerpts and publisher review metadata are retained with them.</p></section>
        <section className="recent-section" id="recent"><div className="recent-heading"><div><span className="section-kicker">WORKSPACE RECORD</span><h2>Analysis history</h2><p className="history-count">{history.length} loaded {history.length === 1 ? 'record' : 'records'}{historyHasMore ? ' · more available' : ''}</p></div><button className="view-all" onClick={() => refreshHistory(false)} disabled={historyLoading}>{historyLoading ? 'Loading…' : 'Refresh'} <ArrowRight size={14} /></button></div><div className="history-tools"><input aria-label="Search history" placeholder="Search reports…" value={historyQuery} onChange={(e) => setHistoryQuery(e.target.value)} /><select aria-label="Filter history by type" value={historyKind} onChange={(e) => setHistoryKind(e.target.value)}><option value="all">All types</option><option value="audio">Voice</option><option value="text">Claims</option><option value="image">Screenshots</option></select><select aria-label="Sort reports" value={historySort} onChange={(e) => setHistorySort(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></div>{historyError && <div role="alert" className="history-error">{historyError}<button onClick={() => refreshHistory(false)} disabled={historyLoading}>Retry loading history</button></div>}{visibleHistory.length ? <div className="history-list">{visibleHistory.map((item) => <div key={item.id} className="history-entry"><button className="history-row" onClick={() => { setActiveNav('history'); setResult(item) }} aria-label={`Open report ${item.id}`}><span className={`history-icon ${item.kind}`}>{item.kind === 'audio' ? <AudioLines size={17} /> : item.kind === 'image' ? <FileImage size={17} /> : <FileText size={17} />}</span><span className="history-info"><strong>{item.kind === 'audio' ? 'Voice recording' : item.kind === 'image' ? 'Screenshot analysis' : 'Text claim'}</strong><small>{item.summary}</small></span><span className="history-badge neutral">{item.model_status === 'ready' ? item.label : 'No model result'}</span><span className="history-time"><Clock3 size={13} />{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</span><ArrowRight className="history-arrow" size={15} /></button><button className="history-delete" type="button" onClick={() => deleteReport(item.id)} disabled={deletingId === item.id} aria-label={`Delete report ${item.id}`} title="Delete report">{deletingId === item.id ? <LoaderCircle size={15} className="spin" /> : <Trash2 size={15} />}</button></div>)}</div> : historyLoading ? <div className="history-loading"><LoaderCircle size={17} className="spin" /> Loading account history…</div> : !historyError && <div className="empty-history"><span className="empty-history-icon"><History size={20} /></span><div><strong>{historyQuery || historyKind !== 'all' ? 'No analyses match these filters' : 'Your checks will show up here'}</strong><p>{historyQuery || historyKind !== 'all' ? 'Clear the search or select another analysis type.' : 'Start an analysis and its status and evidence will be saved to this account.'}</p></div>{(historyQuery || historyKind !== 'all') && <button onClick={() => { setHistoryKind('all'); setHistoryQuery('') }}>Clear filters <ArrowRight size={14} /></button>}</div>}{historyHasMore && <button className="load-more" onClick={() => refreshHistory(true)} disabled={historyLoading}>{historyLoading ? 'Loading reports…' : 'Load older reports'} <ChevronDown size={15} /></button>}</section>
        <footer className="page-footer"><span>© 2026 VoiceShield · A research verification workspace</span><div>{[['How it works', '/about'], ['Help', '/help'], ['FAQ', '/faq'], ['Privacy', '/privacy'], ['Terms', '/terms'], ['Contact', '/contact']].map(([label, path]) => <a href={path} key={path} onClick={(event) => { event.preventDefault(); navigate(path) }}>{label}</a>)}</div></footer>
      </div>
    </main>
  </div>
}

function ResultCard({ result, onDismiss, onDownload, onDelete, pdfBusy, deleting }) {
  const isAudio = result.kind === 'audio'
  const isImage = result.kind === 'image'
  const confidence = result.model_confidence == null ? null : Math.round(result.model_confidence * 100)
  const risk = result.risk_score == null ? null : Math.max(0, Math.min(100, Number(result.risk_score)))
  const metadata = result.processing_metadata || {}
  const segments = (result.evidence || []).filter((item) => typeof item.spoof_probability === 'number')
  const reportName = isAudio ? 'Voice authenticity' : isImage ? 'Screenshot analysis' : 'Claim screening'
  const scoreName = isAudio ? 'Spoof-pattern probability' : 'Fake-pattern score'
  const verdict = result.verdict ? `${result.verdict} pattern` : result.label
  const statusClass = result.model_status === 'ready' ? 'ready' : result.model_status === 'error' ? 'error' : 'pending'
  const evidence = result.evidence || []
  return <section className={`result-card forensic-report ${statusClass}`} aria-labelledby="report-title">
    <div className="report-topline"><span className="section-kicker">FORENSIC REPORT - RECORD #{result.id}</span><div className="report-actions"><button className="report-download" onClick={onDownload} disabled={pdfBusy} title="Download this investigation as a PDF">{pdfBusy ? <LoaderCircle size={15} className="spin" /> : <Download size={15} />}{pdfBusy ? 'Preparing PDF' : 'Download PDF'}</button><button className="report-delete" onClick={onDelete} disabled={deleting} title="Delete this investigation">{deleting ? <LoaderCircle size={15} className="spin" /> : <Trash2 size={15} />}<span className="sr-only">Delete report</span></button><button className="dismiss-result" onClick={onDismiss} aria-label="Dismiss result"><X size={18} /></button></div></div>
    <div className="report-hero">
      <div className="report-identity"><span className={`report-status ${statusClass}`}><i />{result.model_status?.replaceAll('_', ' ')}</span><span className="report-type">{reportName}</span><h2 id="report-title">{result.model_status === 'ready' ? verdict : result.label}</h2><p>{result.summary}</p>
        <div className="report-tags"><span><Languages size={14} />{(result.language || 'Language unavailable').toUpperCase()}</span><span><Activity size={14} />{result.model_name || 'No model prediction returned'}</span></div>
      </div>
      <div className={`report-gauge ${risk == null ? 'empty' : ''}`} style={risk == null ? undefined : { '--gauge-value': `${risk}%` }} role={risk == null ? undefined : 'img'} aria-label={risk == null ? undefined : `${scoreName}: ${risk.toFixed(1)} percent`}>
        <div className="report-gauge-inner"><strong>{risk == null ? '-' : `${risk.toFixed(1)}%`}</strong><span>{risk == null ? 'NO SCORE' : isAudio ? 'SPOOF SIGNAL' : 'FAKE SIGNAL'}</span></div>
      </div>
    </div>
    <div className="report-metrics">
      <div className="report-metric"><span>{scoreName}</span><strong>{risk == null ? 'Unavailable' : `${risk.toFixed(1)}%`}</strong><div className="metric-track" role={risk == null ? undefined : 'progressbar'} aria-valuemin={risk == null ? undefined : 0} aria-valuemax={risk == null ? undefined : 100} aria-valuenow={risk == null ? undefined : risk}><i style={{ width: risk == null ? '0%' : `${risk}%` }} /></div><small>{risk == null ? 'The model did not return a score.' : 'Model output; this is not a factual verdict.'}</small></div>
      <div className="report-metric"><span>Model confidence</span><strong>{confidence == null ? 'Unavailable' : `${confidence}%`}</strong><div className="metric-track" role={confidence == null ? undefined : 'progressbar'} aria-valuemin={confidence == null ? undefined : 0} aria-valuemax={confidence == null ? undefined : 100} aria-valuenow={confidence == null ? undefined : confidence}><i className="confidence-fill" style={{ width: confidence == null ? '0%' : `${confidence}%` }} /></div><small>Confidence for the predicted class.</small></div>
      {isImage && <div className="report-metric"><span>OCR confidence</span><strong>{metadata.ocr_confidence == null ? 'Unavailable' : `${Math.round(metadata.ocr_confidence * 100)}%`}</strong><div className="metric-track" role={metadata.ocr_confidence == null ? undefined : 'progressbar'} aria-valuemin={metadata.ocr_confidence == null ? undefined : 0} aria-valuemax={metadata.ocr_confidence == null ? undefined : 100} aria-valuenow={metadata.ocr_confidence == null ? undefined : Math.round(metadata.ocr_confidence * 100)}><i className="ocr-fill" style={{ width: metadata.ocr_confidence == null ? '0%' : `${Math.round(metadata.ocr_confidence * 100)}%` }} /></div><small>Recognition confidence from the OCR engine.</small></div>}
      {isAudio && <div className="report-metric"><span>Audio reviewed</span><strong>{metadata.duration_seconds == null ? 'Unavailable' : `${Number(metadata.duration_seconds).toFixed(1)} sec`}</strong><small>{metadata.segments == null ? 'No segment details returned.' : `${metadata.segments} four-second model segment${metadata.segments === 1 ? '' : 's'} analyzed`}</small></div>}
    </div>
    <div className="report-content-grid">
      <div className="report-panel report-evidence"><div className="report-panel-heading"><div><span className="section-kicker">TRACEABLE OUTPUT</span><h3>Evidence & analysis</h3></div><span className="evidence-count">{evidence.length} item{evidence.length === 1 ? '' : 's'}</span></div>
        {segments.length > 0 && <div className="segment-breakdown"><div className="segment-heading"><strong>Audio segment breakdown</strong><span>Reported spoof probability by segment</span></div>{segments.map((item, index) => <div className="segment-row" key={`${item.start_seconds}-${index}`}><div className="segment-label"><span>{Number(item.start_seconds).toFixed(1)}-{Number(item.end_seconds).toFixed(1)}s</span><strong>{Math.round(item.spoof_probability * 100)}%</strong></div><div className="metric-track"><i style={{ width: `${Math.max(0, Math.min(100, item.spoof_probability * 100))}%` }} /></div></div>)}</div>}
        <div className="evidence-list">{evidence.map((item, index) => <article className="evidence-row" key={`${item.type}-${index}`}><span className={`evidence-mark ${item.type || 'default'}`}><Activity size={14} /></span><div className="evidence-copy"><strong>{item.title}</strong><p>{item.quote}</p></div></article>)}</div>
      </div>
      <aside className="report-panel report-details"><span className="section-kicker">RUN DETAILS</span><h3>Model & provenance</h3><dl><div><dt>Analysis type</dt><dd>{reportName}</dd></div><div><dt>Model status</dt><dd className={`detail-status ${statusClass}`}>{result.model_status?.replaceAll('_', ' ') || 'unknown'}</dd></div><div><dt>Model</dt><dd>{result.model_name || 'Not returned'}</dd></div><div><dt>Language</dt><dd>{result.language || 'Not detected'}</dd></div><div><dt>Fact-check lookup</dt><dd>{result.fact_check_status?.replaceAll('_', ' ') || 'unknown'}</dd></div>{metadata.source_filename && <div><dt>Source file</dt><dd>{metadata.source_filename}</dd></div>}{metadata.source_content_type && <div><dt>Media type</dt><dd>{metadata.source_content_type}</dd></div>}{(metadata.bytes_received ?? metadata.source_bytes) != null && <div><dt>File size</dt><dd>{Number(metadata.bytes_received ?? metadata.source_bytes).toLocaleString()} bytes</dd></div>}{metadata.source_sha256 && <div><dt>SHA-256</dt><dd>{metadata.source_sha256}</dd></div>}{metadata.sample_rate && <div><dt>Audio sample rate</dt><dd>{Number(metadata.sample_rate).toLocaleString()} Hz</dd></div>}</dl>
        <div className="report-caveat"><CircleHelp size={16} /><p>Model confidence and pattern scores describe this model output. They do not establish that a claim is true or that audio was manipulated.</p></div>
      </aside>
    </div>
    {result.fact_checks?.length > 0 && <div className="report-panel fact-checks report-publisher-checks"><div className="report-panel-heading"><div><span className="section-kicker">INDEPENDENT SOURCES</span><h3>Published fact-check reviews</h3></div><BadgeCheck size={20} /></div>{result.fact_checks.map((check, index) => <a key={`${check.url}-${index}`} href={check.url} target="_blank" rel="noreferrer"><span>{check.publisher} - {check.rating || 'Review'}{check.review_date ? ` - ${check.review_date}` : ''}</span><b>{check.title}</b><ArrowDownToLine size={15} /></a>)}</div>}
    {metadata.ocr_confidence != null && <div className="source-strip"><ScanLine size={16} /><span>Screenshot text was extracted with OCR at {Math.round(metadata.ocr_confidence * 100)}% recognition confidence. Review the extracted text before relying on the classifier output.</span></div>}
  </section>
}
export default App


