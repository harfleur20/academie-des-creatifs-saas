import './person-avatar.css'

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

/** A person's photo, or their initials when they have none. */
export function PersonAvatar({ name, url, size = 34 }: { name: string; url?: string | null; size?: number }) {
  const style = { width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.32)) }
  return url
    ? <img className="person-avatar" src={url} alt="" style={style} />
    : <span className="person-avatar person-avatar--initials" aria-hidden="true" style={style}>{initials(name)}</span>
}

/** A name with its avatar, for the lists of students. */
export function PersonName({ name, url }: { name: string; url?: string | null }) {
  return <strong className="person-name"><PersonAvatar name={name} url={url} />{name}</strong>
}
