import React, { useState, useEffect } from 'react';

export default function App() {
  // INTERNAL STATE MODEL
  const [uploadedImage, setUploadedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [generationCount, setGenerationCount] = useState(1);
  const [variants, setVariants] = useState([]);
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [modelSettings, setModelSettings] = useState({
    wallHeight: 3,
    wallThickness: 0.8,
    basePlate: true,
    targetSize: 150
  });
  const [stlStatus, setStlStatus] = useState('idle'); // idle, working, success, error
  const [stlDownloadUrl, setStlDownloadUrl] = useState(null);
  const [globalError, setGlobalError] = useState(null);

  // 11. GLOBAL ERROR HANDLING (Auto-dismiss)
  useEffect(() => {
    if (globalError) {
      const timer = setTimeout(() => setGlobalError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [globalError]);

  // 2. IMAGE INPUT ZONE HANDLERS
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size < 10000) {
        setGlobalError("Image is too small for processing.");
        return;
      }
      setUploadedImage(file);
      setPreviewUrl(URL.createObjectURL(file));
      // Reset pipeline
      setVariants([]);
      setSelectedVariant(null);
      setStlDownloadUrl(null);
    }
  };

  // 3. VARIANT GENERATION (Connected to Backend)
  const generateOutlines = async () => {
    if (!uploadedImage) return;
    
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

      if (!response.ok) throw new Error('Failed to generate outlines');

      const data = await response.json();
      // Expecting data.variants to be an array of image URLs/base64
      setVariants(data.variants); 
    } catch (err) {
      setGlobalError("Backend Error: " + err.message);
    } finally {
      setVariantsLoading(false);
    }
  };

  // 7. GENERATE STL (Connected to Backend)
  const generateSTL = async () => {
    if (!selectedVariant) return;

    setStlStatus('working');
    setGlobalError(null);

    try {
      const response = await fetch('http://localhost:8000/generate-stl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          variant_id: selectedVariant.id,
          image_url: selectedVariant.url,
          settings: modelSettings
        }),
      });

      if (!response.ok) throw new Error('Failed to build 3D model');

      // 1. Get the binary data
      const blob = await response.blob();
      
      // 2. Create a download link in memory
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // 3. Force the filename
      link.setAttribute('download', `sand-art-${Date.now()}.stl`);
      
      // 4. Append, click, and cleanup
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url); // Free up memory

      setStlStatus('success');
    } catch (err) {
      setStlStatus('error');
      setGlobalError("3D Generation Error: " + err.message);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      {/* 1. HEADER AREA */}
      <header className="text-center border-b pb-6">
        <h1 className="text-3xl font-bold text-indigo-700">Sand Art Generator</h1>
        <p className="text-gray-600">Upload a portrait. Get printable outline walls for sand art.</p>
      </header>

      {/* 2. IMAGE INPUT ZONE */}
      <section className="bg-white p-6 rounded-xl shadow-sm border-2 border-dashed border-gray-300">
        {!previewUrl ? (
          <label className="flex flex-col items-center justify-center cursor-pointer h-40">
            <span className="text-gray-500">Drop an image or click to upload</span>
            <input type="file" className="hidden" onChange={handleFileUpload} accept="image/png, image/jpeg" />
          </label>
        ) : (
          <div className="relative flex flex-col items-center">
            <img src={previewUrl} alt="Preview" className="h-48 rounded-lg mb-4" />
            <button 
              onClick={() => {setPreviewUrl(null); setUploadedImage(null); setVariants([]);}}
              className="text-red-500 text-sm font-semibold underline"
            >Clear Image</button>
          </div>
        )}
      </section>

      {/* 3. VARIANT GENERATION CONTROLS */}
      {previewUrl && (
        <section className="flex items-center justify-between bg-indigo-50 p-4 rounded-lg">
          <div className="flex items-center gap-4">
            <label className="font-medium">How many versions?</label>
            <select 
              value={generationCount} 
              onChange={(e) => setGenerationCount(Number(e.target.value))}
              className="border rounded p-1"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={4}>4</option>
            </select>
          </div>
          <button 
            onClick={generateOutlines}
            disabled={variantsLoading}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:bg-gray-400"
          >
            {variantsLoading ? "Generating..." : "Generate Outlines"}
          </button>
        </section>
      )}

      {/* 4. PREVIEW GRID */}
      <section className={`grid gap-4 ${generationCount > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
        {variantsLoading && <div className="col-span-full text-center p-10 font-medium">GPT is imagining your outlines...</div>}
        {variants.map((v) => (
          <div 
            key={v.id}
            onClick={() => setSelectedVariant(v)}
            className={`cursor-pointer border-4 rounded-lg overflow-hidden relative ${selectedVariant?.id === v.id ? 'border-green-500' : 'border-transparent'}`}
          >
            <img src={v.url} alt="Variant" className="w-full" />
            {selectedVariant?.id === v.id && (
              <span className="absolute top-2 right-2 bg-green-500 text-white px-2 py-1 text-xs rounded">Selected</span>
            )}
          </div>
        ))}
      </section>

      {/* 6. 3D PARAMETERS PANEL */}
      {selectedVariant && (
        <section className="bg-white p-6 rounded-xl shadow-md border">
          <h3 className="text-lg font-bold mb-4">3D Parameters</h3>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium">Wall Height (mm)</label>
              <input type="number" value={modelSettings.wallHeight} className="border w-full p-2 rounded" />
              <p className="text-xs text-gray-500 mt-1">Height of the portrait walls</p>
            </div>
            <div>
              <label className="block text-sm font-medium">Wall Thickness (mm)</label>
              <input type="number" step="0.1" value={modelSettings.wallThickness} className="border w-full p-2 rounded" />
              <p className="text-xs text-gray-500 mt-1">Recommended: 0.8mm for 2 perimeters</p>
            </div>
          </div>
          
          <div className="mt-4 flex items-center gap-2">
            <input 
              type="checkbox" 
              checked={modelSettings.basePlate} 
              onChange={(e) => setModelSettings({...modelSettings, basePlate: e.target.checked})} 
            />
            <label className="text-sm font-medium">Add a support plate</label>
          </div>

          <button 
            onClick={generateSTL}
            disabled={stlStatus === 'working'}
            className="w-full mt-6 bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 disabled:bg-gray-400"
          >
            {stlStatus === 'working' ? "Building 3D Model..." : "Generate STL File"}
          </button>
        </section>
      )}

      {/* 9. DOWNLOAD SECTION */}
      {stlStatus === 'success' && (
        <div className="bg-green-100 p-6 rounded-xl text-center border-2 border-green-300">
          <p className="text-green-800 font-bold mb-4">Success! Your STL is ready.</p>
          <a 
            href={stlDownloadUrl} 
            className="bg-green-600 text-white px-8 py-3 rounded-full font-bold inline-block"
          >Download STL</a>
        </div>
      )}

      {/* 10. GLOBAL ERROR */}
      {globalError && (
        <div className="fixed bottom-4 right-4 bg-red-600 text-white px-6 py-3 rounded-lg shadow-xl">
          {globalError}
        </div>
      )}

      {/* 11. FOOTER */}
      <footer className="text-center text-gray-400 text-xs py-10">
        Experimental tool for sand-art enthusiasts.
      </footer>
    </div>
  );
}