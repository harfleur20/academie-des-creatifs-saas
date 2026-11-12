import { useEffect, useState } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
import {
  ApiError,
  listAdminAddons,
  listAdminPlans,
  replaceAdminPlanEntitlements,
  updateAdminAddon,
  updateAdminPlan,
  type Addon,
  type AdminPlan,
  type AdminPlanEntitlement,
} from '../lib/api'

function emptyEntitlement(): AdminPlanEntitlement {
  return {
    feature_key: '',
    enabled: true,
    limit_value: null,
  }
}

export function AdminPlansPage() {
  const [plans, setPlans] = useState<AdminPlan[]>([])
  const [addons, setAddons] = useState<Addon[]>([])
  const [savingAddon, setSavingAddon] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [savingPlanId, setSavingPlanId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    listAdminAddons().then(setAddons).catch(() => setAddons([]))
    listAdminPlans()
      .then(setPlans)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : 'Impossible de charger les forfaits.',
        ),
      )
  }, [])

  function updateLocalPlan(planId: number, patch: Partial<AdminPlan>) {
    setPlans((items) =>
      items.map((item) => item.id === planId ? { ...item, ...patch } : item),
    )
  }

  function updateEntitlement(
    planId: number,
    index: number,
    patch: Partial<AdminPlanEntitlement>,
  ) {
    setPlans((items) =>
      items.map((item) => {
        if (item.id !== planId) return item
        return {
          ...item,
          entitlements: item.entitlements.map((entitlement, itemIndex) =>
            itemIndex === index
              ? { ...entitlement, ...patch }
              : entitlement,
          ),
        }
      }),
    )
  }

  async function savePlan(plan: AdminPlan) {
    if (reason.trim().length < 3) {
      setError('Indiquez un motif pour enregistrer une modification commerciale.')
      return
    }

    const invalidFeature = plan.entitlements.some(
      (item) => !/^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(item.feature_key),
    )
    if (invalidFeature) {
      setError('Chaque clé de fonctionnalité doit être au format snake_case.')
      return
    }

    setSavingPlanId(plan.id)
    setError('')
    setMessage('')
    try {
      const updated = await updateAdminPlan(
        plan.id,
        {
          name: plan.name,
          description: plan.description,
          currency: plan.currency,
          monthly_price_cents: plan.monthly_price_cents,
          annual_price_cents: plan.annual_price_cents,
          trial_days: plan.trial_days,
          is_public: plan.is_public,
          is_active: plan.is_active,
          sales_commission_bps: plan.sales_commission_bps,
        },
        reason.trim(),
      )
      const withEntitlements = await replaceAdminPlanEntitlements(
        plan.id,
        plan.entitlements,
        reason.trim(),
      )
      setPlans((items) =>
        items.map((item) =>
          item.id === plan.id
            ? { ...updated, entitlements: withEntitlements.entitlements }
            : item,
        ),
      )
      setMessage(`Forfait ${plan.name} enregistré.`)
      setReason('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSavingPlanId(null)
    }
  }

  async function saveAddon(addon: Addon) {
    if (reason.trim().length < 3) {
      setError('Indiquez un motif pour enregistrer une modification commerciale.')
      return
    }
    setSavingAddon(addon.code)
    setError('')
    setMessage('')
    try {
      const updated = await updateAdminAddon(addon.code, {
        name: addon.name,
        description: addon.description,
        unit_price_cents: addon.unit_price_cents,
        status: addon.status,
        plan_codes: addon.plan_codes,
      }, reason.trim())
      setAddons((items) => items.map((item) => (item.code === updated.code ? updated : item)))
      setMessage(`Option ${updated.name} enregistrée.`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSavingAddon(null)
    }
  }

  function updateLocalAddon(code: string, patch: Partial<Addon>) {
    setAddons((items) => items.map((item) => (item.code === code ? { ...item, ...patch } : item)))
  }

  return (
    <main className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="page-kicker">Commercial</span>
          <h1>Plans & quotas</h1>
          <p>
            Configurez les tarifs, périodes d’essai et droits sans modifier le code.
          </p>
        </div>
      </header>

      <section className="admin-plan-reason">
        <label>
          Motif des modifications
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            placeholder="Ex. Nouvelle grille commerciale octobre 2026"
          />
        </label>
        <small>Le motif est enregistré dans le journal d’audit plateforme.</small>
      </section>

      {message && <div className="form-success">{message}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="admin-plan-list">
        {plans.map((plan) => (
          <section className="admin-card admin-plan-card" key={plan.id}>
            <div className="admin-plan-heading">
              <div>
                <span className="section-label">{plan.code}</span>
                <input
                  className="admin-plan-name-input"
                  value={plan.name}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, { name: event.target.value })
                  }
                />
              </div>
              <div className="admin-plan-toggles">
                <label>
                  <input
                    type="checkbox"
                    checked={plan.is_public}
                    onChange={(event) =>
                      updateLocalPlan(plan.id, { is_public: event.target.checked })
                    }
                  />
                  Public
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={plan.is_active}
                    onChange={(event) =>
                      updateLocalPlan(plan.id, { is_active: event.target.checked })
                    }
                  />
                  Actif
                </label>
              </div>
            </div>

            <textarea
              className="admin-plan-description"
              value={plan.description}
              maxLength={2000}
              onChange={(event) =>
                updateLocalPlan(plan.id, { description: event.target.value })
              }
              placeholder="Description du forfait"
            />

            <div className="admin-plan-pricing-grid">
              <label>
                Devise
                <input
                  value={plan.currency}
                  maxLength={3}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, {
                      currency: event.target.value.toUpperCase(),
                    })
                  }
                />
              </label>
              <label>
                Prix mensuel
                <input
                  type="number"
                  min={0}
                  value={plan.monthly_price_cents ?? ''}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, {
                      monthly_price_cents:
                        event.target.value === ''
                          ? null
                          : Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                Prix annuel
                <input
                  type="number"
                  min={0}
                  value={plan.annual_price_cents ?? ''}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, {
                      annual_price_cents:
                        event.target.value === ''
                          ? null
                          : Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                Essai (jours)
                <input
                  type="number"
                  min={0}
                  max={365}
                  value={plan.trial_days}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, {
                      trial_days: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                Commission sur les ventes (%)
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={0.5}
                  value={plan.sales_commission_bps / 100}
                  onChange={(event) =>
                    updateLocalPlan(plan.id, {
                      sales_commission_bps: Math.round(Number(event.target.value) * 100),
                    })
                  }
                />
              </label>
            </div>

            <div className="admin-entitlements">
              <div className="admin-entitlements-heading">
                <div>
                  <strong>Fonctionnalités & quotas</strong>
                  <small>Une limite vide signifie que la fonctionnalité n’a pas de quota numérique.</small>
                </div>
                <button
                  type="button"
                  className="secondary-button compact-action"
                  onClick={() =>
                    updateLocalPlan(plan.id, {
                      entitlements: [...plan.entitlements, emptyEntitlement()],
                    })
                  }
                >
                  <Plus size={14} />
                  Ajouter
                </button>
              </div>

              {plan.entitlements.map((entitlement, index) => (
                <div className="admin-entitlement-row" key={`${plan.id}-${index}`}>
                  <input
                    value={entitlement.feature_key}
                    placeholder="students"
                    onChange={(event) =>
                      updateEntitlement(plan.id, index, {
                        feature_key: event.target.value.toLowerCase(),
                      })
                    }
                  />
                  <label>
                    <input
                      type="checkbox"
                      checked={entitlement.enabled}
                      onChange={(event) =>
                        updateEntitlement(plan.id, index, {
                          enabled: event.target.checked,
                        })
                      }
                    />
                    Activé
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={entitlement.limit_value ?? ''}
                    placeholder="Illimité"
                    onChange={(event) =>
                      updateEntitlement(plan.id, index, {
                        limit_value:
                          event.target.value === ''
                            ? null
                            : Number(event.target.value),
                      })
                    }
                  />
                  <button
                    type="button"
                    className="icon-button danger-icon"
                    onClick={() =>
                      updateLocalPlan(plan.id, {
                        entitlements: plan.entitlements.filter(
                          (_, itemIndex) => itemIndex !== index,
                        ),
                      })
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}

              {plan.entitlements.length === 0 && (
                <div className="empty-row">
                  Aucun droit configuré pour ce forfait.
                </div>
              )}
            </div>

            <div className="admin-plan-actions">
              <button
                className="primary-button"
                type="button"
                disabled={savingPlanId === plan.id}
                onClick={() => void savePlan(plan)}
              >
                <Save size={16} />
                {savingPlanId === plan.id ? 'Enregistrement…' : 'Enregistrer le forfait'}
              </button>
            </div>
          </section>
        ))}
      </div>

      <section className="admin-card admin-addons">
        <div className="admin-entitlements-heading">
          <div>
            <strong>Options à l’unité</strong>
            <small>Facturées sur le prochain paiement de l’école, par unité au-delà de son forfait.</small>
          </div>
        </div>
        {addons.map((addon) => (
          <div className="admin-addon-row" key={addon.code}>
            <input value={addon.name} onChange={(event) => updateLocalAddon(addon.code, { name: event.target.value })} />
            <label>
              Prix / {addon.unit_label} / mois (FCFA)
              <input
                type="number"
                min={0}
                value={addon.unit_price_cents ?? ''}
                placeholder="—"
                onChange={(event) => updateLocalAddon(addon.code, { unit_price_cents: event.target.value === '' ? null : Number(event.target.value) })}
              />
            </label>
            <label>
              Statut
              <select value={addon.status} onChange={(event) => updateLocalAddon(addon.code, { status: event.target.value as Addon['status'] })}>
                <option value="active">Active</option>
                <option value="coming_soon">Bientôt</option>
                <option value="inactive">Masquée</option>
              </select>
            </label>
            <label>
              Forfaits
              <input
                value={addon.plan_codes.join(', ')}
                onChange={(event) => updateLocalAddon(addon.code, { plan_codes: event.target.value.split(',').map((code) => code.trim()).filter(Boolean) })}
              />
            </label>
            <button className="secondary-button" type="button" disabled={savingAddon === addon.code} onClick={() => void saveAddon(addon)}>
              <Save size={15} />
              {savingAddon === addon.code ? '…' : 'Enregistrer'}
            </button>
          </div>
        ))}
      </section>
    </main>
  )
}
