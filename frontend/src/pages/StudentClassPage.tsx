import { useEffect, useState, type ChangeEvent } from 'react'
import { ImagePlus, MessageCircle, Send, Users } from 'lucide-react'
import {
  ApiError,
  createClassDiscussionPost,
  createClassDiscussionReply,
  listClassDiscussion,
  listStudentClasses,
  uploadAssignmentAsset,
  type DiscussionPost,
  type StudentClass,
} from '../lib/api'

export function StudentClassPage() {
  const [classes,setClasses]=useState<StudentClass[]>([])
  const [sessionId,setSessionId]=useState<number|null>(null)
  const [posts,setPosts]=useState<DiscussionPost[]>([])
  const [draft,setDraft]=useState('')
  const [imageUrl,setImageUrl]=useState('')
  const [replyDrafts,setReplyDrafts]=useState<Record<number,string>>({})
  const [error,setError]=useState('')
  const [working,setWorking]=useState(false)

  useEffect(()=>{listStudentClasses().then((rows)=>{setClasses(rows);setSessionId(rows[0]?.session_id??null)}).catch((err)=>setError(err instanceof ApiError?err.message:'Chargement impossible.'))},[])
  useEffect(()=>{if(sessionId)listClassDiscussion(sessionId).then(setPosts).catch((err)=>setError(err instanceof ApiError?err.message:'Discussion indisponible.'))},[sessionId])
  const current=classes.find((item)=>item.session_id===sessionId)??null

  async function uploadImage(event:ChangeEvent<HTMLInputElement>){const file=event.target.files?.[0];event.target.value='';if(!file)return;setWorking(true);try{const asset=await uploadAssignmentAsset(file);setImageUrl(asset.public_url)}catch(err){setError(err instanceof ApiError?err.message:'Upload impossible.')}finally{setWorking(false)}}
  async function publish(){if(!sessionId||(!draft.trim()&&!imageUrl))return;setWorking(true);try{const created=await createClassDiscussionPost(sessionId,{body:draft.trim(),image_url:imageUrl||null});setPosts((rows)=>[created,...rows]);setDraft('');setImageUrl('')}catch(err){setError(err instanceof ApiError?err.message:'Publication impossible.')}finally{setWorking(false)}}
  async function reply(postId:number){if(!sessionId)return;const body=(replyDrafts[postId]||'').trim();if(!body)return;try{const created=await createClassDiscussionReply(sessionId,postId,{body});setPosts((rows)=>rows.map((post)=>post.id===postId?{...post,replies:[...post.replies,created]}:post));setReplyDrafts((x)=>({...x,[postId]:''}))}catch(err){setError(err instanceof ApiError?err.message:'Réponse impossible.')}}

  return <main className="app-page academic-page">
    <header className="app-page-header"><div><span className="page-kicker">Espace étudiant</span><h1>Ma classe</h1><p>Retrouvez votre cohorte et échangez avec votre classe.</p></div></header>
    {error&&<div className="form-error">{error}</div>}
    <label className="academic-session-select">Classe<select value={sessionId??''} onChange={(event)=>setSessionId(Number(event.target.value))}>{classes.map((item)=><option key={item.session_id} value={item.session_id}>{item.formation_title} · {item.session_label}</option>)}</select></label>
    {current&&<section className="class-layout">
      <aside className="app-card class-roster"><div className="settings-section-heading"><div><span className="section-label">Cohorte</span><h2>{current.classmates.length} étudiant(s)</h2></div><Users size={18}/></div>{current.classmates.map((mate)=><div className={'classmate-row '+(mate.is_current_user?'is-me':'')} key={mate.enrollment_id}><div className="roster-avatar">{mate.full_name.split(' ').slice(0,2).map((part)=>part[0]).join('').toUpperCase()}</div><div><strong>{mate.full_name}{mate.is_current_user?' · Vous':''}</strong><small>{mate.badge.label} · {mate.badge.score_pct}%</small></div></div>)}</aside>
      <section className="class-discussion">
        <div className="app-card class-composer"><textarea value={draft} onChange={(event)=>setDraft(event.target.value)} placeholder="Question, remarque, partage avec la classe…"/>{imageUrl&&<img src={imageUrl} alt="Aperçu"/>}<div><label className="secondary-button compact-action"><ImagePlus size={13}/> Image<input type="file" accept="image/*" onChange={(event)=>void uploadImage(event)}/></label><button className="primary-button compact-action" type="button" disabled={working||(!draft.trim()&&!imageUrl)} onClick={()=>void publish()}><Send size={13}/> Publier</button></div></div>
        <div className="class-post-list">{posts.map((post)=><article className="app-card class-post" key={post.id}><header><div className="roster-avatar">{post.author.full_name.split(' ').slice(0,2).map((part)=>part[0]).join('').toUpperCase()}</div><div><strong>{post.author.full_name}</strong><small>{post.author.role} · {new Date(post.created_at).toLocaleString('fr-FR')}</small></div></header>{post.body&&<p>{post.body}</p>}{post.image_url&&<img src={post.image_url} alt="Publication"/>}<div className="class-replies">{post.replies.map((reply)=><div key={reply.id}><strong>{reply.author.full_name}</strong><span>{reply.body}</span><small>{new Date(reply.created_at).toLocaleString('fr-FR')}</small></div>)}</div><div className="class-reply-box"><input value={replyDrafts[post.id]||''} onChange={(event)=>setReplyDrafts((x)=>({...x,[post.id]:event.target.value}))} placeholder="Répondre…"/><button type="button" onClick={()=>void reply(post.id)}><MessageCircle size={13}/></button></div></article>)}</div>
      </section>
    </section>}
  </main>
}
