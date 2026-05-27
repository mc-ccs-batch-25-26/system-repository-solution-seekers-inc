import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { residentProfilesApi } from '../../api/beneficiaries'
import { cyclesApi } from '../../api/cycles'
import { Skeleton, SkeletonForm } from '../../components/common/Skeleton'

const EMPLOYMENT_LABELS = {
  unemployed: 'Unemployed',
  displaced_terminated: 'Displaced/Terminated',
  underemployed: 'Underemployed',
  self_employed_informal: 'Self-Employed/Informal',
  employed: 'Employed',
  student: 'Student',
  retired: 'Retired',
  pwd_unable_to_work: 'PWD / Unable to Work',
}

const HOUSING_LABELS = {
  makeshift: 'Makeshift / Informal Settler',
  semi_permanent: 'Semi-Permanent',
  permanent_deteriorating: 'Permanent but Deteriorating',
  permanent_good: 'Permanent Good Condition',
  informal_settler: 'Informal Settler',
  semi_permanent_housing: 'Semi-Permanent Housing',
  permanent_good_condition: 'Permanent Housing (Good Condition)',
  permanent_needs_repair: 'Permanent Housing (Needs Repair)',
  under_construction: 'Under Construction',
  condemned_unsafe: 'Condemned / Unsafe Structure',
}

const STRUCTURE_LABELS = {
  concrete: 'Concrete House (Concrete Structure)',
  semi_concrete: 'Semi-Concrete House (Concrete and Wood Combination)',
  wooden: 'Wooden House (Primarily Wood Materials)',
  light_materials: 'Light Materials House (Nipa, Bamboo, Yero, Plywood, etc.)',
  mixed_materials: 'Mixed Materials House (Combination of Various Materials)',
}

const TENURE_LABELS = {
  homeowner: 'Homeowner',
  renter_tenant: 'Renter / Tenant',
  living_with_relatives: 'Living with Relatives',
  informal_settler: 'Informal Settler',
  government_housing_beneficiary: 'Government Housing Beneficiary',
}

const ELECTRICAL_LABELS = {
  legal_canoreco: 'Legally Connected to Electric Utility (CANORECO)',
  shared_meter: 'Shared Meter / Sub-metered Connection',
  unauthorized_connection: 'Unauthorized Electrical Connection',
  no_service: 'No Electrical Service Access',
  unstable_supply: 'Unstable Electrical Supply',
}

const WATER_LABELS = {
  private_connection: 'Private Water Connection',
  shared_connection: 'Shared Water Connection',
  community_system: 'Community Water System',
  deep_well: 'Deep Well / Own Well',
  hand_pump: 'Hand Pump',
  refilling_station: 'Water Refilling Station',
  no_regular_supply: 'No Regular Water Supply',
}

const SECTOR_LABELS = {
  PWD: 'Person with Disability (PWD)',
  SOLO_PARENT: 'Solo Parent',
  SENIOR: 'Senior Citizen (60+)',
  '4PS': '4Ps Beneficiary',
  IP: 'Indigenous People',
  YOUTH: 'Youth (15-30)',
  LACTATING: 'Lactating / Pregnant Mother',
  OFW: 'OFW Family Member',
}

function initials(name = '') {
  return name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
}

function display(value, fallback = '--') {
  return value === null || value === undefined || value === '' ? fallback : value
}

function money(value) {
  if (value === null || value === undefined || value === '') return '--'
  return `PHP ${Number(value).toLocaleString('en-PH', { minimumFractionDigits: 2 })}`
}

function dateText(value) {
  if (!value) return '--'
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-PH', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function titleCase(value = '') {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function BeneficiaryDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [error, setError] = useState('')
  const [historyError, setHistoryError] = useState('')

  useEffect(() => {
    residentProfilesApi.get(id)
      .then(setData)
      .catch(() => setError('Failed to load resident profile.'))

    cyclesApi.listParticipation({ beneficiary: id, page_size: 100 })
      .then((rows) => setHistory(rows.results ?? rows))
      .catch(() => setHistoryError('Failed to load TUPAD history.'))
      .finally(() => setLoadingHistory(false))
  }, [id])

  if (error) {
    return (
      <div className="max-w-3xl">
        <div className="alert-error">{error}</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="max-w-6xl space-y-5">
        <Skeleton className="h-32 w-full" />
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="card p-6"><SkeletonForm fields={8} /></div>
          <div className="card p-6"><SkeletonForm fields={5} /></div>
        </div>
      </div>
    )
  }

  const sectors = data.sectors ?? []
  const totalDays = history.reduce((sum, row) => sum + Number(row.days_worked ?? 0), 0)
  const latestRecord = history[0]

  return (
    <div className="max-w-6xl space-y-5">
      <button onClick={() => navigate('/official/resident-profiles')} className="btn-ghost -ml-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
        </svg>
        Back to Resident Profiles
      </button>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-slate-50 px-5 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-primary-100 text-xl font-bold text-primary-700">
                {initials(data.full_name)}
              </div>
              <div className="min-w-0">
                <p className="page-section-label">Resident Profile</p>
                <h1 className="mt-1 text-2xl font-bold text-ink-900">{data.full_name}</h1>
                <p className="mt-1 text-sm text-ink-500">
                  {titleCase(data.role)} | Household {display(data.household_code)}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className={`badge ${data.is_tupad_eligible ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-ink-500'}`}>
                {data.is_tupad_eligible ? 'TUPAD Eligible' : 'Not Eligible'}
              </span>
              {data.is_household_head && <span className="badge bg-blue-100 text-blue-700">Household Head</span>}
              <button onClick={() => navigate(`/official/resident-profiles/${id}/edit`)} className="btn-primary">
                Edit Profile
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-0 lg:grid-cols-4">
          <Metric label="Age" value={data.age != null ? `${data.age}` : '--'} note="years old" />
          <Metric label="Participation" value={history.length} note="recorded cycles" />
          <Metric label="Days Worked" value={totalDays} note="total TUPAD days" />
          <Metric label="Latest Project" value={latestRecord?.project_name ?? '--'} compact />
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <main className="space-y-5">
          <DetailSection title="Household Assignment">
            <InfoGrid>
              <Info label="Household Code" value={data.household_code} mono />
              <Info label="Family" value={data.family_detail ? `Family ${data.family_detail.family_number}` : null} />
              <Info label="Role" value={titleCase(data.role)} />
              <Info label="Household Head" value={data.is_household_head ? 'Yes' : 'No'} />
            </InfoGrid>
          </DetailSection>

          <DetailSection title="Profile Information">
            <InfoGrid>
              <Info label="Full Name" value={data.full_name} />
              <Info label="Birthdate" value={dateText(data.birthdate)} />
              <Info label="Gender" value={titleCase(data.gender)} />
              <Info label="Civil Status" value={titleCase(data.civil_status)} />
              <Info label="Contact Number" value={data.contact_number} />
              <Info label="Address" value={data.address} wide />
            </InfoGrid>
          </DetailSection>

          <DetailSection title="TUPAD Socio-Economic Profile">
            <InfoGrid>
              <Info label="Employment Status" value={EMPLOYMENT_LABELS[data.employment_status] ?? data.employment_status} />
              <Info label="Monthly Income" value={money(data.monthly_income)} />
              <Info label="Lot Area" value={data.lot_area_sqm != null ? `${data.lot_area_sqm} sqm` : null} />
              <Info label="Dependents" value={data.num_dependents} />
              <Info label="Housing Condition" value={HOUSING_LABELS[data.housing_condition] ?? data.housing_condition} wide />
              <Info label="Structure Condition" value={STRUCTURE_LABELS[data.structure_condition] ?? data.structure_condition} wide />
              <Info label="Tenure Status" value={TENURE_LABELS[data.tenure_status] ?? data.tenure_status} />
              <Info label="Electrical Condition" value={ELECTRICAL_LABELS[data.electrical_condition] ?? data.electrical_condition} wide />
              <Info label="Water Source" value={WATER_LABELS[data.water_source] ?? data.water_source} />
            </InfoGrid>
          </DetailSection>

          <DetailSection title="TUPAD Participation History">
            {historyError && <div className="alert-error">{historyError}</div>}
            {loadingHistory ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : history.length === 0 ? (
              <EmptyState title="No TUPAD history yet" text="Participation records will appear here once this resident completes a recorded TUPAD cycle." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr>
                      {['Cycle', 'Project', 'Days', 'Period', 'Recorded By'].map((heading, index) => (
                        <th key={heading} className={`border-b border-slate-200 bg-slate-50 px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400 ${index < 2 ? 'text-left' : 'text-center'}`}>
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-50 align-top">
                        <td className="border-b border-slate-100 px-4 py-3 font-semibold text-ink-900">{row.cycle_name}</td>
                        <td className="border-b border-slate-100 px-4 py-3 text-ink-600">
                          <p>{row.project_name}</p>
                          {row.daily_records?.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {row.daily_records.map((daily) => (
                                <span key={daily.id} className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                  daily.status === 'present'
                                    ? 'bg-emerald-100 text-emerald-700'
                                    : daily.status === 'excused'
                                      ? 'bg-blue-100 text-blue-700'
                                      : 'bg-slate-100 text-ink-500'
                                }`}>
                                  {dateText(daily.work_date)}: {daily.status}
                                </span>
                              ))}
                            </div>
                          )}
                          {row.daily_records?.some((daily) => daily.photo_url) && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {row.daily_records.filter((daily) => daily.photo_url).map((daily) => (
                                <a key={`${daily.id}-photo`} href={daily.photo_url} target="_blank" rel="noreferrer" className="text-[11px] font-semibold text-primary-600 hover:text-primary-800">
                                  Photo {dateText(daily.work_date)}
                                </a>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="border-b border-slate-100 px-4 py-3 text-center font-semibold text-primary-700">{row.days_worked}</td>
                        <td className="border-b border-slate-100 px-4 py-3 text-center text-xs text-ink-500">
                          {dateText(row.participation_start)} to {dateText(row.participation_end)}
                        </td>
                        <td className="border-b border-slate-100 px-4 py-3 text-center text-xs text-ink-500">{row.recorded_by_name ?? '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </DetailSection>
        </main>

        <aside className="space-y-5">
          <DetailSection title="Sector Membership">
            {sectors.length === 0 ? (
              <EmptyState title="No sectors recorded" text="No priority sector membership has been encoded for this resident." compact />
            ) : (
              <div className="flex flex-wrap gap-2">
                {sectors.map((sector) => (
                  <span key={sector} className="badge bg-blue-50 text-blue-700">{SECTOR_LABELS[sector] ?? sector}</span>
                ))}
              </div>
            )}
          </DetailSection>

          <DetailSection title="Staff Notes">
            <div className="space-y-3 text-sm text-ink-600">
              <p>This view is read-only except for profile edits. Participation records are created from the Participation module.</p>
              <p>Use the history section to verify prior TUPAD participation before reviewing future program cycle applications.</p>
            </div>
          </DetailSection>
        </aside>
      </div>
    </div>
  )
}

function DetailSection({ title, children }) {
  return (
    <section className="card overflow-hidden">
      <div className="border-b border-slate-100 bg-white px-5 py-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-ink-700">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function InfoGrid({ children }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>
}

function Info({ label, value, mono, wide }) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 ${wide ? 'sm:col-span-2' : ''}`}>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</p>
      <p className={`mt-1 text-sm font-semibold text-ink-900 ${mono ? 'font-mono' : ''}`}>{display(value)}</p>
    </div>
  )
}

function Metric({ label, value, note, compact }) {
  return (
    <div className="border-t border-slate-100 px-5 py-4 lg:border-t-0 lg:border-r last:border-r-0">
      <p className={`${compact ? 'truncate text-lg' : 'text-2xl'} font-bold text-ink-900`}>{value}</p>
      <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</p>
      {note && <p className="mt-1 text-xs text-ink-400">{note}</p>}
    </div>
  )
}

function EmptyState({ title, text, compact }) {
  return (
    <div className={`rounded-lg border border-dashed border-slate-200 bg-slate-50 text-center ${compact ? 'px-3 py-4' : 'px-5 py-10'}`}>
      <p className="text-sm font-semibold text-ink-600">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-ink-400">{text}</p>
    </div>
  )
}
