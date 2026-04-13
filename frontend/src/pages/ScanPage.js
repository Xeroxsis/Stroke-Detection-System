import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import DashboardLayout from '../components/DashboardLayout';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Upload, X, ScanLine, Loader2, Image as ImageIcon, Zap, Eye, Brain } from 'lucide-react';
import { toast } from 'sonner';

const classMap = {
  hemorrhagic: { label: 'Hemorrhagic', color: 'bg-[#E11D48]/10 text-[#E11D48]', border: 'border-[#E11D48]/30' },
  ischemic: { label: 'Ischemic', color: 'bg-[#F59E0B]/10 text-[#F59E0B]', border: 'border-[#F59E0B]/30' },
  normal: { label: 'Normal', color: 'bg-[#10B981]/10 text-[#10B981]', border: 'border-[#10B981]/30' },
};

export default function ScanPage() {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [batchResults, setBatchResults] = useState([]);
  const [demoImages, setDemoImages] = useState([]);
  const [loadingDemos, setLoadingDemos] = useState(false);
  const [analyzingDemos, setAnalyzingDemos] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/patients').then(r => setPatients(r.data)).catch(() => {});
    api.get('/demo/images').then(r => setDemoImages(r.data)).catch(() => {});
  }, []);

  const addFiles = useCallback((newFiles) => {
    const valid = [];
    for (const f of newFiles) {
      if (f.size > 10 * 1024 * 1024) { toast.error(`${f.name} too large (max 10MB)`); continue; }
      valid.push(f);
    }
    if (valid.length === 0) return;
    setFiles(prev => [...prev, ...valid]);
    valid.forEach(f => {
      const reader = new FileReader();
      reader.onload = e => setPreviews(prev => [...prev, { name: f.name, src: e.target.result }]);
      reader.readAsDataURL(f);
    });
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files?.length) addFiles(Array.from(e.dataTransfer.files));
  }, [addFiles]);

  const removeFile = (idx) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
    setPreviews(prev => prev.filter((_, i) => i !== idx));
  };

  const clearAll = () => { setFiles([]); setPreviews([]); setBatchResults([]); };

  const handleBatchAnalyze = async () => {
    if (files.length === 0) { toast.error('Add at least one MRI image'); return; }
    setAnalyzing(true);
    setBatchResults([]);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      if (selectedPatient) {
        formData.append('patient_id', selectedPatient);
        const pt = patients.find(p => p.id === selectedPatient);
        if (pt) formData.append('patient_name', pt.name);
      } else {
        formData.append('patient_name', 'Batch Scan');
      }
      const { data } = await api.post('/scans/batch-analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setBatchResults(data);
      toast.success(`Analyzed ${data.length} image${data.length > 1 ? 's' : ''}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Batch analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAnalyzeDemos = async () => {
    setAnalyzingDemos(true);
    setBatchResults([]);
    try {
      const { data } = await api.post('/demo/analyze-all');
      setBatchResults(data);
      toast.success(`Analyzed ${data.length} demo images`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Demo analysis failed');
    } finally {
      setAnalyzingDemos(false);
    }
  };

  const loadDemoImage = async (demo) => {
    setLoadingDemos(true);
    try {
      const response = await api.get(`/demo/images/${demo.id}`, { responseType: 'blob' });
      const blob = response.data;
      const file = new File([blob], demo.filename, { type: 'image/png' });
      addFiles([file]);
      toast.success(`Loaded ${demo.label}`);
    } catch {
      toast.error('Failed to load demo image');
    } finally {
      setLoadingDemos(false);
    }
  };

  return (
    <DashboardLayout>
      <div data-testid="scan-page" className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-medium text-[#111827]">MRI Analysis</h1>
          <p className="text-sm text-[#9CA3AF] mt-1">Upload MRI images or use demo samples for stroke detection</p>
        </div>

        {/* Patient Selection */}
        <Card className="border border-[#E5E7EB] shadow-none">
          <CardContent className="p-5 space-y-3">
            <p className="text-xs uppercase tracking-[0.2em] font-bold text-[#9CA3AF]">Patient (Optional)</p>
            <Select value={selectedPatient} onValueChange={setSelectedPatient}>
              <SelectTrigger data-testid="patient-select" className="border-[#E5E7EB]">
                <SelectValue placeholder="Select a patient or leave empty" />
              </SelectTrigger>
              <SelectContent>
                {patients.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name} - Age {p.age}, {p.gender}</SelectItem>
                ))}
                {patients.length === 0 && (
                  <div className="p-3 text-sm text-[#9CA3AF] text-center">No patients yet.</div>
                )}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid grid-cols-2 bg-[#F3F4F6]">
            <TabsTrigger value="upload" data-testid="tab-upload">Upload Images</TabsTrigger>
            <TabsTrigger value="demo" data-testid="tab-demo">Demo Images</TabsTrigger>
          </TabsList>

          {/* Upload Tab */}
          <TabsContent value="upload" className="space-y-5 mt-5">
            <Card className="border border-[#E5E7EB] shadow-none">
              <CardContent className="p-5">
                <div
                  data-testid="upload-dropzone"
                  onDrop={handleDrop}
                  onDragOver={e => { e.preventDefault(); setDragActive(true); }}
                  onDragLeave={() => setDragActive(false)}
                  onClick={() => document.getElementById('file-input').click()}
                  className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
                    ${dragActive ? 'border-[#0EA5E9] bg-[#0EA5E9]/5' : 'border-[#E5E7EB] hover:border-[#93C5FD] hover:bg-[#F3F4F6]/50'}`}
                >
                  <Upload className="w-9 h-9 text-[#9CA3AF] mx-auto mb-3" strokeWidth={1.5} />
                  <p className="text-[#111827] font-medium mb-1">Drop MRI images here</p>
                  <p className="text-sm text-[#9CA3AF]">Select multiple files for batch analysis (max 10MB each)</p>
                  <input
                    id="file-input"
                    data-testid="file-input"
                    type="file"
                    accept="image/*,.dcm"
                    multiple
                    className="hidden"
                    onChange={e => { if (e.target.files?.length) addFiles(Array.from(e.target.files)); }}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Selected Files Grid */}
            {previews.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-[#111827]">{previews.length} image{previews.length > 1 ? 's' : ''} selected</p>
                  <Button variant="ghost" size="sm" onClick={clearAll} className="text-[#9CA3AF] hover:text-[#E11D48]">
                    <X className="w-4 h-4 mr-1" /> Clear All
                  </Button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {previews.map((p, i) => (
                    <div key={i} className="relative group rounded-lg overflow-hidden border border-[#E5E7EB] bg-[#F3F4F6]">
                      <img src={p.src} alt={p.name} className="w-full h-32 object-cover" />
                      <button
                        onClick={() => removeFile(i)}
                        className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-white/80 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3 text-[#4B5563]" />
                      </button>
                      <p className="text-[10px] text-[#4B5563] p-1.5 truncate">{p.name}</p>
                    </div>
                  ))}
                </div>
                <Button
                  data-testid="batch-analyze-btn"
                  onClick={handleBatchAnalyze}
                  disabled={analyzing}
                  className="w-full bg-[#0EA5E9] hover:bg-[#0284C7] text-white rounded-lg py-3 text-base gap-2"
                >
                  {analyzing ? <><Loader2 className="w-4 h-4 animate-spin" /> Analyzing {files.length} images...</>
                    : <><ScanLine className="w-4 h-4" /> Analyze {files.length} Image{files.length > 1 ? 's' : ''}</>}
                </Button>
              </div>
            )}
          </TabsContent>

          {/* Demo Tab */}
          <TabsContent value="demo" className="space-y-5 mt-5">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[#4B5563]">Pre-loaded synthetic MRI images for demonstration</p>
              <Button
                data-testid="analyze-all-demos-btn"
                onClick={handleAnalyzeDemos}
                disabled={analyzingDemos}
                className="bg-[#F59E0B] hover:bg-[#D97706] text-white gap-2"
              >
                {analyzingDemos ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                {analyzingDemos ? 'Analyzing...' : 'Analyze All Demos'}
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {demoImages.map(demo => (
                <Card key={demo.id} className="border border-[#E5E7EB] shadow-none hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 overflow-hidden">
                  <div className="h-36 bg-[#111827] flex items-center justify-center relative">
                    <img
                      src={`${process.env.REACT_APP_BACKEND_URL}/api/demo/images/${demo.id}`}
                      alt={demo.label}
                      className="h-full w-full object-contain"
                      crossOrigin="anonymous"
                    />
                    <Badge className={`absolute top-2 right-2 ${classMap[demo.expected]?.color || ''} border-0 text-[10px]`}>
                      {demo.expected}
                    </Badge>
                  </div>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Brain className="w-4 h-4 text-[#0EA5E9]" strokeWidth={1.5} />
                      <p className="font-medium text-sm text-[#111827]">{demo.label}</p>
                    </div>
                    <p className="text-xs text-[#9CA3AF] leading-relaxed mb-3 line-clamp-2">{demo.description}</p>
                    <Button
                      variant="outline"
                      size="sm"
                      data-testid={`load-demo-${demo.id}`}
                      disabled={loadingDemos}
                      onClick={() => loadDemoImage(demo)}
                      className="w-full text-xs border-[#E5E7EB] text-[#4B5563] hover:bg-[#F3F4F6] gap-1.5"
                    >
                      <ImageIcon className="w-3 h-3" /> Add to Upload Queue
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>

        {/* Batch Results */}
        {batchResults.length > 0 && (
          <div className="space-y-4" data-testid="batch-results">
            <div className="flex items-center gap-2">
              <ScanLine className="w-5 h-5 text-[#0EA5E9]" strokeWidth={1.5} />
              <h2 className="font-heading text-lg font-medium text-[#111827]">Analysis Results</h2>
              <Badge className="bg-[#0EA5E9]/10 text-[#0EA5E9] border-0">{batchResults.length}</Badge>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {batchResults.map((r, i) => {
                if (r.error) {
                  return (
                    <Card key={i} className="border border-[#E11D48]/20 shadow-none bg-[#E11D48]/5">
                      <CardContent className="p-4">
                        <p className="text-sm font-medium text-[#E11D48]">{r.filename}</p>
                        <p className="text-xs text-[#E11D48]/70 mt-1">{r.error}</p>
                      </CardContent>
                    </Card>
                  );
                }
                const cls = classMap[r.classification] || classMap.normal;
                return (
                  <Card
                    key={r.id}
                    className={`border ${cls.border} shadow-none hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 cursor-pointer`}
                    onClick={() => navigate(`/scan/${r.id}`)}
                    data-testid={`result-card-${r.id}`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <Badge className={`${cls.color} border-0 font-semibold text-xs`}>{cls.label}</Badge>
                        <span className="text-xs font-medium text-[#111827]">{(r.confidence * 100).toFixed(1)}%</span>
                      </div>
                      <p className="text-sm font-medium text-[#111827] truncate">{r.filename || r.patient_name}</p>
                      <p className="text-xs text-[#9CA3AF] mt-1">{new Date(r.created_at).toLocaleString()}</p>
                      <div className="mt-3 flex items-center gap-1.5 text-xs text-[#0EA5E9] font-medium">
                        <Eye className="w-3 h-3" /> View Full Results
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {(analyzing || analyzingDemos) && (
          <div className="text-center space-y-3">
            <div className="w-full h-2 bg-[#F3F4F6] rounded-full overflow-hidden">
              <div className="h-full bg-[#0EA5E9] rounded-full animate-pulse" style={{ width: '70%' }} />
            </div>
            <p className="text-sm text-[#9CA3AF]">Running ML analysis on images...</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
