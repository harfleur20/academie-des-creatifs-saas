import type { PublicFormation, PublicSession } from '../lib/api'

export type PublicCartItem = {
  schoolSlug: string
  formation: Pick<PublicFormation,'id'|'slug'|'title'|'cover_url'|'currency'>
  session: PublicSession
}

const KEY='academie_school_cart'

export function readPublicCart(): PublicCartItem[] {
  try {
    const raw=localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) as PublicCartItem[] : []
  } catch { return [] }
}

export function writePublicCart(items: PublicCartItem[]) {
  localStorage.setItem(KEY,JSON.stringify(items))
  window.dispatchEvent(new Event('school-cart-change'))
}

export function addPublicCartItem(item: PublicCartItem) {
  const current=readPublicCart().filter((entry)=>!(entry.schoolSlug===item.schoolSlug&&entry.session.id===item.session.id))
  writePublicCart([...current,item])
}

export function removePublicCartItem(schoolSlug:string,sessionId:number) {
  writePublicCart(readPublicCart().filter((entry)=>!(entry.schoolSlug===schoolSlug&&entry.session.id===sessionId)))
}
