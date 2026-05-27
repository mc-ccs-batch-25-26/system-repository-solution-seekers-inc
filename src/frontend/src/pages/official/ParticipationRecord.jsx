import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { cyclesApi } from '../../api/cycles'

const EMPTY_FORM = {
  cycle: '',
  beneficiary: '',
  project_name: '',
  status: 'present',
  hours_worked: '8',
  remarks: '',
  photo_data: '',
  photo_name: '',
}

const DAILY_STATUS_OPTIONS = [
  { value: 'present', label: 'Present / Worked' },
  { value: 'absent', label: 'Absent / No Work' },
  { value: 'excused', label: 'Excused' },
]

function getTodayDateString() {
  const now = new Date()
  const timezoneOffset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - timezoneOffset).toISOString().slice(0, 10)
}

function validate(form, selectedCycle, today) {
  const errors = {}
  if (!form.cycle) errors.cycle = 'Select a program cycle.'
  if (!form.beneficiary) errors.beneficiary = 'Select a beneficiary.'
  if (!form.project_name.trim()) errors.project_name = 'Project name is required.'
  if (!selectedCycle) return errors
  if (today < selectedCycle.work_start_date || today > selectedCycle.work_end_date) {
    errors.work_date = 'Attendance can only be recorded during the TUPAD work period.'
  }
  if (form.status === 'present' && Number(form.hours_worked) <= 0) {
    errors.hours_worked = 'Hours worked must be greater than 0 for present attendance.'
  }
  return errors
}

export default function ParticipationRecord() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const today = getTodayDateString()
  const [cycles, setCycles] = useState([])
  const [selectedApplicants, setSelectedApplicants] = useState([])
  const [applicantsLoading, setApplicantsLoading] = useState(false)
  const [existingTodayRecord, setExistingTodayRecord] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [benSearch, setBenSearch] = useState('')
  const [form, setForm] = useState({
    ...EMPTY_FORM,
    cycle: searchParams.get('cycle') || '',
  })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')

  useEffect(() => {
    cyclesApi.list()
      .then((d) => setCycles(d.results ?? d))
      .catch(() => setServerError('Failed to load cycles.'))
  }, [])

  useEffect(() => {
    if (!form.cycle) {
      setSelectedApplicants([])
      return
    }

    setApplicantsLoading(true)
    cyclesApi.listApplications(form.cycle)
      .then((d) => {
        const applications = d.results ?? d
        setSelectedApplicants(applications.filter((app) => app.status === 'selected'))
      })
      .catch(() => setServerError('Failed to load selected applicants for this cycle.'))
      .finally(() => setApplicantsLoading(false))
  }, [form.cycle])

  useEffect(() => {
    if (!form.cycle || !form.beneficiary) {
      setExistingTodayRecord(null)
      return
    }

    setHistoryLoading(true)
    cyclesApi.listParticipation({ cycle: form.cycle, beneficiary: form.beneficiary, page_size: 100 })
      .then((d) => {
        const records = d.results ?? d
        const participation = records.find((record) => record.project_name) ?? records[0]
        const todayRecord = records
          .flatMap((record) => record.daily_records ?? [])
          .find((row) => row.work_date === today) ?? null
        setExistingTodayRecord(todayRecord)
        if (participation?.project_name) {
          setForm((prev) => ({ ...prev, project_name: participation.project_name }))
        }
      })
      .catch(() => setServerError('Failed to check today attendance history.'))
      .finally(() => setHistoryLoading(false))
  }, [form.cycle, form.beneficiary, today])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: value,
      ...(name === 'cycle' ? { beneficiary: '', project_name: '', photo_data: '', photo_name: '' } : {}),
      ...(name === 'status' && value !== 'present' ? { hours_worked: '0' } : {}),
      ...(name === 'status' && value === 'present' && Number(prev.hours_worked) === 0 ? { hours_worked: '8' } : {}),
    }))
    if (name === 'cycle') setBenSearch('')
    setErrors((prev) => ({ ...prev, [name]: undefined }))
    setSuccess('')
  }

  const handlePhoto = (file) => {
    if (!file) {
      setForm((prev) => ({ ...prev, photo_data: '', photo_name: '' }))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setForm((prev) => ({ ...prev, photo_data: reader.result, photo_name: file.name }))
    }
    reader.readAsDataURL(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const selectedCycle = cycles.find((c) => String(c.id) === String(form.cycle))
    const errs = validate(form, selectedCycle, today)
    if (Object.keys(errs).length) { setErrors(errs); return }
    if (existingTodayRecord) {
      setErrors({ work_date: 'Attendance for today has already been recorded and cannot be modified.' })
      return
    }
    if (!window.confirm(`Record attendance for ${today}? This cannot be edited after saving.`)) return

    setSaving(true)
    setServerError('')
    setSuccess('')
    try {
      await cyclesApi.recordDailyAttendance({
        cycle: form.cycle,
        beneficiary: form.beneficiary,
        project_name: form.project_name.trim(),
        status: form.status,
        hours_worked: Number(form.hours_worked || 0),
        remarks: form.remarks,
        photo_data: form.photo_data,
      })
      const beneName = selectedApplicants.find((app) => String(app.beneficiary) === String(form.beneficiary))?.beneficiary_name ?? ''
      setSuccess(`Attendance recorded for ${beneName} on ${today}.`)
      setForm((prev) => ({ ...EMPTY_FORM, cycle: prev.cycle }))
      setBenSearch('')
      setExistingTodayRecord(null)
      setErrors({})
    } catch (err) {
      const detail = err.response?.data
      if (typeof detail === 'object') {
        const fieldErrors = {}
        for (const [k, v] of Object.entries(detail)) {
          fieldErrors[k] = Array.isArray(v) ? v[0] : v
        }
        setErrors(fieldErrors)
      } else {
        setServerError('Failed to record attendance. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  const filteredApplicants = selectedApplicants.filter((app) =>
    app.beneficiary_name.toLowerCase().includes(benSearch.toLowerCase())
  )
  const selectedCycle = cycles.find((c) => String(c.id) === String(form.cycle))
  const selectedBeneficiary = selectedApplicants.find((app) => String(app.beneficiary) === String(form.beneficiary))
  const isWithinWorkPeriod = Boolean(
    selectedCycle?.work_start_date &&
    selectedCycle?.work_end_date &&
    today >= selectedCycle.work_start_date &&
    today <= selectedCycle.work_end_date
  )
  const submitDisabled = saving || historyLoading || existingTodayRecord || !isWithinWorkPeriod
  const backTarget = form.cycle ? `/official/cycles/${form.cycle}` : '/official/cycles'

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <button onClick={() => navigate(backTarget)} className="btn-ghost mb-3 -ml-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <path d="M12 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          <p className="page-section-label">Barangay Operations</p>
          <h1 className="mt-1 text-2xl font-bold text-ink-900">Daily Attendance</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-500">
            Record attendance only for the current work date. Saved attendance is locked for audit integrity.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="badge bg-blue-100 text-blue-700">Today: {today}</span>
          <span className={`badge ${isWithinWorkPeriod ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            {isWithinWorkPeriod ? 'Work day open' : 'Outside work period'}
          </span>
          <span className={`badge ${existingTodayRecord ? 'bg-slate-100 text-ink-600' : 'bg-primary-100 text-primary-700'}`}>
            {existingTodayRecord ? 'Already recorded' : 'Insert only'}
          </span>
        </div>
      </div>

      {serverError && <Alert type="error" text={serverError} />}
      {success && <Alert type="success" text={success} />}
      {errors.work_date && <Alert type="warning" text={errors.work_date} />}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <form onSubmit={handleSubmit} className="card">
          <div className="border-b border-slate-200 bg-slate-50 px-5 py-4">
            <h2 className="text-base font-bold text-ink-900">Attendance Details</h2>
            <p className="mt-0.5 text-xs text-ink-500">Only today can be recorded. Past and future dates are read-only in history.</p>
          </div>

          <div className="space-y-5 p-5">
            <section className="space-y-3">
              <SectionTitle number="1" title="Choose Cycle" />
              <Field label="Program Cycle" error={errors.cycle}>
                <select name="cycle" value={form.cycle} onChange={handleChange} className={inp(errors.cycle)}>
                  <option value="">Select a cycle...</option>
                  {cycles.map((c) => <option key={c.id} value={c.id}>{c.cycle_name}</option>)}
                </select>
              </Field>
              {selectedCycle && (
                <div className="flex flex-wrap gap-2">
                  <span className="badge bg-primary-100 text-primary-700">
                    Application: {selectedCycle.application_start_date ?? selectedCycle.start_date} to {selectedCycle.application_end_date ?? selectedCycle.end_date}
                  </span>
                  <span className="badge bg-emerald-100 text-emerald-700">Work: {selectedCycle.work_start_date} to {selectedCycle.work_end_date}</span>
                  <span className="badge bg-blue-100 text-blue-700">{selectedCycle.slots} slots</span>
                </div>
              )}
            </section>

            <section className="space-y-3">
              <SectionTitle number="2" title="Select Resident Profile" />
              <Field label="Selected Applicant" error={errors.beneficiary}>
                <div className="relative">
                  <svg className="pointer-events-none absolute left-3 top-3 text-ink-400" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                  <input
                    type="text"
                    placeholder={form.cycle ? 'Search selected applicants...' : 'Select a cycle first'}
                    value={benSearch}
                    onChange={(e) => setBenSearch(e.target.value)}
                    disabled={!form.cycle || applicantsLoading}
                    className={`${inp()} pl-9 disabled:bg-slate-100 disabled:text-ink-400`}
                  />
                </div>
                <div className={`mt-2 max-h-64 overflow-auto rounded-lg border ${errors.beneficiary ? 'border-red-300 bg-red-50/30' : 'border-slate-200 bg-white'}`}>
                  {!form.cycle && <EmptyPanel text="Select a cycle to see accepted applicants." />}
                  {form.cycle && applicantsLoading && <EmptyPanel text="Loading selected applicants..." />}
                  {form.cycle && !applicantsLoading && selectedApplicants.length === 0 && <EmptyPanel text="No selected applicants yet." />}
                  {form.cycle && !applicantsLoading && selectedApplicants.length > 0 && filteredApplicants.length === 0 && <EmptyPanel text="No selected applicant matches your search." />}
                  {filteredApplicants.map((app, index) => (
                    <button
                      type="button"
                      key={app.id}
                      onClick={() => {
                        setForm((prev) => ({ ...prev, beneficiary: app.beneficiary, photo_data: '', photo_name: '' }))
                        setErrors((prev) => ({ ...prev, beneficiary: undefined, work_date: undefined }))
                        setSuccess('')
                      }}
                      className={`flex w-full items-center gap-3 border-b border-slate-100 px-4 py-3 text-left transition last:border-b-0 hover:bg-slate-50 ${
                        String(form.beneficiary) === String(app.beneficiary) ? 'bg-primary-50' : ''
                      }`}
                    >
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                        String(form.beneficiary) === String(app.beneficiary) ? 'bg-primary-600 text-white' : 'bg-emerald-100 text-emerald-700'
                      }`}>
                        {app.rank_position ?? index + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-ink-900">{app.beneficiary_name}</span>
                        <span className="text-xs text-ink-400">Selected applicant</span>
                      </span>
                    </button>
                  ))}
                </div>
              </Field>
            </section>

            <section className="space-y-3">
              <SectionTitle number="3" title="Today Attendance" />
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Attendance Date">
                  <input type="date" value={today} readOnly className="form-input bg-slate-100 text-ink-500" />
                </Field>
                <Field label="Project Name" error={errors.project_name}>
                  <input
                    name="project_name"
                    value={form.project_name}
                    onChange={handleChange}
                    className={inp(errors.project_name)}
                    placeholder="e.g. Road Clearing Project"
                    disabled={Boolean(existingTodayRecord)}
                  />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Status" error={errors.status}>
                  <select
                    name="status"
                    value={form.status}
                    onChange={handleChange}
                    className={inp(errors.status)}
                    disabled={Boolean(existingTodayRecord)}
                  >
                    {DAILY_STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Hours Worked" error={errors.hours_worked}>
                  <input
                    name="hours_worked"
                    type="number"
                    min="0"
                    step="0.5"
                    value={form.hours_worked}
                    onChange={handleChange}
                    disabled={form.status !== 'present' || Boolean(existingTodayRecord)}
                    className={`${inp(errors.hours_worked)} disabled:bg-slate-100`}
                  />
                </Field>
              </div>

              <Field label="Photo Proof">
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => handlePhoto(e.target.files?.[0])}
                  disabled={Boolean(existingTodayRecord)}
                  className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-ink-500 file:mr-3 file:rounded-md file:border-0 file:bg-primary-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary-700 disabled:bg-slate-100"
                />
                {form.photo_name && <p className="mt-1 truncate text-xs text-emerald-600">{form.photo_name}</p>}
              </Field>

              <Field label="Remarks">
                <textarea
                  name="remarks"
                  value={form.remarks}
                  onChange={handleChange}
                  disabled={Boolean(existingTodayRecord)}
                  className="form-input min-h-[90px] disabled:bg-slate-100"
                  placeholder="Optional notes for today's attendance"
                />
              </Field>
            </section>

            {existingTodayRecord && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-sm font-semibold text-ink-900">Today's attendance is already recorded.</p>
                <p className="mt-1 text-xs text-ink-500">
                  Status: {existingTodayRecord.status} | Hours: {existingTodayRecord.hours_worked} | Saved: {new Date(existingTodayRecord.created_at).toLocaleString()}
                </p>
              </div>
            )}

            <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center">
              <button type="submit" disabled={submitDisabled} className="btn-primary justify-center disabled:cursor-not-allowed disabled:opacity-60">
                {saving ? 'Recording...' : 'Record Today Attendance'}
              </button>
              <p className="text-xs text-ink-400">Attendance is saved once per resident per work date.</p>
            </div>
          </div>
        </form>

        <aside className="space-y-5">
          <div className="card p-5">
            <h2 className="text-base font-bold text-ink-900">Current Selection</h2>
            <div className="mt-4 space-y-3">
              <SummaryRow label="Cycle" value={selectedCycle?.cycle_name || 'No cycle selected'} active={Boolean(selectedCycle)} />
              <SummaryRow label="Resident Profile" value={selectedBeneficiary?.beneficiary_name || 'No resident profile selected'} active={Boolean(selectedBeneficiary)} />
              <SummaryRow label="Today" value={today} active />
            </div>
          </div>

          <div className="card p-5">
            <h2 className="text-base font-bold text-ink-900">Recording Rule</h2>
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
              <p className="text-sm font-semibold text-emerald-800">Current date only</p>
              <p className="mt-1 text-xs leading-5 text-emerald-700">
                Staff can record only today's attendance, only inside the cycle work period, and only once per selected resident.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

function SectionTitle({ number, title }) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-100 text-xs font-bold text-primary-700">{number}</span>
      <h2 className="text-sm font-bold text-ink-900">{title}</h2>
    </div>
  )
}

function SummaryRow({ label, value, active }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold ${active ? 'text-ink-900' : 'text-ink-400'}`}>{value}</p>
    </div>
  )
}

function EmptyPanel({ text }) {
  return <div className="px-5 py-8 text-center text-sm text-ink-400">{text}</div>
}

function Alert({ type, text }) {
  const classes = {
    error: 'alert-error',
    success: 'alert-success',
    warning: 'alert-warning',
  }
  return <div className={classes[type]}>{text}</div>
}

function Field({ label, error, children }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">{label}</label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function inp(error) {
  return `form-input ${error ? 'form-input-error' : ''}`
}
