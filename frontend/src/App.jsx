import React, { useState } from 'react';

export default function App() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isPreOutlined, setIsPreOutlined] = useState(false);
  const [generationCount, setGenerationCount] = useState(1);
  const [variants, setVariants] = useState([]);
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [hoveredVariant, setHoveredVariant] = useState(null);
  const [downloadOutline, setDownloadOutline] = useState(false);

  const [modelSettings, setModelSettings] = useState({
    wallHeight: 3.0,
    wallThickness: 0.35,
    basePlate: true,
    basePlateThickness: 0.12,
    scalePercent: 100, 
  });

  const [stlStatus, setStlStatus] = useState('idle');
  const [globalError, setGlobalError] = useState(null);

  const getFormattedDate = () => {
    const d = new Date();
    return `${d.getFullYear()}${(d.getMonth() + 1).toString().padStart(2, '0')}${d.getDate().toString().padStart(2, '0')}`;
  };

  const togglePreOutlined = (val) => {
    setIsPreOutlined(val);
    setUploadedImage(null);
    setPreviewUrl(null);
    setVariants([]);
    setSelectedVariant(null);
    setStlStatus('idle');
    setGlobalError(null);
  };

  const steps = [
    { id: 1, label: "Upload Photo", status: uploadedImage ? 'done' : 'active' },
    { 
      id: 2, 
      label: "Generate Outlines", 
      status: (variants.length > 0 || isPreOutlined) ? 'done' : (uploadedImage ? 'active' : 'pending'), 
      loading: variantsLoading,
      hidden: isPreOutlined 
    },
    { 
      id: 3, 
      label: "Select Variant", 
      status: selectedVariant ? 'done' : (variants.length > 0 ? 'active' : 'pending'),
      hidden: isPreOutlined 
    },
    { id: 4, label: "Configure & Export", status: stlStatus === 'success' ? 'done' : (selectedVariant ? 'active' : 'pending') }
  ].filter(s => !s.hidden);

  const resetProcess = () => {
    setUploadedImage(null);
    setPreviewUrl(null);
    setIsPreOutlined(false);
    setVariants([]);
    setSelectedVariant(null);
    setStlStatus('idle');
    setGlobalError(null);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    setUploadedImage(file);
    setPreviewUrl(URL.createObjectURL(file));
    
    if (isPreOutlined) {
      setVariantsLoading(true);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const response = await fetch('http://localhost:8000/upload-direct', { method: 'POST', body: formData });
        const data = await response.json();
        setSelectedVariant({
          id: 'direct-upload',
          url: data.server_url,
          width: data.width || 1000,
          height: data.height || 1000
        });
      } catch (err) {
        setGlobalError("Failed to process direct upload");
      } finally {
        setVariantsLoading(false);
      }
    }
  };

  const generateOutlines = async () => {
    setGlobalError(null);
    setVariantsLoading(true);
    setVariants([]);
    setSelectedVariant(null);
    const formData = new FormData();
    formData.append('file', uploadedImage);
    formData.append('count', generationCount);
    try {
      const response = await fetch('http://localhost:8000/generate-variants', { method: 'POST', body: formData });
      const data = await response.json();
      setVariants(data.variants || []); 
    } catch (err) { 
      setGlobalError(err.message); 
    } finally { 
      setVariantsLoading(false); 
    }
  };

  const generateSTL = async () => {
    setStlStatus('working');
    const baseName = uploadedImage.name.split('.').slice(0, -1).join('.');
    const dateStr = getFormattedDate();

    try {
      const response = await fetch('http://localhost:8000/generate-stl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: selectedVariant.url, settings: modelSettings }),
      });
      const stlBlob = await response.blob();
      
      const stlUrl = window.URL.createObjectURL(stlBlob);
      const stlLink = document.createElement('a');
      stlLink.href = stlUrl;
      stlLink.setAttribute('download', `${baseName}_${dateStr}.stl`);
      document.body.appendChild(stlLink);
      stlLink.click();
      stlLink.remove();

      if (downloadOutline) {
        const imgLink = document.createElement('a');
        imgLink.href = selectedVariant.url;
        imgLink.setAttribute('download', `${baseName}_${dateStr}_outline.png`);
        document.body.appendChild(imgLink);
        imgLink.click();
        imgLink.remove();
      }

      setStlStatus('success');
    } catch (err) { 
      setStlStatus('error'); 
      setGlobalError(err.message); 
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <aside className="w-80 bg-white border-r relative flex-shrink-0">
        <div className="sticky top-0 h-screen p-8 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-10">
            <h2 className="text-2xl font-black text-indigo-900 tracking-tight italic leading-tight">
              SAND ART<br/><span className="text-indigo-400 not-italic">STUDIO</span>
            </h2>
            <img src="/logo.png" alt="Logo" className="w-12 h-12 object-contain" onError={(e) => e.target.style.display='none'}/>
          </div>
          
          <nav className="space-y-8 flex-1">
            {steps.map((step, idx) => (
              <div key={step.id} className="relative">
                <div className="flex items-start gap-4">
                  <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold transition-all ${
                    step.status === 'done' ? 'bg-green-500 text-white' : 
                    step.status === 'active' ? 'bg-indigo-600 text-white ring-4 ring-indigo-100' : 'bg-gray-100 text-gray-400'
                  }`}>
                    {step.status === 'done' ? '✓' : idx + 1}
                  </div>
                  <div>
                    <span className={`font-bold block ${step.status === 'pending' ? 'text-gray-300' : 'text-gray-700'}`}>
                      {step.label}
                    </span>
                    {step.id === 2 && step.loading && (
                      <div className="mt-3 bg-indigo-50 p-3 rounded-lg border border-indigo-100 animate-pulse text-[10px] text-indigo-600 font-bold uppercase tracking-wider">
                         AI Computing (Up to 20s)...
                      </div>
                    )}
                  </div>
                </div>
                {idx !== steps.length - 1 && <div className="absolute left-4 top-8 w-0.5 h-8 bg-gray-100 -z-10"></div>}
              </div>
            ))}
          </nav>
          <button onClick={resetProcess} className="mt-auto py-4 border-t font-bold text-xs uppercase tracking-widest text-gray-400 hover:text-red-500 transition-colors">New Project</button>
        </div>
      </aside>

      <main className="flex-1 p-12">
        <div className="max-w-4xl mx-auto space-y-16">
          <section className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">01</div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic">Import Source</h3>
              </div>
              <label className="flex items-center gap-3 cursor-pointer group">
                <input type="checkbox" checked={isPreOutlined} onChange={(e) => togglePreOutlined(e.target.checked)} className="w-5 h-5 rounded accent-indigo-600" />
                <span className="text-xs font-bold text-gray-500 group-hover:text-indigo-600">I already have an outline picture</span>
              </label>
            </div>

            {!previewUrl ? (
              <label className="block bg-white border-4 border-dashed border-gray-200 rounded-3xl p-16 text-center hover:border-indigo-400 transition-all cursor-pointer">
                <input type="file" className="hidden" onChange={handleUpload} />
                <span className="text-4xl">📸</span>
                <p className="text-xl font-bold text-gray-700 mt-4">Drop your {isPreOutlined ? 'outlined' : 'photo'} here</p>
                <p className="text-xs text-gray-400 font-bold uppercase tracking-widest mt-2">Click anywhere in this box</p>
              </label>
            ) : (
              <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex items-center gap-8">
                <img src={previewUrl} className="h-24 w-24 object-cover rounded-xl shadow-inner border-2 border-white" alt="Source" />
                {!isPreOutlined ? (
                  <div className="flex-1 flex items-center gap-4">
                    <select value={generationCount} onChange={(e) => setGenerationCount(Number(e.target.value))} className="bg-gray-50 border-none rounded-xl px-4 py-3 font-bold text-indigo-600 outline-none">
                      {[1, 2, 4].map(n => <option key={n} value={n}>{n} Variants</option>)}
                    </select>
                    <button onClick={generateOutlines} disabled={variantsLoading} className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-indigo-100">
                      {variantsLoading ? "Analyzing..." : "Generate Outlines"}
                    </button>
                  </div>
                ) : (
                  <div className="flex-1 bg-indigo-50 border border-indigo-100 px-8 py-4 rounded-xl font-bold text-indigo-600 text-center italic animate-in fade-in">
                    Outline detected. Proceed to final specs.
                  </div>
                )}
              </div>
            )}
          </section>

          {!isPreOutlined && variants.length > 0 && (
            <section className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">02</div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic">Select Favorite Outline</h3>
              </div>
              <div className="flex flex-row gap-6 overflow-x-auto pb-6 no-scrollbar">
                {variants.map((v) => (
                  <div key={v.id} onClick={() => setSelectedVariant(v)} onMouseEnter={() => setHoveredVariant(v.url)} onMouseLeave={() => setHoveredVariant(null)}
                    className={`flex-shrink-0 cursor-pointer border-4 rounded-3xl overflow-hidden bg-white transition-all duration-300 w-64 h-64 relative ${selectedVariant?.id === v.id ? 'border-green-500 ring-4 ring-green-100 shadow-xl' : 'border-transparent shadow-sm'}`}>
                    <img src={v.url} alt="Variant" className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            </section>
          )}

          {selectedVariant && (
            <section className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
              {/* Header moved outside the white box to match other steps */}
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">
                  {isPreOutlined ? '02' : '03'}
                </div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic">Final Print Specs</h3>
              </div>

              <div className="bg-white p-10 rounded-[2.5rem] shadow-xl border border-gray-100">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                  <div className="space-y-6">
                    <label className="block bg-gray-50 p-4 rounded-2xl min-h-[110px] flex flex-col justify-center border border-transparent focus-within:border-indigo-100">
                      <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Global Scale (%)</span>
                      <input type="number" value={modelSettings.scalePercent} onChange={(e) => setModelSettings(prev => ({...prev, scalePercent: e.target.value}))} className="bg-transparent w-full text-3xl font-black text-indigo-600 outline-none mt-1" />
                    </label>
                    
                    <div className="flex gap-4 p-4 bg-gray-50 rounded-2xl border border-gray-100 min-h-[110px] items-center">
                      <div className="flex-1 border-r border-gray-200 text-center">
                        <span className="text-[10px] font-bold text-gray-400 uppercase block mb-1">Final Width</span>
                        <div className="text-2xl font-black text-indigo-600">{(selectedVariant.width * 0.1 * modelSettings.scalePercent / 100).toFixed(1)}<span className="text-xs ml-1">mm</span></div>
                      </div>
                      <div className="flex-1 text-center">
                        <span className="text-[10px] font-bold text-gray-400 uppercase block mb-1">Final Height</span>
                        <div className="text-2xl font-black text-indigo-600">{(selectedVariant.height * 0.1 * modelSettings.scalePercent / 100).toFixed(1)}<span className="text-xs ml-1">mm</span></div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <label className="block bg-indigo-50 p-4 rounded-2xl min-h-[110px] flex flex-col justify-center border border-transparent focus-within:border-indigo-200">
                        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Wall Height</span>
                        <div className="flex items-baseline gap-1 mt-1">
                          <input type="number" step="0.1" value={modelSettings.wallHeight} onChange={(e) => setModelSettings(prev => ({...prev, wallHeight: e.target.value}))} className="bg-transparent w-full text-2xl font-black text-indigo-700 outline-none" />
                          <span className="text-[10px] font-black text-indigo-300">MM</span>
                        </div>
                      </label>
                      <label className="block bg-indigo-50 p-4 rounded-2xl min-h-[110px] flex flex-col justify-center border border-transparent focus-within:border-indigo-200">
                        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Wall Width</span>
                        <div className="flex items-baseline gap-1 mt-1">
                          <input type="number" step="0.1" value={modelSettings.wallThickness} onChange={(e) => setModelSettings(prev => ({...prev, wallThickness: e.target.value}))} className="bg-transparent w-full text-2xl font-black text-indigo-700 outline-none" />
                          <span className="text-[10px] font-black text-indigo-300">MM</span>
                        </div>
                      </label>
                    </div>
                    
                    <div className={`flex items-center justify-between p-6 rounded-2xl text-white shadow-lg transition-all min-h-[110px] ${modelSettings.basePlate ? 'bg-indigo-900' : 'bg-gray-400'}`}>
                      <div className="flex items-center gap-4">
                        <input type="checkbox" checked={modelSettings.basePlate} onChange={(e) => setModelSettings(prev => ({...prev, basePlate: e.target.checked}))} className="w-6 h-6 rounded-lg accent-indigo-400 cursor-pointer" />
                        <span className="text-sm font-black uppercase tracking-tight leading-tight">
                          {modelSettings.basePlate ? 'Support Plate Included' : 'No Support Plate'}
                        </span>
                      </div>
                      {modelSettings.basePlate && (
                        <div className="flex flex-col items-end">
                          <span className="text-[9px] font-black opacity-50 uppercase mb-1">Thickness</span>
                          <div className="flex items-center gap-1">
                            <input type="number" step="0.1" value={modelSettings.basePlateThickness} onChange={(e) => setModelSettings(prev => ({...prev, basePlateThickness: e.target.value}))} className="w-16 bg-white/10 rounded-lg p-2 text-xl font-black text-right text-white outline-none" />
                            <span className="text-[10px] font-black opacity-50">MM</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-10 space-y-4">
                  <label className="flex items-center gap-3 justify-center cursor-pointer group">
                    <input type="checkbox" checked={downloadOutline} onChange={(e) => setDownloadOutline(e.target.checked)} className="w-4 h-4 rounded accent-green-500" />
                    <span className="text-[11px] font-black text-gray-400 uppercase tracking-wider group-hover:text-green-600 transition-colors">Include source outline (.png) in download</span>
                  </label>
                  
                  <button onClick={generateSTL} disabled={stlStatus === 'working'} className="w-full py-6 rounded-3xl font-black text-xl tracking-tighter shadow-2xl transition-all active:scale-[0.98] bg-green-500 hover:bg-green-600 text-white disabled:bg-gray-100 disabled:text-gray-400">
                    {stlStatus === 'working' ? 'BUILDING 3D GEOMETRY...' : `DOWNLOAD ${downloadOutline ? 'FILES (STL + PNG)' : '3D MODEL (.STL)'}`}
                  </button>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      {hoveredVariant && (
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[999] pointer-events-none">
          <div className="bg-white p-4 rounded-[3rem] shadow-2xl border-8 border-white animate-in zoom-in duration-200">
            <img src={hoveredVariant} alt="Zoomed" className="w-[500px] h-[500px] object-contain rounded-[2rem]" />
          </div>
        </div>
      )}
    </div>
  );
}