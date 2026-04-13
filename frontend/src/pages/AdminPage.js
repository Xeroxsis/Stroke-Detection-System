import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../lib/api';
import DashboardLayout from '../components/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ShieldCheck, Trash2, Users } from 'lucide-react';
import { toast } from 'sonner';

const roleColors = {
  admin: 'bg-[#E11D48]/10 text-[#E11D48]',
  doctor: 'bg-[#0EA5E9]/10 text-[#0EA5E9]',
  nurse: 'bg-[#10B981]/10 text-[#10B981]',
};

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchUsers = () => {
    api.get('/admin/users')
      .then(r => setUsers(r.data))
      .catch(err => {
        if (err.response?.status === 403) toast.error('Admin access required');
        else toast.error('Failed to load users');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleRoleChange = async (userId, newRole) => {
    try {
      await api.put(`/admin/users/${userId}/role`, { role: newRole });
      toast.success(`Role updated to ${newRole}`);
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleDelete = async (userId, email) => {
    if (!window.confirm(`Delete user ${email}? This cannot be undone.`)) return;
    try {
      await api.delete(`/admin/users/${userId}`);
      toast.success('User deleted');
      fetchUsers();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  if (currentUser?.role !== 'admin') {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-20 text-[#9CA3AF]">
          <ShieldCheck className="w-8 h-8 mr-3" />
          <p>Admin access required</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div data-testid="admin-page" className="space-y-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-medium text-[#111827]">User Management</h1>
          <p className="text-sm text-[#9CA3AF] mt-1">Manage user accounts and role assignments</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {['admin', 'doctor', 'nurse'].map(role => (
            <Card key={role} className="border border-[#E5E7EB] shadow-none">
              <CardContent className="p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.15em] font-bold text-[#9CA3AF]">{role}s</p>
                  <p className="text-2xl font-heading font-medium text-[#111827] mt-1">
                    {users.filter(u => u.role === role).length}
                  </p>
                </div>
                <Badge className={`${roleColors[role]} border-0 capitalize text-sm`}>{role}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Users Table */}
        <Card className="border border-[#E5E7EB] shadow-none">
          <CardHeader className="pb-4">
            <CardTitle className="font-heading text-lg font-medium text-[#111827] flex items-center gap-2">
              <Users className="w-5 h-5 text-[#0EA5E9]" strokeWidth={1.5} />
              All Users
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-2 border-[#0EA5E9] border-t-transparent rounded-full animate-spin mx-auto" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-[#9CA3AF]">Name</TableHead>
                    <TableHead className="text-[#9CA3AF]">Email</TableHead>
                    <TableHead className="text-[#9CA3AF]">Current Role</TableHead>
                    <TableHead className="text-[#9CA3AF]">Change Role</TableHead>
                    <TableHead className="text-[#9CA3AF]">Joined</TableHead>
                    <TableHead className="text-[#9CA3AF] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map(u => {
                    const isSelf = u.id === currentUser?._id || u.id === currentUser?.id;
                    return (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium text-[#111827]">
                          {u.name} {isSelf && <span className="text-xs text-[#9CA3AF]">(you)</span>}
                        </TableCell>
                        <TableCell className="text-[#4B5563] text-sm">{u.email}</TableCell>
                        <TableCell>
                          <Badge className={`${roleColors[u.role] || roleColors.nurse} border-0 capitalize`}>
                            {u.role}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {isSelf ? (
                            <span className="text-xs text-[#9CA3AF]">-</span>
                          ) : (
                            <Select
                              value={u.role}
                              onValueChange={val => handleRoleChange(u.id, val)}
                            >
                              <SelectTrigger
                                data-testid={`role-select-${u.id}`}
                                className="w-28 h-8 text-xs border-[#E5E7EB]"
                              >
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="admin">Admin</SelectItem>
                                <SelectItem value="doctor">Doctor</SelectItem>
                                <SelectItem value="nurse">Nurse</SelectItem>
                              </SelectContent>
                            </Select>
                          )}
                        </TableCell>
                        <TableCell className="text-[#4B5563] text-sm">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                        </TableCell>
                        <TableCell className="text-right">
                          {!isSelf && (
                            <Button
                              variant="ghost"
                              size="sm"
                              data-testid={`delete-user-${u.id}`}
                              onClick={() => handleDelete(u.id, u.email)}
                              className="text-[#4B5563] hover:text-[#E11D48]"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
