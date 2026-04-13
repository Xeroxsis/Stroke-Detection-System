import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../lib/api';
import DashboardLayout from '../components/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Progress } from '../components/ui/progress';
import { Upload, Zap, BarChart3, CheckCircle, XCircle, Loader2, GraduationCap } from 'lucide-react';
import { toast } from 'sonner';

const labelColors = {
  hemorrhagic: 'bg-[#E11D48]/10 text-[#E11D48]',
  ischemic: 'bg-[#F59E0B]/10 text-[#F59E0B]',
  normal: 'bg-[#10B981]/10 text-[#10B981]',
};

export default function TrainingPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState(null);
  const [label, setLabel] = useState('');
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);

  const fetchData = useCallback(() => {
    Promise.all([
      api.get('/training/status'),
      api.get('/training/history'),
    ])
      .then(([s, h]) => {
        setStatus(s.data);
        setHistory(h.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !label) {
      toast.error('Select an image and a classification label');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('label', label);
      const { data } = await api.post('/training/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(`Sample added (${data.total_samples} total)`);
      setFile(null);
      setLabel('');
      const input = document.getElementById('training-file-input');
      if (input) input.value = '';
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    try {
      const { data } = await api.post('/training/train');
      toast.success(`Model trained on ${data.samples_count} samples (accuracy: ${(data.accuracy * 100).toFixed(1)}%)`);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Training failed');
    } finally {
      setTraining(false);
    }
  };

  const totalSamples = status?.total_samples || 0;
  const isAdmin = user?.role === 'admin';
  const canUpload = user?.role === 'admin' || user?.role === 'doctor';

  return (
    <DashboardLayout>
      <div data-testid="training-page" className="space-y-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-medium text-[#111827]">Model Training</h1>
          <p className="text-sm text-[#9CA3AF] mt-1">Upload labeled MRI images to fine-tune the stroke detection model</p>
        </div>

        {loading ? (
          <div className="py-20 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-[#0EA5E9] mx-auto" />
          </div>
        ) : (
          <>
            {/* Status Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="border border-[#E5E7EB] shadow-none">
                <CardContent className="p-5">
                  <p className="text-xs uppercase tracking-[0.15em] font-bold text-[#9CA3AF]">Model Status</p>
                  <div className="flex items-center gap-2 mt-2">
                    {status?.is_trained ? (
                      <><CheckCircle className="w-5 h-5 text-[#10B981]" /><span className="font-medium text-[#10B981]">Trained</span></>
                    ) : (
                      <><XCircle className="w-5 h-5 text-[#F59E0B]" /><span className="font-medium text-[#F59E0B]">Default</span></>
                    )}
                  </div>
                </CardContent>
              </Card>
              <Card className="border border-[#E5E7EB] shadow-none">
                <CardContent className="p-5">
                  <p className="text-xs uppercase tracking-[0.15em] font-bold text-[#9CA3AF]">Total Samples</p>
                  <p className="text-2xl font-heading font-medium text-[#111827] mt-1">{totalSamples}</p>
                </CardContent>
              </Card>
              {['hemorrhagic', 'ischemic', 'normal'].map(cls => (
                <Card key={cls} className="border border-[#E5E7EB] shadow-none">
                  <CardContent className="p-5">
                    <p className="text-xs uppercase tracking-[0.15em] font-bold text-[#9CA3AF] capitalize">{cls}</p>
                    <p className="text-2xl font-heading font-medium text-[#111827] mt-1">
                      {status?.samples_by_class?.[cls] || 0}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Upload + Train */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Upload Form */}
              {canUpload && (
                <Card className="border border-[#E5E7EB] shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle className="font-heading text-lg font-medium text-[#111827] flex items-center gap-2">
                      <Upload className="w-5 h-5 text-[#0EA5E9]" strokeWidth={1.5} />
                      Upload Training Sample
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handleUpload} className="space-y-4" data-testid="training-upload-form">
                      <div>
                        <label className="text-sm text-[#111827] font-medium block mb-1.5">MRI Image</label>
                        <input
                          id="training-file-input"
                          data-testid="training-file-input"
                          type="file"
                          accept="image/*"
                          onChange={e => setFile(e.target.files?.[0] || null)}
                          className="block w-full text-sm text-[#4B5563] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-[#0EA5E9]/10 file:text-[#0EA5E9] file:font-medium file:text-sm hover:file:bg-[#0EA5E9]/20 file:cursor-pointer cursor-pointer"
                        />
                      </div>
                      <div>
                        <label className="text-sm text-[#111827] font-medium block mb-1.5">Classification Label</label>
                        <Select value={label} onValueChange={setLabel}>
                          <SelectTrigger data-testid="training-label-select" className="border-[#E5E7EB]">
                            <SelectValue placeholder="Select stroke type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="hemorrhagic">Hemorrhagic Stroke</SelectItem>
                            <SelectItem value="ischemic">Ischemic Stroke</SelectItem>
                            <SelectItem value="normal">Normal (No Stroke)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        type="submit"
                        data-testid="training-upload-btn"
                        disabled={!file || !label || uploading}
                        className="w-full bg-[#0EA5E9] hover:bg-[#0284C7] text-white gap-2"
                      >
                        {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        {uploading ? 'Uploading...' : 'Upload Sample'}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              )}

              {/* Train Model */}
              <Card className="border border-[#E5E7EB] shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle className="font-heading text-lg font-medium text-[#111827] flex items-center gap-2">
                    <Zap className="w-5 h-5 text-[#F59E0B]" strokeWidth={1.5} />
                    Train Model
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <p className="text-sm text-[#4B5563] mb-3">
                      Training requires at least <strong>5 samples</strong> from <strong>2+ classes</strong>.
                      Current: {totalSamples} samples.
                    </p>
                    <div className="space-y-2">
                      {['hemorrhagic', 'ischemic', 'normal'].map(cls => {
                        const count = status?.samples_by_class?.[cls] || 0;
                        const pct = totalSamples > 0 ? (count / totalSamples) * 100 : 0;
                        return (
                          <div key={cls} className="flex items-center gap-3">
                            <span className="text-xs text-[#4B5563] w-24 capitalize">{cls}</span>
                            <Progress value={pct} className="flex-1 h-2" />
                            <span className="text-xs font-medium text-[#111827] w-8 text-right">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {status?.latest_run && (
                    <div className="p-3 rounded-lg bg-[#F3F4F6]">
                      <p className="text-xs text-[#9CA3AF] mb-1">Last Training</p>
                      <p className="text-sm text-[#111827]">
                        {status.latest_run.samples_count} samples &middot;{' '}
                        Accuracy: {(status.latest_run.accuracy * 100).toFixed(1)}% &middot;{' '}
                        {new Date(status.latest_run.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  )}

                  {isAdmin ? (
                    <Button
                      data-testid="train-model-btn"
                      onClick={handleTrain}
                      disabled={totalSamples < 5 || training}
                      className="w-full bg-[#F59E0B] hover:bg-[#D97706] text-white gap-2"
                    >
                      {training ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                      {training ? 'Training...' : 'Start Training'}
                    </Button>
                  ) : (
                    <p className="text-xs text-[#9CA3AF] text-center">Only admins can trigger model training.</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Training History */}
            {history.length > 0 && (
              <Card className="border border-[#E5E7EB] shadow-none">
                <CardHeader className="pb-4">
                  <CardTitle className="font-heading text-lg font-medium text-[#111827] flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-[#0EA5E9]" strokeWidth={1.5} />
                    Training History
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-[#9CA3AF]">Date</TableHead>
                        <TableHead className="text-[#9CA3AF]">Trained By</TableHead>
                        <TableHead className="text-[#9CA3AF]">Samples</TableHead>
                        <TableHead className="text-[#9CA3AF]">Classes</TableHead>
                        <TableHead className="text-[#9CA3AF]">Accuracy</TableHead>
                        <TableHead className="text-[#9CA3AF]">Features</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {history.map((run, i) => (
                        <TableRow key={run.id || i}>
                          <TableCell className="text-[#4B5563] text-sm">
                            {new Date(run.created_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-[#111827] font-medium text-sm">{run.user_name || '-'}</TableCell>
                          <TableCell className="text-[#4B5563]">{run.samples_count}</TableCell>
                          <TableCell>
                            <div className="flex gap-1 flex-wrap">
                              {run.classes?.map(c => (
                                <Badge key={c} className={`${labelColors[c] || ''} border-0 text-xs capitalize`}>{c}</Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell className="text-[#111827] font-medium">
                            {run.accuracy > 0 ? `${(run.accuracy * 100).toFixed(1)}%` : 'N/A'}
                          </TableCell>
                          <TableCell className="text-[#4B5563] text-sm">{run.feature_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
