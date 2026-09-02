import { Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './layouts/AppLayout'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import IdentityLookupPage from './pages/IdentityLookupPage'
import LoginPage from './pages/LoginPage'
import ReportsPage from './pages/ReportsPage'
import VerificationCaseDetailPage from './pages/VerificationCaseDetailPage'
import VerificationCasesPage from './pages/VerificationCasesPage'
import VerificationReportPage from './pages/VerificationReportPage'
import VerificationWorkspacePage from './pages/VerificationWorkspacePage'

/**
 * Application shell. Public surface is only the login page; every app page
 * sits behind the ProtectedRoute guard, which is unchanged.
 *
 * Step 10: the signed-in entry point is the Command Center (`/`), with the
 * verification flow, case history and the report library alongside it. The
 * project overview page keeps the original landing content under `/overview`.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* Step 10: Command Center is the home surface. */}
          <Route index element={<DashboardPage />} />
          <Route path="overview" element={<HomePage />} />
          <Route path="lookup" element={<IdentityLookupPage />} />
          <Route path="verify" element={<VerificationWorkspacePage />} />
          <Route path="verifications" element={<VerificationCasesPage />} />
          <Route path="verifications/:verificationId" element={<VerificationCaseDetailPage />} />
          {/* Step 9: full report view (protected by the same guard). */}
          <Route
            path="verifications/:verificationId/report"
            element={<VerificationReportPage />}
          />
          {/* Step 10: report library built from the existing case + report APIs. */}
          <Route path="reports" element={<ReportsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
