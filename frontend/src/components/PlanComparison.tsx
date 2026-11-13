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
export function PlanComparison({ plans, highlight }: { plans: Plan[]; highlight?: string | null }) {
  const rows = comparisonRows(plans)
  if (plans.length === 0 || rows.length === 0) return null

  return (
    <details className="plan-compare">
      <summary>Comparer les forfaits en détail</summary>
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
    </details>
  )
}
