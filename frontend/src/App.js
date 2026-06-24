import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { Layout } from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import MemeAssetViewer from "@/pages/MemeAssetViewer";
import CanonVault from "@/pages/CanonVault";
import Governance from "@/pages/Governance";
import RarityCalculator from "@/pages/RarityCalculator";
import EconomicSimulator from "@/pages/EconomicSimulator";
import ChartViewer from "@/pages/ChartViewer";
import ControlDeck from "@/pages/ControlDeck";
import DebugDashboard from "@/pages/DebugDashboard";
import Legal from "@/pages/Legal";
import Login from "@/pages/Login";
import Marketplace from "@/pages/Marketplace";
import PublicCanon from "@/pages/PublicCanon";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/assets" element={<MemeAssetViewer />} />
            <Route path="/assets/:id" element={<MemeAssetViewer />} />
            <Route path="/canon" element={<CanonVault />} />
            <Route path="/marketplace" element={<Marketplace />} />
            <Route path="/public/:id" element={<PublicCanon />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/rarity" element={<RarityCalculator />} />
            <Route path="/economic" element={<EconomicSimulator />} />
            <Route path="/charts" element={<ChartViewer />} />
            <Route path="/control-deck" element={<ControlDeck />} />
            <Route path="/debug" element={<DebugDashboard />} />
            <Route path="/legal" element={<Legal />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </Layout>
        <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#0B0C15", border: "1px solid #1A1D2E", color: "#E2E8F0", borderRadius: 2, fontFamily: "JetBrains Mono, monospace" } }} />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
