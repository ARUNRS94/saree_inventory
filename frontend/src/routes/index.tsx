import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { MainLayout } from '@/layouts/MainLayout';
import LoginPage from '@/pages/Login';
import SignupPage from '@/pages/Signup';
import DashboardPage from '@/pages/Dashboard';
import SareesPage from '@/pages/Sarees';
import SuppliersPage from '@/pages/Suppliers';
import VendorsPage from '@/pages/Vendors';
import PurchaseOrdersPage from '@/pages/PurchaseOrders';
import GRNPage from '@/pages/GRN';
import JobWorkPage from '@/pages/JobWork';
import InventoryPage from '@/pages/Inventory';
import ReportsPage from '@/pages/Reports';
import UsersPage from '@/pages/Users';
import AccessManagementPage from '@/pages/Access';
import SettingsPage from '@/pages/Settings';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function AppRoutes() {
  const { user } = useAuth();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route path="/signup" element={user ? <Navigate to="/" replace /> : <SignupPage />} />
        <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="sarees" element={<SareesPage />} />
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="vendors" element={<VendorsPage />} />
          <Route path="purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="grn" element={<GRNPage />} />
          <Route path="job-work" element={<JobWorkPage />} />
          <Route path="inventory" element={<InventoryPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="access" element={<AccessManagementPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
