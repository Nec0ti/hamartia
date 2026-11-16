import { useEffect, useState } from 'react'
import { useI18n } from '../i18n.jsx'
import socialClient from '../social/socialClient.js'

function payload(result) {
  return result.data ?? result.profile
}

export default function SocialForumPanel() {
  const { t, language } = useI18n()
  const [posts, setPosts] = useState([])
  const [queue, setQueue] = useState([])
  const [moderator, setModerator] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [retryAfter, setRetryAfter] = useState(null)
  const [submitted, setSubmitted] = useState(false)

  const refresh = async () => {
    const feed = await socialClient.listForumPosts()
    if (feed.status !== 'signedIn') throw new Error('forum unavailable')
    setPosts(payload(feed))
    const moderation = await socialClient.getModerationQueue()
    if (moderation.status === 'signedIn') {
      setModerator(true)
      setQueue(payload(moderation))
    } else if (moderation.status === 'forbidden') {
      setModerator(false)
      setQueue([])
    } else {
      throw new Error('forum unavailable')
    }
  }

  useEffect(() => {
    let active = true
    refresh().catch(() => { if (active) setError(true) })
    return () => { active = false }
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(false)
    setRetryAfter(null)
    setSubmitted(false)
    try {
      const result = await socialClient.createForumPost({ title, body })
      if (result.status === 'rateLimited') {
        setRetryAfter(result.retryAfterSeconds)
        return
      }
      if (result.status !== 'signedIn' || payload(result)?.status !== 'pending') throw new Error('submit failed')
      setTitle('')
      setBody('')
      setSubmitted(true)
      await refresh()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  const moderate = async (postId, decision) => {
    setBusy(true)
    setError(false)
    try {
      const result = await socialClient.moderateForumPost(postId, decision)
      if (result.status !== 'signedIn') throw new Error('moderation failed')
      await refresh()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-6 space-y-4 border-t border-canvas-line pt-5" aria-labelledby="social-forum-heading">
      <div>
        <h3 id="social-forum-heading" className="text-lg font-semibold text-canvas-text">{t('social.forumTitle')}</h3>
        <p className="mt-1 text-xs text-canvas-muted">{t('social.forumPrivacy')}</p>
      </div>
      <form onSubmit={submit} className="space-y-3 rounded-lg border border-canvas-line p-3">
        <label className="block text-sm text-canvas-muted">{t('social.postTitle')}
          <input required maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
        </label>
        <label className="block text-sm text-canvas-muted">{t('social.postBody')}
          <textarea required maxLength={5000} rows={3} value={body} onChange={(event) => setBody(event.target.value)} className="mt-1 w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-sm text-canvas-text" />
        </label>
        <button type="submit" disabled={busy} className="rounded-lg bg-canvas-text px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('social.postSubmit')}</button>
        {submitted && <p role="status" className="text-sm text-green-300">{t('social.postPending')}</p>}
      </form>
      {retryAfter !== null && <p role="alert" className="text-sm text-red-300">{t('social.rateLimited', { seconds: retryAfter })}</p>}
      {error && <p role="alert" className="text-sm text-red-300">{t('social.forumError')}</p>}
      <div className="space-y-3">
        {posts.map((post) => <article key={post.post_id} className="rounded-lg border border-canvas-line p-3">
          <h4 className="font-medium text-canvas-text">{post.title}</h4>
          <p className="mt-2 whitespace-pre-wrap text-sm text-canvas-muted">{post.body}</p>
          <time className="mt-2 block text-xs text-canvas-muted" dateTime={post.created_at}>{new Intl.DateTimeFormat(language === 'tr' ? 'tr-TR' : 'en', { dateStyle: 'medium' }).format(new Date(post.created_at))}</time>
        </article>)}
        {!posts.length && <p className="text-sm text-canvas-muted">{t('social.noApprovedPosts')}</p>}
      </div>
      {moderator && <section className="space-y-3 border-t border-canvas-line pt-4" aria-labelledby="social-moderation-heading">
        <h4 id="social-moderation-heading" className="font-semibold text-canvas-text">{t('social.moderationQueue')}</h4>
        {!queue.length && <p className="text-sm text-canvas-muted">{t('social.noPendingPosts')}</p>}
        {queue.map((post) => <article key={post.post_id} className="rounded-lg border border-canvas-line p-3">
          <h5 className="font-medium text-canvas-text">{post.title}</h5>
          <p className="mt-2 whitespace-pre-wrap text-sm text-canvas-muted">{post.body}</p>
          <div className="mt-3 flex gap-2">
            <button type="button" disabled={busy} onClick={() => moderate(post.post_id, 'approved')} className="rounded-lg bg-canvas-text px-3 py-1.5 text-sm text-canvas-base disabled:opacity-50">{t('social.approve')}</button>
            <button type="button" disabled={busy} onClick={() => moderate(post.post_id, 'rejected')} className="rounded-lg border border-canvas-line px-3 py-1.5 text-sm text-canvas-muted disabled:opacity-50">{t('social.reject')}</button>
          </div>
        </article>)}
      </section>}
    </section>
  )
}
