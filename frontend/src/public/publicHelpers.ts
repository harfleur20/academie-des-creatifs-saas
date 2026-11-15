import type { SchoolCurrencyRates } from './currencyRates'

export function hasSchoolCurrencyRate(fromCurrency: string, toCurrency: string, rates: SchoolCurrencyRates | null) {
  const from = (fromCurrency || 'XAF').toUpperCase()
  const to = (toCurrency || from).toUpperCase()
  if (from === to) return true
  return Boolean(rates && (from === 'XAF' || rates.rates[from]) && (to === 'XAF' || rates.rates[to]))
}

export function formatSchoolMoney(
  amount: number,
  currency: string,
  displayCurrency = currency,
  rates: SchoolCurrencyRates | null = null,
) {
  const source = (currency || 'XAF').toUpperCase()
  const target = (displayCurrency || source).toUpperCase()
  const sourceMajor = source === 'XAF' ? amount : amount / 100

  let displayedMajor = sourceMajor
  if (source !== target) {
    const sourceRate = source === 'XAF' ? 1 : rates?.rates[source]
    const targetRate = target === 'XAF' ? 1 : rates?.rates[target]
    if (!sourceRate || !targetRate) {
      return formatNativeSchoolMoney(amount, source)
    }
    displayedMajor = sourceMajor / sourceRate * targetRate
  }

  if (target === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(displayedMajor) + ' FCFA'
  }
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: target,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(displayedMajor)
}

function formatNativeSchoolMoney(amount: number, currency: string) {
  if (currency === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(amount) + ' FCFA'
  }
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 2,
  }).format(amount / 100)
}

/** 37.5 → "37,5 %". */
export function formatSchoolPercent(value: number) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(value) + ' %'
}

export function formatSchoolDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value + (value.length === 10 ? 'T12:00:00' : '')))
}

export function formatSchoolRateDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value + 'T12:00:00'))
}
