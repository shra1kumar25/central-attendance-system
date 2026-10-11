import { useEffect, useMemo, useState } from 'react'
import './App.css'

const navigation = [
  { label: 'Dashboard', icon: '▦' },
  { label: 'Employees', icon: '♙' },
  { label: 'Attendance', icon: '◷' },
  { label: 'Reports', icon: '▤' },
]

function getToday() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

function formatTime(value) {
  if (!value) return '—'

  return new Date(value).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata',
  })
}

function formatDate(value) {
  if (!value) return '—'

  return new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function getStatusLabel(status) {
  const labels = {
    PRESENT: 'Present',
    ABSENT: 'Absent',
    LEAVE: 'Leave',
  }

  return labels[status] || status || 'Not marked'
}

async function fetchJson(url) {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${url}`)
  }

  return response.json()
}

function App() {
  const [employees, setEmployees] = useState([])
  const [records, setRecords] = useState([])
  const [activePage, setActivePage] = useState('Dashboard')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [actionLoading, setActionLoading] = useState(null)
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadDashboard() {
      setLoading(true)
      setError('')

      try {
        const today = getToday()

        const [employeeData, departmentData, attendanceData] =
          await Promise.all([
            fetchJson('/api/employees'),
            fetchJson('/api/departments'),
            fetchJson(
              `/api/attendance?attendance_date=${today}&limit=100`,
            ),
          ])

        if (cancelled) return

        const departmentMap = new Map(
          departmentData.map((department) => [
            department.id,
            department.name,
          ]),
        )

        const attendanceByEmployee = new Map()

        // If duplicate records exist for an employee, prefer the latest one.
        for (const record of attendanceData) {
          const existing = attendanceByEmployee.get(record.employee_id)

          if (!existing || record.id > existing.id) {
            attendanceByEmployee.set(record.employee_id, record)
          }
        }

        const mappedRecords = employeeData
          .filter((employee) => employee.is_active)
          .map((employee) => {
            const record = attendanceByEmployee.get(employee.id)

            return {
              id: record?.id ?? `employee-${employee.id}`,
              employeeId: employee.id,
              employeeCode: employee.employee_code,
              name: employee.full_name,
              department:
                departmentMap.get(employee.department_id) || 'Unassigned',
              date: record?.attendance_date || today,
              checkIn: record?.check_in || null,
              checkOut: record?.check_out || null,
              status: record ? getStatusLabel(record.status) : 'Not marked',
              hasRecord: Boolean(record),
            }
          })

        setEmployees(employeeData)
        setRecords(mappedRecords)
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load attendance data.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadDashboard()

    return () => {
      cancelled = true
    }
  }, [refreshKey])

  async function handleAttendanceAction(employeeId, action) {
    const key = `${employeeId}-${action}`

    setActionLoading(key)
    setError('')
    setSuccessMessage('')

    try {
      const response = await fetch(
        `/api/attendance/${employeeId}/${action}`,
        { method: 'POST' },
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Attendance action failed.')
      }

      setSuccessMessage(
        action === 'check-in'
          ? 'Check-in recorded successfully.'
          : 'Check-out recorded successfully.',
      )

      // Reload employee and attendance data from the backend.
      setRefreshKey((current) => current + 1)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to update attendance.',
      )
    } finally {
      setActionLoading(null)
    }
  }

  const activeEmployees = employees.filter(
    (employee) => employee.is_active,
  )

  const present = records.filter(
    (record) => record.status === 'Present',
  ).length

  const absent = records.filter(
    (record) => record.status === 'Absent',
  ).length

  const leave = records.filter(
    (record) => record.status === 'Leave',
  ).length

  const attendanceRate = activeEmployees.length
    ? Math.round((present / activeEmployees.length) * 100)
    : 0

  const filteredRecords = useMemo(
    () =>
      records.filter((record) => {
        const searchText =
          `${record.name} ${record.employeeCode} ${record.department}`.toLowerCase()

        const matchesSearch = searchText.includes(search.toLowerCase())

        const matchesStatus =
          statusFilter === 'All' ||
          record.status === statusFilter

        return matchesSearch && matchesStatus
      }),
    [records, search, statusFilter],
  )

  const todayLabel = new Date().toLocaleDateString('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  })

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#dashboard"
          aria-label="Attendly home"
          onClick={() => setActivePage('Dashboard')}
        >
          <span className="brand-mark">A</span>
          <span>
            Attendly<span className="brand-dot">.</span>
          </span>
        </a>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="navigation" aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              className={`nav-item ${
                activePage === item.label ? 'active' : ''
              }`}
              key={item.label}
              onClick={() => setActivePage(item.label)}
              type="button"
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
              {item.label === 'Attendance' && (
                <span className="nav-count">{records.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon">✦</div>
            <strong>Need a hand?</strong>
            <p>Find help using your attendance dashboard.</p>
            <button
              type="button"
              onClick={() =>
                window.alert('Help documentation will be added later.')
              }
            >
              Visit help center ↗
            </button>
          </div>

          <div className="profile">
            <div className="avatar">SK</div>
            <div className="profile-info">
              <strong>System Admin</strong>
              <span>Administrator</span>
            </div>
            <span className="profile-menu" aria-hidden="true">
              •••
            </span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> {activePage}
          </div>

          <div className="topbar-actions">
            <span className="today-label">{todayLabel}</span>
            <button
              className="icon-button notification-button"
              type="button"
              aria-label="Notifications"
            >
              ♧<span className="notification-dot" />
            </button>
            <div className="avatar top-avatar">SK</div>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow">
                <span className="live-dot" />
                YOUR WORKSPACE AT A GLANCE
              </div>

              <h1>
                {activePage === 'Dashboard'
                  ? 'Good morning, Admin'
                  : activePage}
              </h1>

              <p className="page-subtitle">
                {activePage === 'Dashboard'
                  ? "Here's what's happening with your team today."
                  : `Explore and manage your ${activePage.toLowerCase()} information.`}
              </p>
            </div>

            <button
              className="primary-button"
              type="button"
              onClick={() => window.print()}
            >
              <span aria-hidden="true">↧</span> Export report
            </button>
          </section>

          {successMessage && (
            <div
              role="status"
              style={{
                padding: '12px 16px',
                marginBottom: '16px',
                borderRadius: '10px',
                border: '1px solid #bbf7d0',
                background: '#f0fdf4',
                color: '#166534',
              }}
            >
              {successMessage}
            </div>
          )}

          {error && (
            <div
              role="alert"
              style={{
                padding: '14px 18px',
                marginBottom: '20px',
                borderRadius: '10px',
                border: '1px solid #fecaca',
                background: '#fef2f2',
                color: '#991b1b',
              }}
            >
              <strong>Unable to complete the request.</strong>
              <p>{error}</p>
              <button
                type="button"
                onClick={() => setRefreshKey((key) => key + 1)}
              >
                Reload data
              </button>
            </div>
          )}

          {loading && (
            <p role="status" aria-live="polite">
              Loading attendance data from the backend...
            </p>
          )}

          <section
            className="stats-grid"
            aria-label="Attendance statistics"
            aria-busy={loading}
          >
            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Total employees</span>
                <span className="stat-icon purple">♙</span>
              </div>
              <div className="stat-value">
                {activeEmployees.length.toString().padStart(2, '0')}
              </div>
              <div className="stat-foot">
                <span className="stat-neutral">Team overview</span>
                <span> active employees</span>
              </div>
              <div className="stat-track">
                <span
                  className="track-purple"
                  style={{
                    width: activeEmployees.length ? '100%' : '0%',
                  }}
                />
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Present today</span>
                <span className="stat-icon green">✓</span>
              </div>
              <div className="stat-value">
                {present.toString().padStart(2, '0')}
              </div>
              <div className="stat-foot">
                <span className="positive">● Present</span>
                <span> recorded today</span>
              </div>
              <div className="stat-track">
                <span
                  className="track-green"
                  style={{
                    width: `${attendanceRate}%`,
                  }}
                />
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Absent today</span>
                <span className="stat-icon red">−</span>
              </div>
              <div className="stat-value">
                {absent.toString().padStart(2, '0')}
              </div>
              <div className="stat-foot">
                <span className="negative">● Marked absent</span>
              </div>
              <div className="stat-track">
                <span
                  className="track-red"
                  style={{
                    width: `${activeEmployees.length
                      ? Math.min(
                          (absent / activeEmployees.length) * 100,
                          100,
                        )
                      : 0}%`,
                  }}
                />
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Attendance rate</span>
                <span className="stat-icon blue">↗</span>
              </div>
              <div className="stat-value">
                {attendanceRate}
                <span className="value-percent">%</span>
              </div>
              <div className="stat-foot">
                <span className="positive">● Today's overview</span>
              </div>
              <div className="stat-track">
                <span
                  className="track-blue"
                  style={{ width: `${attendanceRate}%` }}
                />
              </div>
            </article>
          </section>

          <section className="insights-grid">
            <article className="panel attendance-panel">
              <div className="panel-heading">
                <div>
                  <h2>Attendance overview</h2>
                  <p>Today's employee attendance breakdown</p>
                </div>
                <span className="date-chip">
                  Today <span>⌄</span>
                </span>
              </div>

              <div className="overview-body">
                <div
                  className="donut-chart"
                  style={{
                    '--present-angle': `${
                      records.length
                        ? (present / records.length) * 360
                        : 0
                    }deg`,
                    '--late-angle': `${
                      records.length
                        ? (leave / records.length) * 360
                        : 0
                    }deg`,
                  }}
                  role="img"
                  aria-label={`${present} present, ${leave} on leave, ${absent} absent`}
                >
                  <div className="donut-center">
                    <strong>{attendanceRate}%</strong>
                    <span>Attendance</span>
                  </div>
                </div>

                <div className="legend">
                  <div className="legend-item">
                    <span className="legend-dot dot-green" />
                    <span>Present</span>
                    <strong>{present}</strong>
                  </div>
                  <div className="legend-item">
                    <span className="legend-dot dot-orange" />
                    <span>Leave</span>
                    <strong>{leave}</strong>
                  </div>
                  <div className="legend-item">
                    <span className="legend-dot dot-red" />
                    <span>Absent</span>
                    <strong>{absent}</strong>
                  </div>
                  <div className="legend-total">
                    <span>Active employees</span>
                    <strong>{activeEmployees.length}</strong>
                  </div>
                </div>
              </div>
            </article>

            <article className="panel quick-panel">
              <div className="panel-heading">
                <div>
                  <h2>Quick summary</h2>
                  <p>A snapshot of today's activity</p>
                </div>
                <span className="summary-icon">✦</span>
              </div>

              <div className="summary-list">
                <div className="summary-row">
                  <span className="summary-symbol summary-green">✓</span>
                  <div>
                    <strong>Employees present</strong>
                    <span>Marked present today</span>
                  </div>
                  <b>{present}</b>
                </div>

                <div className="summary-row">
                  <span className="summary-symbol summary-orange">◷</span>
                  <div>
                    <strong>Employees on leave</strong>
                    <span>Marked on leave today</span>
                  </div>
                  <b>{leave}</b>
                </div>

                <div className="summary-row">
                  <span className="summary-symbol summary-red">!</span>
                  <div>
                    <strong>Absences</strong>
                    <span>Marked absent today</span>
                  </div>
                  <b>{absent}</b>
                </div>
              </div>
            </article>
          </section>

          <section className="panel records-panel">
            <div className="records-heading">
              <div>
                <h2>Today's attendance</h2>
                <p>
                  Search employees and manage their attendance below.
                </p>
              </div>
              <span className="records-badge">
                {filteredRecords.length} employees
              </span>
            </div>

            <div className="table-toolbar">
              <label className="search-box">
                <span aria-hidden="true">⌕</span>
                <input
                  aria-label="Search employees"
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search employees or departments..."
                  value={search}
                />
                <kbd>⌘ K</kbd>
              </label>

              <label className="filter-select">
                <span aria-hidden="true">☷</span>
                <select
                  aria-label="Filter by attendance status"
                  onChange={(event) => setStatusFilter(event.target.value)}
                  value={statusFilter}
                >
                  <option value="All">All statuses</option>
                  <option value="Present">Present</option>
                  <option value="Absent">Absent</option>
                  <option value="Leave">Leave</option>
                  <option value="Not marked">Not marked</option>
                </select>
              </label>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>EMPLOYEE</th>
                    <th>DEPARTMENT</th>
                    <th>DATE</th>
                    <th>CHECK IN</th>
                    <th>CHECK OUT</th>
                    <th>STATUS</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredRecords.map((record) => {
                    const checkInKey = `${record.employeeId}-check-in`
                    const checkOutKey = `${record.employeeId}-check-out`

                    const checkingIn = actionLoading === checkInKey
                    const checkingOut = actionLoading === checkOutKey

                    return (
                      <tr key={record.id}>
                        <td>
                          <div className="employee-cell">
                            <span
                              className={`employee-avatar avatar-${
                                record.employeeId % 6 || 6
                              }`}
                            >
                              {record.name
                                .split(' ')
                                .map((part) => part[0])
                                .join('')}
                            </span>
                            <div>
                              <strong>{record.name}</strong>
                              <div
                                style={{
                                  fontSize: '12px',
                                  opacity: 0.7,
                                  marginTop: '3px',
                                }}
                              >
                                {record.employeeCode}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="department-cell">
                          {record.department}
                        </td>

                        <td>{formatDate(record.date)}</td>
                        <td>{formatTime(record.checkIn)}</td>
                        <td>{formatTime(record.checkOut)}</td>

                        <td>
                          <span
                            className={`status-pill status-${record.status
                              .toLowerCase()
                              .replace(/\s+/g, '-')}`}
                          >
                            <span />
                            {record.status}
                          </span>
                        </td>

                        <td>
                          <div
                            style={{
                              display: 'flex',
                              gap: '6px',
                              minWidth: '190px',
                            }}
                          >
                            <button
                              type="button"
                              disabled={
                                Boolean(actionLoading) ||
                                Boolean(record.checkIn)
                              }
                              onClick={() =>
                                handleAttendanceAction(
                                  record.employeeId,
                                  'check-in',
                                )
                              }
                              style={{
                                padding: '7px 10px',
                                borderRadius: '7px',
                                border: '1px solid #bbf7d0',
                                background:
                                  record.checkIn ? '#f3f4f6' : '#dcfce7',
                                color:
                                  record.checkIn ? '#6b7280' : '#166534',
                                cursor:
                                  record.checkIn || actionLoading
                                    ? 'not-allowed'
                                    : 'pointer',
                                fontSize: '12px',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {checkingIn ? 'Checking in…' : 'Check In'}
                            </button>

                            <button
                              type="button"
                              disabled={
                                Boolean(actionLoading) ||
                                !record.checkIn ||
                                Boolean(record.checkOut)
                              }
                              onClick={() =>
                                handleAttendanceAction(
                                  record.employeeId,
                                  'check-out',
                                )
                              }
                              style={{
                                padding: '7px 10px',
                                borderRadius: '7px',
                                border: '1px solid #bfdbfe',
                                background:
                                  !record.checkIn || record.checkOut
                                    ? '#f3f4f6'
                                    : '#dbeafe',
                                color:
                                  !record.checkIn || record.checkOut
                                    ? '#6b7280'
                                    : '#1d4ed8',
                                cursor:
                                  !record.checkIn ||
                                  record.checkOut ||
                                  actionLoading
                                    ? 'not-allowed'
                                    : 'pointer',
                                fontSize: '12px',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {checkingOut ? 'Checking out…' : 'Check Out'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}

                  {!loading && filteredRecords.length === 0 && (
                    <tr>
                      <td className="empty-state" colSpan="7">
                        {error
                          ? 'Attendance data could not be loaded.'
                          : 'No employees match your search or status filter.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="table-footer">
              <span>
                Showing <strong>{filteredRecords.length}</strong> of{' '}
                <strong>{records.length}</strong> employees
              </span>
              <span className="demo-note">
                <span />
                Live data · FastAPI backend
              </span>
            </div>
          </section>

          <footer className="page-footer">
            <span>© 2026 Attendly · Central Attendance System</span>
            <span>
              Made for better team visibility{' '}
              <span className="footer-heart">♥</span>
            </span>
          </footer>
        </div>
      </main>
    </div>
  )
}

export default App