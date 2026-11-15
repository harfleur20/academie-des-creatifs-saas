export const FORMATION_CHARACTER_LIMITS = {
  title: 120,
  category: 60,
  level: 40,
  shortDescription: 220,
  description: 3000,
  objectives: 1500,
  objective: 180,
  prerequisites: 1000,
  programIntro: 600,
  programModuleTitle: 100,
  programChapterTitle: 100,
  programLessonTitle: 120,
  serializedProgram: 30_000,
} as const

/** Count Unicode code points so the browser and Python API agree on limits. */
export function characterCount(value: string) {
  return Array.from(value).length
}

export function exceedsCharacterLimit(value: string, limit: number) {
  return characterCount(value) > limit
}
