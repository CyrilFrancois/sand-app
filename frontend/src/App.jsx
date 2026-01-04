import React, { useState } from 'react';

export default function App() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [generationCount, setGenerationCount] = useState(1);
  const [variants, setVariants] = useState([]);
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [hoveredVariant, setHoveredVariant] = useState(null); // For the overlay
  
  const [modelSettings, setModelSettings] = useState({
    wallHeight: 3.0,
    wallThickness: 0.4,
    basePlate: true,
    basePlateThickness: 0.4,
    scalePercent: 100, 
  });

  const [stlStatus, setStlStatus] = useState('idle');
  const [globalError, setGlobalError] = useState(null);

  // STEP LOGIC
  const steps = [
    { id: 1, label: "Upload Photo", status: uploadedImage ? 'done' : 'active' },
    { id: 2, label: "Generate Outlines", status: variants.length > 0 ? 'done' : (uploadedImage ? 'active' : 'pending'), loading: variantsLoading },
    { id: 3, label: "Select Variant", status: selectedVariant ? 'done' : (variants.length > 0 ? 'active' : 'pending') },
    { id: 4, label: "Configure & Export", status: stlStatus === 'success' ? 'done' : (selectedVariant ? 'active' : 'pending') }
  ];

  const resetProcess = () => {
    setUploadedImage(null);
    setPreviewUrl(null);
    setVariants([]);
    setSelectedVariant(null);
    setStlStatus('idle');
    setGlobalError(null);
  };

  const updateSetting = (key, value) => {
    const val = (key === 'basePlate') ? value : parseFloat(value) || value;
    setModelSettings(prev => ({ ...prev, [key]: val }));
  };

  const generateOutlines = async () => {
    // RESET PROGRESS: Clear existing variants and selection if regenerating
    setVariants([]);
    setSelectedVariant(null);
    setStlStatus('idle');
    
    setVariantsLoading(true);
    const formData = new FormData();
    formData.append('file', uploadedImage);
    formData.append('count', generationCount);
    try {
      const response = await fetch('http://localhost:8000/generate-variants', { method: 'POST', body: formData });
      const data = await response.json();
      setVariants(data.variants); 
    } catch (err) { setGlobalError(err.message); } finally { setVariantsLoading(false); }
  };

  const generateSTL = async () => {
    setStlStatus('working');
    try {
      const response = await fetch('http://localhost:8000/generate-stl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: selectedVariant.url, settings: modelSettings }),
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sand-art-${Date.now()}.stl`);
      link.click();
      setStlStatus('success');
    } catch (err) { setStlStatus('error'); setGlobalError(err.message); }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* SIDEBAR */}
      <aside className="w-80 bg-white border-r relative flex-shrink-0">
        <div className="sticky top-0 h-screen p-8 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-10">
            <h2 className="text-2xl font-black text-indigo-900 tracking-tight italic leading-tight">
              SAND ART<br/><span className="text-indigo-400 not-italic">STUDIO</span>
            </h2>
            {/* LOGO RESSOURCE: Put your logo.png in /public folder */}
            <img src="/logo.png" alt="Logo" className="w-12 h-12 object-contain" onError={(e) => e.target.style.display='none'}/>
          </div>
          
          <nav className="space-y-8 flex-1">
            {steps.map((step) => (
              <div key={step.id} className="relative">
                <div className="flex items-start gap-4">
                  <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold transition-all ${
                    step.status === 'done' ? 'bg-green-500 text-white' : 
                    step.status === 'active' ? 'bg-indigo-600 text-white ring-4 ring-indigo-100' : 'bg-gray-100 text-gray-400'
                  }`}>
                    {step.status === 'done' ? '✓' : step.id}
                  </div>
                  <div>
                    <span className={`font-bold block ${step.status === 'pending' ? 'text-gray-300' : 'text-gray-700'}`}>
                      {step.label}
                    </span>
                    {step.id === 2 && step.loading && (
                      <div className="mt-3 bg-indigo-50 p-3 rounded-lg border border-indigo-100 animate-pulse text-[10px] text-indigo-600 font-bold uppercase tracking-wider">
                         AI Computing (up to 20s)...
                      </div>
                    )}
                  </div>
                </div>
                {step.id !== 4 && <div className="absolute left-4 top-8 w-0.5 h-8 bg-gray-100 -z-10"></div>}
              </div>
            ))}
          </nav>

          <button onClick={resetProcess} className="mt-auto flex items-center justify-center gap-2 text-gray-400 hover:text-red-500 transition-colors py-4 border-t font-bold text-xs uppercase tracking-widest">
            New Project
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 p-12">
        <div className="max-w-4xl mx-auto space-y-16">
          
          {/* 1. IMPORT */}
          <section className="space-y-6">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">01</div>
              <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic">Import Source</h3>
            </div>
            {!previewUrl ? (
              <div className="bg-white border-4 border-dashed border-gray-200 rounded-3xl p-16 text-center hover:border-indigo-400 transition-all cursor-pointer">
                <input type="file" id="u-file" className="hidden" onChange={(e) => {
                  const f = e.target.files[0];
                  setUploadedImage(f);
                  setPreviewUrl(URL.createObjectURL(f));
                }} />
                <label htmlFor="u-file" className="cursor-pointer">
                  <span className="text-4xl">📸</span>
                  <p className="text-xl font-bold text-gray-700 mt-4">Drop your photo here</p>
                </label>
              </div>
            ) : (
              <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex items-center gap-8">
                <img src={previewUrl} className="h-24 w-24 object-cover rounded-xl shadow-inner border-2 border-white" alt="Source" />
                <div className="flex-1 flex items-center gap-4">
                  <select value={generationCount} onChange={(e) => setGenerationCount(Number(e.target.value))} className="bg-gray-50 border-none rounded-xl px-4 py-3 font-bold text-indigo-600 outline-none">
                    {[1, 2, 4].map(n => <option key={n} value={n}>{n} Variants</option>)}
                  </select>
                  <button onClick={generateOutlines} disabled={variantsLoading} className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-indigo-100">
                    {variantsLoading ? "Analyzing..." : "Generate Outlines"}
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* 2. VARIANT SELECTION & OVERLAY ZOOM */}
          {variants.length > 0 && (
            <section className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">02</div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic">Select Favorite Outline</h3>
              </div>
              
              <div className="flex flex-row gap-6 overflow-x-auto pb-6 no-scrollbar">
                {variants.map((v) => (
                  <div 
                    key={v.id}
                    onClick={() => setSelectedVariant(v)}
                    onMouseEnter={() => setHoveredVariant(v.url)}
                    onMouseLeave={() => setHoveredVariant(null)}
                    className={`flex-shrink-0 cursor-pointer border-4 rounded-3xl overflow-hidden bg-white transition-all duration-300 w-64 h-64 relative ${
                      selectedVariant?.id === v.id ? 'border-green-500 ring-4 ring-green-100 shadow-xl' : 'border-transparent shadow-sm'
                    }`}
                  >
                    <img src={v.url} alt="Variant" className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 3. CONFIGURATION */}
          {selectedVariant && (
            <section className="bg-white p-10 rounded-[2.5rem] shadow-xl border border-gray-100">
               <div className="flex items-center gap-4 mb-10">
                <div className="w-10 h-10 bg-indigo-600 text-white rounded-xl flex items-center justify-center text-lg font-black italic">03</div>
                <h3 className="text-2xl font-black text-gray-900 tracking-tighter uppercase italic flex items-center gap-3">
                  Final Print Specs
                  <div className="group relative">
                    <span className="inline-flex items-center justify-center w-6 h-6 bg-gray-200 text-gray-500 rounded-full text-xs font-bold cursor-help not-italic">?</span>
                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-3 w-64 p-4 bg-gray-900 text-white text-[11px] rounded-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-2xl z-[100]">
                      Check your .STL file with <strong>Microsoft 3D Viewer</strong>.
                      <a href="https://apps.microsoft.com/detail/9nblggh42ths?hl=en-us&gl=CA" target="_blank" rel="noreferrer" className="block mt-2 text-indigo-400 font-bold underline pointer-events-auto">Download Here</a>
                    </div>
                  </div>
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                <div className="space-y-6">
                  <label className="block">
                    <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Global Scale (%)</span>
                    <input type="number" value={modelSettings.scalePercent} onChange={(e) => updateSetting('scalePercent', e.target.value)} className="mt-2 w-full p-4 bg-gray-50 border-none rounded-2xl text-xl font-black text-indigo-600 outline-none" />
                  </label>
                  <div className="flex gap-4 p-4 bg-gray-50 rounded-2xl border border-gray-100">
                    <div className="flex-1 border-r text-center">
                      <span className="text-[10px] font-bold text-gray-400 uppercase">Width</span>
                      <div className="text-lg font-black text-gray-800">{(selectedVariant.width * 0.1 * modelSettings.scalePercent / 100).toFixed(1)} mm</div>
                    </div>
                    <div className="flex-1 text-center">
                      <span className="text-[10px] font-bold text-gray-400 uppercase">Height</span>
                      <div className="text-lg font-black text-gray-800">{(selectedVariant.height * 0.1 * modelSettings.scalePercent / 100).toFixed(1)} mm</div>
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <label className="block">
                      <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Wall Height (mm)</span>
                      <input type="number" step="0.1" value={modelSettings.wallHeight} onChange={(e) => updateSetting('wallHeight', e.target.value)} className="mt-2 w-full p-4 bg-indigo-50 border-none rounded-2xl font-black text-indigo-700" />
                    </label>
                    <label className="block">
                      <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Wall Width (mm)</span>
                      <input type="number" step="0.1" value={modelSettings.wallThickness} onChange={(e) => updateSetting('wallThickness', e.target.value)} className="mt-2 w-full p-4 bg-indigo-50 border-none rounded-2xl font-black text-indigo-700" />
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-indigo-900 rounded-2xl text-white shadow-lg">
                    <div className="flex items-center gap-3">
                      <input type="checkbox" checked={modelSettings.basePlate} onChange={(e) => updateSetting('basePlate', e.target.checked)} className="w-5 h-5 accent-indigo-400" />
                      <span className="text-sm font-bold uppercase tracking-tight">Support Plate</span>
                    </div>
                    {modelSettings.basePlate && (
                      <div className="flex items-center gap-2 bg-indigo-800 px-3 py-2 rounded-xl">
                        <input type="number" step="0.1" value={modelSettings.basePlateThickness} onChange={(e) => updateSetting('basePlateThickness', e.target.value)} className="w-12 bg-transparent border-none font-black text-right outline-none text-indigo-100" />
                        <span className="text-[10px] font-black opacity-50">MM</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <button onClick={generateSTL} disabled={stlStatus === 'working'} className="w-full mt-10 py-6 rounded-3xl font-black text-xl tracking-tighter shadow-2xl transition-all active:scale-[0.98] bg-green-500 hover:bg-green-600 text-white disabled:bg-gray-100 disabled:text-gray-400">
                {stlStatus === 'working' ? 'BUILDING 3D GEOMETRY...' : 'DOWNLOAD .STL FILE'}
              </button>
            </section>
          )}
        </div>
      </main>

      {/* FIXED HOVER OVERLAY (ZOOM) */}
      {hoveredVariant && (
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[999] pointer-events-none">
          <div className="bg-white p-4 rounded-[3rem] shadow-[0_0_100px_rgba(0,0,0,0.3)] border-8 border-white animate-in zoom-in duration-200">
            <img src={hoveredVariant} alt="Zoomed" className="w-[500px] h-[500px] object-contain rounded-[2rem]" />
            <div className="text-center mt-4 text-indigo-900 font-black italic tracking-widest">DETAILED VIEW</div>
          </div>
        </div>
      )}
    </div>
  );
}