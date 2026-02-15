import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./features/dashboard/DashboardPage";
import BacktestPage from "./features/backtest/BacktestPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
      </Route>
    </Routes>
  );
}
