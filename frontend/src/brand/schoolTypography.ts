export const schoolFontOptions = [
  { name: 'Inter', family: 'Inter, system-ui, sans-serif' },
  { name: 'Arial', family: 'Arial, Helvetica, sans-serif' },
  { name: 'Verdana', family: 'Verdana, Geneva, sans-serif' },
  { name: 'Trebuchet MS', family: '"Trebuchet MS", Arial, sans-serif' },
  { name: 'Georgia', family: 'Georgia, serif' },
  { name: 'Times New Roman', family: '"Times New Roman", Times, serif' },
] as const

export function schoolFontFamily(name: string) {
  return schoolFontOptions.find((option) => option.name === name)?.family ?? schoolFontOptions[0].family
}
