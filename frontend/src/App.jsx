import React, { useState, useEffect } from 'react';

export default function App() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [generationCount, setGenerationCount] = useState(1);
  const [variants, setVariants] = useState([]);
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState(null);
  
  const [modelSettings, setModelSettings] = useState({
    wallHeight: 3.0,
    wallThickness: 0.3,
    basePlate: true,
    basePlateThickness: 0.3,
    scalePercent: 100, 
  });

  const [stlStatus, setStlStatus] = useState('idle');
  const [globalError, setGlobalError] = useState(null);

  const getDisplayDim = (originalDim) => {
    if (!originalDim) return 0;
    const baseMm = originalDim * 0.1; 
    return ((baseMm * modelSettings.scalePercent) / 100).toFixed(1);
  };

  const updateSetting = (key, value) => {
    const val = (key === 'basePlate') ? value : parseFloat(value) || value;
    setModelSettings(prev => ({ ...prev, [key]: val }));
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      console.log("📂 File selected:", file.name, "Size:", file.size);
      setUploadedImage(file);
      setPreviewUrl(URL.createObjectURL(file));
      setVariants([]);
      setSelectedVariant(null);
    }
  };

  const generateOutlines = async () => {
    if (!uploadedImage) return;
    console.log("🚀 Starting Outline Generation. Count:", generationCount);
    setVariantsLoading(true);
    setGlobalError(null);

    const formData = new FormData();
    formData.append('file', uploadedImage);
    formData.append('count', generationCount);

    try {
      const response = await fetch('http://localhost:8000/generate-variants', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      
      const data = await response.json();
      
      // CRITICAL LOG: This shows exactly what the backend sent
      console.log("📥 BACKEND RESPONSE (Variants):", data);
      
      if (data.variants && data.variants.length > 0) {
        console.log("🔍 First Variant URL Sample:", data.variants[0].url?.substring(0, 100) + "...");
        console.log("🔍 First Variant Dimensions:", data.variants[0].width, "x", data.variants[0].height);
      } else {
        console.warn("⚠️ Backend returned an empty variants array!");
      }

      setVariants(data.variants); 
    } catch (err) {
      console.error("❌ Generation Error:", err);
      setGlobalError("Backend Error: " + err.message);
    } finally {
      setVariantsLoading(false);
    }
  };

  const generateSTL = async () => {
    if (!selectedVariant) return;
    console.log("🏗️ Generating STL with settings:", modelSettings);
    console.log("🏗️ Using variant URL (first 50 chars):", selectedVariant.url?.substring(0, 50));
    
    setStlStatus('working');

    try {
      const response = await fetch('http://localhost:8000/generate-stl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_url: selectedVariant.url,
          settings: modelSettings
        }),
      });

      if (!response.ok) throw new Error('Failed to build 3D model');
      
      console.log("📥 STL received, starting download...");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sand-art-${Date.now()}.stl`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setStlStatus('success');
    } catch (err) {
      console.error("❌ STL Error:", err);
      setStlStatus('error');
      setGlobalError("3D Generation Error: " + err.message);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8 pb-20">
      <header className="text-center border-b pb-6">
        <h1 className="text-3xl font-bold text-indigo-700">Sand Art Studio</h1>
        <p className="text-gray-600">Precision 3D Wall Generation</p>
      </header>

      {/* UPLOAD SECTION */}
      {!previewUrl ? (
        <section className="bg-white p-10 rounded-xl border-2 border-dashed border-gray-300 text-center">
          <input type="file" id="fileInput" className="hidden" onChange={handleFileUpload} />
          <label htmlFor="fileInput" className="cursor-pointer text-indigo-600 font-bold hover:underline">
            Click to upload your portrait
          </label>
        </section>
      ) : (
        <section className="bg-indigo-50 p-6 rounded-xl flex flex-col items-center">
            <img src={previewUrl} className="h-40 rounded shadow-md mb-6" alt="source" />
            
            <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                    <label className="text-sm font-bold text-gray-700">Versions:</label>
                    <select 
                        value={generationCount} 
                        onChange={(e) => setGenerationCount(Number(e.target.value))}
                        className="border rounded p-2 bg-white"
                    >
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={4}>4</option>
                    </select>
                </div>
                <button 
                    onClick={generateOutlines} 
                    disabled={variantsLoading} 
                    className="bg-indigo-600 text-white px-8 py-2 rounded-lg font-bold hover:bg-indigo-700 transition-colors"
                >
                    {variantsLoading ? "Analyzing..." : "Generate 3D Outlines"}
                </button>
            </div>
        </section>
      )}

      {/* VARIANT DISPLAY */}
      <section className={`grid gap-4 ${variants.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
        {variants.map((v) => (
          <div 
            key={v.id}
            onClick={() => {
              console.log("🎯 Variant selected:", v.id);
              setSelectedVariant(v);
            }}
            className={`cursor-pointer border-4 rounded-lg overflow-hidden transition-all bg-white ${selectedVariant?.id === v.id ? 'border-green-500 scale-[1.02]' : 'border-transparent'}`}
          >
            <img 
              src={v.url} 
              alt="Variant" 
              className="w-full h-auto" 
              onLoad={() => console.log(`🖼️ Variant ${v.id} loaded successfully`)}
              onError={() => console.error(`🖼️ Variant ${v.id} FAILED to load. URL:`, v.url?.substring(0, 50))}
            />
          </div>
        ))}
      </section>

      {/* SETTINGS PANEL */}
      {selectedVariant && (
        <section className="bg-white p-6 rounded-xl shadow-lg border-t-4 border-indigo-500">
           <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-4">
              <h4 className="font-bold text-gray-700 border-b pb-2">A. Physical Size</h4>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="text-xs text-gray-500">Scale %</label>
                  <input type="number" value={modelSettings.scalePercent} onChange={(e) => updateSetting('scalePercent', e.target.value)} className="w-full p-2 border rounded font-bold text-indigo-600" />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-gray-400">Width (mm)</label>
                  <input type="text" readOnly value={getDisplayDim(selectedVariant.width)} className="w-full p-2 border rounded bg-gray-50 text-gray-400" />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-gray-400">Height (mm)</label>
                  <input type="text" readOnly value={getDisplayDim(selectedVariant.height)} className="w-full p-2 border rounded bg-gray-50 text-gray-400" />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h4 className="font-bold text-gray-700 border-b pb-2">B. Wall & Plate</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500">Wall Height (mm)</label>
                  <input type="number" step="0.1" value={modelSettings.wallHeight} onChange={(e) => updateSetting('wallHeight', e.target.value)} className="w-full p-2 border rounded" />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Wall Thickness (mm)</label>
                  <input type="number" step="0.1" value={modelSettings.wallThickness} onChange={(e) => updateSetting('wallThickness', e.target.value)} className="w-full p-2 border rounded text-green-600 font-bold" />
                </div>
              </div>

              <div className="flex items-center justify-between bg-indigo-50 p-2 rounded">
                <div className="flex items-center gap-2">
                    <input type="checkbox" checked={modelSettings.basePlate} onChange={(e) => updateSetting('basePlate', e.target.checked)} />
                    <span className="text-sm font-medium">Base Plate</span>
                </div>
                {modelSettings.basePlate && (
                    <input type="number" step="0.1" value={modelSettings.basePlateThickness} onChange={(e) => updateSetting('basePlateThickness', e.target.value)} className="w-16 p-1 border rounded text-xs" />
                )}
              </div>
            </div>
          </div>

          <button onClick={generateSTL} disabled={stlStatus === 'working'} className="w-full mt-8 bg-green-600 text-white py-4 rounded-xl font-bold hover:bg-green-700 shadow-lg disabled:bg-gray-400">
            {stlStatus === 'working' ? "Generating 3D Mesh..." : "Create STL File"}
          </button>
        </section>
      )}

      {globalError && (
        <div className="fixed bottom-4 right-4 bg-red-600 text-white px-6 py-3 rounded-lg shadow-2xl z-50">
          {globalError}
        </div>
      )}
    </div>
  );
}