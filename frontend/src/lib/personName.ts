import { activeSchoolLocale } from '../app/schoolLocale'
export function formatPersonName(name?: string | null) {
  const normalized = (name || '').trim().replace(/\s+/g, ' ')
  if (!normalized) return ''

  return normalized
    .toLocaleLowerCase(activeSchoolLocale())
    .replace(
      /(^|[\s'’\-])(\p{L})/gu,
      (_match, prefix: string, letter: string) =>
        prefix + letter.toLocaleUpperCase(activeSchoolLocale()),
    )
}
