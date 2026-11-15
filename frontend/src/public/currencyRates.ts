export const POPULAR_CURRENCIES = [
  { code: 'XAF', label: 'FCFA — Afrique centrale (XAF)' },
  { code: 'XOF', label: 'FCFA — Afrique de l’Ouest (XOF)' },
  { code: 'EUR', label: 'Euro (EUR)' },
  { code: 'USD', label: 'Dollar américain (USD)' },
  { code: 'GBP', label: 'Livre sterling (GBP)' },
  { code: 'CAD', label: 'Dollar canadien (CAD)' },
  { code: 'CHF', label: 'Franc suisse (CHF)' },
  { code: 'MAD', label: 'Dirham marocain (MAD)' },
  { code: 'NGN', label: 'Naira nigérian (NGN)' },
  { code: 'ZAR', label: 'Rand sud-africain (ZAR)' },
  { code: 'GHS', label: 'Cedi ghanéen (GHS)' },
  { code: 'AUD', label: 'Dollar australien (AUD)' },
  { code: 'CNY', label: 'Yuan chinois (CNY)' },
  { code: 'JPY', label: 'Yen japonais (JPY)' },
] as const

export type SchoolCurrencyRates = {
  base: 'XAF'
  date: string
  rates: Record<string, number>
}

type CachedSchoolCurrencyRates = {
  savedAt: number
  value: SchoolCurrencyRates
}

const CACHE_KEY = 'school-currency-rates-v1'
const REFRESH_AFTER_MS = 12 * 60 * 60 * 1000
const MAX_STALE_MS = 7 * 24 * 60 * 60 * 1000

function readCache(): CachedSchoolCurrencyRates | null {
  try {
    const cached = JSON.parse(window.localStorage.getItem(CACHE_KEY) || 'null') as CachedSchoolCurrencyRates | null
    if (!cached || !Number.isFinite(cached.savedAt) || cached.value?.base !== 'XAF' || !cached.value.rates) return null
    return cached
  } catch {
    return null
  }
}

export function getCachedSchoolCurrencyRates(): SchoolCurrencyRates | null {
  const cached = readCache()
  return cached && Date.now() - cached.savedAt <= MAX_STALE_MS ? cached.value : null
}

export async function loadSchoolCurrencyRates(): Promise<SchoolCurrencyRates | null> {
  const cached = readCache()
  if (cached && Date.now() - cached.savedAt < REFRESH_AFTER_MS) return cached.value

  try {
    const response = await fetch('https://api.frankfurter.dev/v2/rates?base=XAF', {
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) throw new Error(`Exchange rate request failed: ${response.status}`)

    const rows = await response.json() as Array<{ base: string; quote: string; rate: number; date: string }>
    const rates = Object.fromEntries(
      rows
        .filter((row) => row.base === 'XAF' && Number.isFinite(row.rate) && row.rate > 0)
        .map((row) => [row.quote.toUpperCase(), row.rate]),
    ) as Record<string, number>
    rates.XAF = 1
    if (!rates.EUR || !rates.USD) throw new Error('The exchange rate response is incomplete.')

    const value: SchoolCurrencyRates = {
      base: 'XAF',
      date: rows[0]?.date || new Date().toISOString().slice(0, 10),
      rates,
    }
    try {
      window.localStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), value } satisfies CachedSchoolCurrencyRates))
    } catch { /* A blocked or full local cache should not prevent public browsing. */ }
    return value
  } catch {
    return cached && Date.now() - cached.savedAt <= MAX_STALE_MS ? cached.value : null
  }
}
