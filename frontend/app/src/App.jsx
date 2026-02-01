import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Fields from './pages/Fields';
import Rotation from './pages/Rotation';
import Plans from './pages/Plans';
import CropSettings from './pages/CropSettings';
import PesticideOrders from './pages/PesticideOrders';
import PesticideRecords from './pages/PesticideRecords';
import PesticideMasters from './pages/PesticideMasters';
import DataManagement from './pages/DataManagement';
import JAAggregation from './pages/JAAggregation';
import UserManagement from './pages/UserManagement';
import FieldRegister from './pages/FieldRegister';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="fields" element={<Fields />} />
          <Route path="field-register" element={<FieldRegister />} />
          <Route path="rotation" element={<Rotation />} />
          <Route path="plans" element={<Plans />} />
          <Route path="crops" element={<CropSettings />} />
          <Route path="pesticide-orders" element={<PesticideOrders />} />
          <Route path="pesticide-records" element={<PesticideRecords />} />
          <Route path="pesticide-masters" element={<PesticideMasters />} />
          <Route path="data" element={<DataManagement />} />
          <Route path="ja" element={<JAAggregation />} />
          <Route path="users" element={<UserManagement />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
