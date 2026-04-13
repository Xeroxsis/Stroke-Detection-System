import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LayoutDashboard, ScanLine, Users, LogOut, Menu, X, Brain, ShieldCheck, GraduationCap } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const roleColors = {
  admin: 'bg-[#E11D48]/10 text-[#E11D48]',
  doctor: 'bg-[#0EA5E9]/10 text-[#0EA5E9]',
  nurse: 'bg-[#10B981]/10 text-[#10B981]',
};

function getNavItems(role) {
  const items = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/scan', label: 'New Scan', icon: ScanLine, minRole: 'doctor' },
    { path: '/patients', label: 'Patients', icon: Users },
    { path: '/training', label: 'Training', icon: GraduationCap, minRole: 'doctor' },
  ];
  if (role === 'admin') {
    items.push({ path: '/admin', label: 'Admin', icon: ShieldCheck, minRole: 'admin' });
  }
  const hierarchy = { admin: 3, doctor: 2, nurse: 1 };
  const userLevel = hierarchy[role] || 0;
  return items.filter(item => {
    const minLevel = hierarchy[item.minRole] || 0;
    return userLevel >= minLevel;
  });
}

export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] font-body" data-testid="dashboard-layout">
      {/* Mobile header */}
      <div className="md:hidden sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-[#E5E7EB] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6 text-[#0EA5E9]" strokeWidth={1.5} />
          <span className="font-heading font-medium text-[#111827]">NeuroScan</span>
        </div>
        <button
          data-testid="mobile-menu-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-lg hover:bg-[#F3F4F6] transition-colors"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/20" onClick={() => setSidebarOpen(false)}>
          <div className="w-64 h-full bg-white border-r border-[#E5E7EB] p-6" onClick={e => e.stopPropagation()}>
            <SidebarContent location={location} onLogout={handleLogout} user={user} onNavClick={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex">
        {/* Desktop sidebar */}
        <aside className="hidden md:flex flex-col w-64 min-h-screen bg-white border-r border-[#E5E7EB] p-6 fixed left-0 top-0">
          <SidebarContent location={location} onLogout={handleLogout} user={user} />
        </aside>

        {/* Main content */}
        <main className="flex-1 md:ml-64 p-6 md:p-8 lg:p-10 min-h-screen">
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarContent({ location, onLogout, user, onNavClick }) {
  const navItems = getNavItems(user?.role);
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2.5 mb-10">
        <Brain className="w-7 h-7 text-[#0EA5E9]" strokeWidth={1.5} />
        <span className="font-heading font-semibold text-lg text-[#111827]">NeuroScan AI</span>
      </div>

      <nav className="flex-1 flex flex-col gap-1">
        {navItems.map(item => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
              onClick={onNavClick}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
                ${isActive
                  ? 'bg-[#0EA5E9]/10 text-[#0EA5E9]'
                  : 'text-[#4B5563] hover:bg-[#F3F4F6] hover:text-[#111827]'}`}
            >
              <Icon className="w-4.5 h-4.5" strokeWidth={1.5} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="pt-6 border-t border-[#E5E7EB]">
        <div className="px-3 mb-3">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-sm font-medium text-[#111827] truncate">{user?.name}</p>
            <Badge className={`${roleColors[user?.role] || roleColors.nurse} border-0 text-[10px] px-1.5 py-0 capitalize`}>
              {user?.role}
            </Badge>
          </div>
          <p className="text-xs text-[#9CA3AF] truncate">{user?.email}</p>
        </div>
        <Button
          data-testid="logout-button"
          variant="ghost"
          onClick={onLogout}
          className="w-full justify-start gap-3 px-3 text-[#4B5563] hover:text-[#E11D48] hover:bg-red-50"
        >
          <LogOut className="w-4 h-4" strokeWidth={1.5} />
          Sign Out
        </Button>
      </div>
    </div>
  );
}
