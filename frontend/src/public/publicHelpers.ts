import { activeSchoolLocale } from '../app/schoolLocale'
import { CFA_PER_EURO, type SchoolCurrencyRates } from './currencyRates'

export function hasSchoolCurrencyRate(fromCurrency: string, toCurrency: string, rates: SchoolCurrencyRates | null) {
  const from = (fromCurrency || 'XAF').toUpperCase()
  const to = (toCurrency || from).toUpperCase()
  if (from === to) return true
  if ((from === 'XAF' || from === 'XOF') && to === 'EUR') return true
  if (from === 'EUR' && (to === 'XAF' || to === 'XOF')) return true
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
    const ratePerXaf = (currency: string) => {
      if (currency === 'XAF' || currency === 'XOF') return 1
      if (currency === 'EUR') return 1 / CFA_PER_EURO
      return rates?.rates[currency]
    }
    const sourceRate = ratePerXaf(source)
    const targetRate = ratePerXaf(target)
    if (!sourceRate || !targetRate) {
      return formatNativeSchoolMoney(amount, source)
    }
    displayedMajor = sourceMajor / sourceRate * targetRate
  }

  if (target === 'XAF') {
    return new Intl.NumberFormat(activeSchoolLocale(), { maximumFractionDigits: 0 }).format(displayedMajor) + ' FCFA'
  }
  return new Intl.NumberFormat(activeSchoolLocale(), {
    style: 'currency',
    currency: target,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(displayedMajor)
}

function formatNativeSchoolMoney(amount: number, currency: string) {
  if (currency === 'XAF') {
    return new Intl.NumberFormat(activeSchoolLocale(), { maximumFractionDigits: 0 }).format(amount) + ' FCFA'
  }
  return new Intl.NumberFormat(activeSchoolLocale(), {
    style: 'currency', currency, minimumFractionDigits: 0, maximumFractionDigits: 2,
  }).format(amount / 100)
}

/** 37.5 → "37,5 %". */
export function formatSchoolPercent(value: number) {
  return new Intl.NumberFormat(activeSchoolLocale(), { maximumFractionDigits: 1 }).format(value) + ' %'
}

export function formatSchoolDate(value: string) {
  return new Intl.DateTimeFormat(activeSchoolLocale(), { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value + (value.length === 10 ? 'T12:00:00' : '')))
}

export function formatSchoolRateDate(value: string) {
  return new Intl.DateTimeFormat(activeSchoolLocale(), { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value + 'T12:00:00'))
}
