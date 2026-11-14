export function formatSchoolMoney(amount: number, currency: string) {
  if (currency === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(amount) + ' FCFA'
  }
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(amount / 100)
}

/** 37.5 → "37,5 %". */
export function formatSchoolPercent(value: number) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(value) + ' %'
}

export function formatSchoolDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value + (value.length === 10 ? 'T12:00:00' : '')))
}
