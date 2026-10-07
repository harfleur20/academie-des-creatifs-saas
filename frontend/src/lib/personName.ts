export function formatPersonName(name?: string | null) {
  const normalized = (name || '').trim().replace(/\s+/g, ' ')
  if (!normalized) return ''

  return normalized
    .toLocaleLowerCase('fr-FR')
    .replace(
      /(^|[\s'’\-])(\p{L})/gu,
      (_match, prefix: string, letter: string) =>
        prefix + letter.toLocaleUpperCase('fr-FR'),
    )
}
