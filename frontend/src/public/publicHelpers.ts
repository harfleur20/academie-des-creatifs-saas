export function formatSchoolMoney(amount: number, currency: string) {
  if (currency === 'XAF') {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(amount) + ' XAF'
  }
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(amount / 100)
}

export function formatSchoolDate(value: string) {
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value + (value.length === 10 ? 'T12:00:00' : '')))
}
