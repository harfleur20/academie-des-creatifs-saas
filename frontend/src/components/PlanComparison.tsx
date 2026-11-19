import { useState, type ReactNode } from 'react'
import { Check, Minus } from 'lucide-react'
import type { Plan } from '../lib/api'
import { comparisonRows, type ComparisonCell } from '../lib/planFeatures'
import '../plan-comparison.css'

function Cell({ value }: { value: ComparisonCell }) {
  if (value === true) return <Check size={17} aria-label="Inclus" className="plan-compare__yes" />
  if (value === false) return <Minus size={16} aria-label="Non inclus" className="plan-compare__no" />
  return <>{value}</>
}

/** Every plan side by side, row by row; folded under the plan cards so they stay short. */
export function PlanComparison({
  plans,
  highlight,
  onOpenChange,
  action,
}: {
  plans: Plan[]
  highlight?: string | null
  onOpenChange?: (open: boolean) => void
  action?: ReactNode
}) {
  const [open, setOpen] = useState(true)
  const rows = comparisonRows(plans)
  if (plans.length === 0 || rows.length === 0) return null

  const toggleOpen = () => {
    const nextOpen = !open
    setOpen(nextOpen)
    onOpenChange?.(nextOpen)
  }

  return (
    <div className="plan-compare">
      <div className="plan-compare__toolbar">
        <button
          className="plan-compare__toggle"
          type="button"
          aria-expanded={open}
          aria-controls="plan-comparison-table"
          onClick={toggleOpen}
        >
          Comparer les forfaits en détail
        </button>
        {action}
      </div>
      <div
        className={`plan-compare__panel${open ? ' is-open' : ''}`}
        id="plan-comparison-table"
        aria-hidden={!open}
      >
        <div className="plan-compare__scroll">
          <table>
            <thead>
              <tr>
                <th scope="col"><span className="plan-compare__hidden">Fonctionnalité</span></th>
                {plans.map((plan) => (
                  <th scope="col" className={plan.code === highlight ? 'is-highlight' : undefined} key={plan.id}>{plan.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}
                    {row.soon && <em className="plan-compare__soon">Bientôt</em>}
                  </th>
                  {plans.map((plan) => (
                    <td className={plan.code === highlight ? 'is-highlight' : undefined} key={plan.id}>
                      <Cell value={row.cell(plan)} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
