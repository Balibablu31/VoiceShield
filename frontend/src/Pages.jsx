import { useState } from 'react'
import { ArrowLeft, ArrowRight, HelpCircle, Mail, Shield, Trash2, UserRound, Settings } from 'lucide-react'

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'include', ...options })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.detail || 'The request could not be completed.')
    error.status = response.status
    throw error
  }
  return data
}

const pageInfo = {
  '/about': ['About VoiceShield', 'A research workspace for reviewing suspicious audio, public claims, and screenshot text.', 'VoiceShield brings model screening, OCR, and published fact-check reviews into one evidence-focused workflow. Each report separates model predictions from external publisher reviews and records the limits of its analysis.', 'VoiceShield uses public community checkpoints and local OCR. Its scores are screening signals; they are not proof that a recording was manipulated or that a claim is true.'],
  '/help': ['Help and support', 'Find help with account access, analysis inputs, and interpreting reports.', 'Choose a clear audio file or a legible screenshot. For screenshots, inspect and correct OCR text before running the claim analysis. If a model is unavailable, check the system status and backend configuration.', 'If you need help from the project team, send a support request from Contact. Email delivery must be configured by the installation administrator.'],
  '/privacy': ['Privacy policy', 'What VoiceShield stores and how its analysis integrations are used.', 'Account data includes your name, email, and a salted password hash. Sessions are stored as token hashes. Analysis history is private to your account and can include model output, OCR text excerpts, source-file metadata, SHA-256 hashes, and fact-check review metadata.', 'Uploaded audio and screenshots are processed for analysis and are not saved as original files by this application. Claim text may be sent to Google Fact Check Tools when that integration is configured. The administrator controls database retention, backups, mail delivery, and deployment security. Delete your account to remove its history from the active database.'],
  '/terms': ['Terms of use', 'Use VoiceShield as an investigative aid, not as a final authority.', 'VoiceShield is provided for research and review. Model outputs can be wrong, biased, incomplete, or unsuitable for a particular language or recording condition. Verify important findings with primary sources and qualified reviewers.', 'You are responsible for having permission to submit content and for protecting sensitive information. Do not use automated predictions as the sole basis for consequential decisions. The service may be unavailable when external model checkpoints or integrations cannot be reached.'],
}

export function SitePage({ path, navigate, onSessionExpired }) {
  const info = pageInfo[path]
  const [form, setForm] = useState({ full_name: '', email: '', message: '' })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const faq = path === '/faq'
  const contact = path === '/contact'
  const title = faq ? 'Frequently asked questions' : contact ? 'Contact VoiceShield' : info?.[0] || 'Page not found'
  const subtitle = faq ? 'Clear answers about the analysis workflow and its limitations.' : contact ? 'Send a message to the VoiceShield support team.' : info?.[1]
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setNotice(null)
    try {
      const result = await api('/api/contact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
      setNotice({ kind: 'success', text: result.message }); setForm({ full_name: '', email: '', message: '' })
    } catch (error) { setNotice({ kind: 'error', text: error.message }) } finally { setBusy(false) }
  }
  return <main className="site-page-shell">
    <header className="site-page-nav"><a className="brand" href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}><span className="brand-mark"><Shield size={20} /><span className="brand-spark">✳</span></span><span>voice<span className="brand-bold">shield</span></span></a><div><a href="/help" onClick={(event) => { event.preventDefault(); navigate('/help') }}>Help</a><button className="page-back" onClick={() => navigate('/')}>Workspace <ArrowRight size={15} /></button></div></header>
    <section className="site-page-content"><nav className="page-breadcrumb"><button onClick={() => navigate('/')}>Workspace</button><span>/</span><strong>{title}</strong></nav><span className="section-kicker">VOICESHIELD · {path === '/not-found' ? '404' : 'SUPPORT'}</span><h1>{title}</h1><p className="page-lede">{subtitle}</p>
      {info && <div className="page-copy"><p>{info[2]}</p><p>{info[3]}</p></div>}
      {faq && <div className="page-faq">{[
        ['Does a model result prove a claim is true or false?', 'No. Text and audio models return pattern predictions. Published fact-check reviews are listed separately and link to their source.'],
        ['Why is a model unavailable?', 'Model checkpoints download on first use and may require local ML dependencies or network access. Check the service status and backend logs.'],
        ['What does screenshot analysis inspect?', 'It extracts legible text using OCR and routes the reviewed text through the claim workflow. It does not detect image editing or synthesis.'],
        ['Can I remove an investigation?', 'Yes. Use the delete control in the history row or report. Deletion removes the saved analysis from the active database.'],
        ['How do password reset emails work?', 'The administrator must configure SMTP settings. Reset links expire after 30 minutes and can only be used once.'],
      ].map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div>}
      {contact && <form className="account-form contact-form" onSubmit={submit}><label>Your name<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required maxLength={100} autoComplete="name" /></label><label>Email address<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required maxLength={254} autoComplete="email" /></label><label>How can we help?<textarea value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} required minLength={10} maxLength={4000} rows={6} /></label>{notice && <div role="status" className={`form-notice ${notice.kind}`}>{notice.text}</div>}<button className="page-primary" disabled={busy}>{busy ? 'Sending…' : 'Send support request'} <Mail size={16} /></button></form>}
      {path === '/not-found' && <button className="page-primary" onClick={() => navigate('/')}>Return to workspace <ArrowRight size={16} /></button>}
      <PageLinks navigate={navigate} />
    </section><footer className="site-page-footer"><span>© 2026 VoiceShield · Evidence-focused analysis</span><PageLinks navigate={navigate} /></footer>
  </main>
}

function PageLinks({ navigate }) {
  return <nav className="site-page-links" aria-label="Information pages">{[['About', '/about'], ['FAQ', '/faq'], ['Help', '/help'], ['Contact', '/contact'], ['Privacy', '/privacy'], ['Terms', '/terms']].map(([name, path]) => <a href={path} key={path} onClick={(event) => { event.preventDefault(); navigate(path) }}>{name}</a>)}</nav>
}

export function AccountPage({ path, user, navigate, onUserUpdated, onAccountDeleted }) {
  const [profile, setProfile] = useState({ full_name: user.full_name, email: user.email })
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' })
  const [deletePassword, setDeletePassword] = useState('')
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState(null)
  const settings = path === '/settings'
  const notify = (kind, text) => setNotice({ kind, text })
  const saveProfile = async (event) => {
    event.preventDefault(); setBusy('profile'); setNotice(null)
    try { const updated = await api('/api/auth/profile', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) }); onUserUpdated(updated); notify('success', 'Your profile was updated.') }
    catch (error) { if (error.status === 401) onAccountDeleted(); notify('error', error.message) } finally { setBusy('') }
  }
  const changePassword = async (event) => {
    event.preventDefault(); setBusy('password'); setNotice(null)
    try { await api('/api/auth/password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(passwords) }); setPasswords({ current_password: '', new_password: '' }); notify('success', 'Password updated. Other sessions have been signed out.') }
    catch (error) { if (error.status === 401) onAccountDeleted(); notify('error', error.message) } finally { setBusy('') }
  }
  const deleteAccount = async (event) => {
    event.preventDefault()
    if (!window.confirm('Delete your VoiceShield account and all saved investigations? This cannot be undone.')) return
    setBusy('delete'); setNotice(null)
    try { await api('/api/auth/account', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: deletePassword }) }); onAccountDeleted() }
    catch (error) { notify('error', error.message) } finally { setBusy('') }
  }
  return <main className="site-page-shell"><header className="site-page-nav"><a className="brand" href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}><span className="brand-mark"><Shield size={20} /><span className="brand-spark">✳</span></span><span>voice<span className="brand-bold">shield</span></span></a><div><button className="page-back" onClick={() => navigate('/')}>Workspace <ArrowRight size={15} /></button></div></header>
    <section className="site-page-content account-page"><nav className="page-breadcrumb"><button onClick={() => navigate('/')}>Workspace</button><span>/</span><strong>{settings ? 'Account settings' : 'Profile'}</strong></nav><span className="section-kicker">ACCOUNT · PRIVATE WORKSPACE</span><h1>{settings ? 'Account settings' : 'Your profile'}</h1><p className="page-lede">Manage your identity, sign-in credentials, and saved account data.</p>
      <div className="account-tabs"><button className={!settings ? 'selected' : ''} onClick={() => navigate('/profile')}><UserRound size={15} /> Profile</button><button className={settings ? 'selected' : ''} onClick={() => navigate('/settings')}><Settings size={15} /> Security & settings</button></div>
      {!settings ? <section className="account-panel"><div className="account-panel-heading"><span className="account-avatar">{profile.full_name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</span><div><h2>{profile.full_name}</h2><p>{profile.email}</p></div></div><form className="account-form" onSubmit={saveProfile}><label>Full name<input value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} required maxLength={100} autoComplete="name" /></label><label>Email address<input type="email" value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} required maxLength={254} autoComplete="email" /></label><button className="page-primary" disabled={busy === 'profile'}>{busy === 'profile' ? 'Saving…' : 'Save profile'} <ArrowRight size={16} /></button></form></section> : <><section className="account-panel"><div className="account-panel-heading"><div><span className="section-kicker">SIGN-IN SECURITY</span><h2>Change password</h2><p>Changing your password signs out any other active sessions.</p></div></div><form className="account-form" onSubmit={changePassword}><label>Current password<input type="password" value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} required autoComplete="current-password" maxLength={128} /></label><label>New password<input type="password" value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} required minLength={10} maxLength={128} autoComplete="new-password" /><small>Use at least 10 characters.</small></label><button className="page-primary" disabled={busy === 'password'}>{busy === 'password' ? 'Updating…' : 'Update password'} <ArrowRight size={16} /></button></form></section><section className="account-panel danger-panel"><div className="account-panel-heading"><div><span className="section-kicker">PERMANENT ACTION</span><h2>Delete account</h2><p>This removes your profile, sessions, and saved analysis history from the active database.</p></div></div><form className="account-form" onSubmit={deleteAccount}><label>Confirm your password<input type="password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} required autoComplete="current-password" maxLength={128} /></label><button className="danger-button" disabled={busy === 'delete'}>{busy === 'delete' ? 'Deleting…' : 'Delete account'} <Trash2 size={16} /></button></form></section></>}
      {notice && <div role="status" className={`form-notice ${notice.kind}`}>{notice.text}</div>}<button className="back-link" onClick={() => navigate('/') }><ArrowLeft size={15} /> Back to workspace</button>
    </section><footer className="site-page-footer"><span>VoiceShield · Account data stays scoped to this account.</span></footer>
  </main>
}

export function RecoveryPage({ path, navigate }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const isReset = path === '/reset-password'
  const token = new URLSearchParams(window.location.search).get('token') || ''
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setNotice(null)
    try {
      const result = isReset
        ? await api('/api/auth/password-reset/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, new_password: password }) })
        : await api('/api/auth/password-reset/request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) })
      setNotice({ kind: 'success', text: isReset ? 'Your password has been reset. You can now sign in.' : result.message })
      if (isReset) setPassword('')
    } catch (error) { setNotice({ kind: 'error', text: error.message }) } finally { setBusy(false) }
  }
  return <main className="auth-shell"><a className="brand auth-brand" href="/" onClick={(event) => { event.preventDefault(); navigate('/login') }}><span className="brand-mark"><Shield size={20} /><span className="brand-spark">✳</span></span><span>voice<span className="brand-bold">shield</span></span></a><section className="auth-card"><span className="section-kicker">ACCOUNT RECOVERY</span><h1>{isReset ? 'Choose a new password.' : 'Reset your password.'}</h1><p className="auth-subtitle">{isReset ? 'Reset links expire after 30 minutes and can be used once.' : 'We will email a one-time reset link if your account exists.'}</p><form className="auth-form" onSubmit={submit}>{isReset ? <label>New password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={10} maxLength={128} autoComplete="new-password" /></label> : <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={254} autoComplete="email" /></label>}{notice && <div role="status" className={`form-notice ${notice.kind}`}>{notice.text}</div>}<button className="analyze-button auth-submit" disabled={busy || (isReset && !token)}>{busy ? 'Working…' : isReset ? 'Reset password' : 'Send reset link'} <ArrowRight size={16} /></button></form><button className="back-link" onClick={() => navigate('/login')}><ArrowLeft size={15} /> Back to login</button></section><span className="auth-footer">VoiceShield · Secure account recovery</span></main>
}
